"""Load CPU weights without an entire extra float32 checkpoint in memory.

The default preserves weights: load bfloat16, convert modules individually to
float32, and re-tie shared embeddings. Optional MLP quantization is experimental;
it is never enabled automatically. Original safetensors remain unchanged.
"""
from pathlib import Path


def cpu_text_components(model_id: str, quantize_mlp: bool = False):
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

    class DynamicLinear(torch.nn.Module):
        def __init__(self, linear):
            super().__init__()
            sequence = torch.nn.Sequential(linear.float())
            self.linear = torch.ao.quantization.quantize_dynamic(
                sequence, {torch.nn.Linear: torch.ao.quantization.per_channel_dynamic_qconfig},
                inplace=True)[0]

        def forward(self, values):
            return self.linear(values.float()).to(values.dtype)

    local = Path(model_id).exists()
    config = AutoConfig.from_pretrained(model_id, local_files_only=local)
    # Transformers 4.57.6's local-checkpoint heuristic warns about Mistral's
    # regex even for newly saved Qwen/Llama configs. Preserve the native regex.
    tokenizer_options = {} if config.model_type in {"mistral", "mistral3", "voxtral", "ministral", "pixtral"} else {"fix_mistral_regex": False}
    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=local, **tokenizer_options)
    model = AutoModelForCausalLM.from_pretrained(model_id, local_files_only=local,
                                               dtype=torch.bfloat16)

    def convert(module):
        for name, child in list(module.named_children()):
            if isinstance(child, torch.nn.Linear) and name in {"gate_proj", "up_proj", "down_proj"}:
                setattr(module, name, DynamicLinear(child))
            else:
                convert(child)

    if quantize_mlp:
        convert(model)
    # Preserve attention and the vocabulary projection. Quantizing them changed
    # evidence selections substantially in the first measured trials. Float32
    # residual operations also avoid slow emulated bfloat16 CPU arithmetic.
    model.float()
    model.tie_weights()
    model.eval()
    return {"model": model, "tokenizer": tokenizer}
