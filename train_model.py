"""Task adaptation with native chat formatting and assistant-only supervision.

Produces a candidate checkpoint; never activates it based on training loss.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import shutil
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).parent.resolve()


def encode_example(record, tokenizer, max_length=768):
    messages = record["messages"]
    prefix = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=False)
    # Tokenize the completion after the exact inference prefix; includes an EOS target.
    completion = tokenizer(json.dumps(record["target"]), add_special_tokens=False)["input_ids"] + [tokenizer.eos_token_id]
    if len(prefix) + len(completion) > max_length:
        raise ValueError("Training example is too long; do not truncate away the answer.")
    ids = prefix + completion
    return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": [-100] * len(prefix) + completion}


def train_slm(model_name=None, epochs=2, batch_size=2, lr=5e-5, output_dir=None, max_steps=None):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from build_task_training_data import main as build
    random.seed(42)
    torch.manual_seed(42)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    build()
    source = model_name or str(ROOT / "models" / "nutriguide_adapted_slm")
    output_dir = Path(output_dir or ROOT / "models" / "nutrition_evidence_candidate")
    if Path(source).resolve() == output_dir.resolve():
        raise ValueError("Candidate output must not overwrite the source checkpoint.")
    train_file = ROOT / "data" / "training" / "evidence_train.jsonl"
    rows = [json.loads(line) for line in train_file.read_text(encoding="utf-8").splitlines()]
    tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=Path(source).exists())
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    examples = [encode_example(row, tokenizer) for row in rows]
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    if device == "cpu":
        from cpu_model import cpu_text_components
        model = cpu_text_components(source)["model"]
    else:
        model = AutoModelForCausalLM.from_pretrained(source, local_files_only=Path(source).exists(), dtype=torch.float32)
    model.to(device)
    # Adapt actual final blocks; previous code hard-coded intermediate layer numbers.
    layers = model.model.layers
    for param in model.parameters():
        param.requires_grad = False
    for layer in layers[-2:]:
        for param in layer.parameters():
            param.requires_grad = True
    parameters = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(parameters, lr=lr, weight_decay=0.01)
    start = time.perf_counter()
    history, steps = [], 0
    model.train()
    for epoch in range(epochs):
        random.shuffle(examples)
        for offset in range(0, len(examples), batch_size):
            items = examples[offset:offset + batch_size]
            width = max(len(item["input_ids"]) for item in items)
            batch = {key: torch.tensor([item[key] + [fill] * (width - len(item[key])) for item in items], device=device)
                     for key, fill in (("input_ids", tokenizer.pad_token_id), ("attention_mask", 0), ("labels", -100))}
            optimizer.zero_grad(set_to_none=True)
            # Project only supervised prediction positions into the vocabulary.
            # Qwen's large vocabulary otherwise materializes hundreds of MB of
            # ignored prompt logits. Token t is predicted by hidden state t-1.
            hidden = model.model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"], use_cache=False).last_hidden_state
            supervised = batch["labels"][:, 1:] != -100
            logits = model.lm_head(hidden[:, :-1][supervised])
            loss = torch.nn.functional.cross_entropy(logits.float(), batch["labels"][:, 1:][supervised])
            if not torch.isfinite(loss):
                raise RuntimeError("Training loss is not finite")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(parameters, 1.0)
            optimizer.step()
            steps += 1
            history.append(float(loss.detach().cpu()))
            print(f"step={steps} assistant_loss={history[-1]:.4f} elapsed={time.perf_counter()-start:.1f}s", flush=True)
            if max_steps is not None and steps >= max_steps:
                break
        if max_steps is not None and steps >= max_steps:
            break
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "training_records.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    # Persist compact original-format weights; evaluation reloads this saved
    # checkpoint, so any bfloat16 rounding is included in measured accuracy.
    model.to(dtype=torch.bfloat16)
    # Safetensors finalizes via atomic rename. Sync/scanner handles can block
    # that rename on OneDrive. Serialize off the sync folder, then retry copies
    # while the trained model remains alive rather than losing the entire run.
    with tempfile.TemporaryDirectory(prefix="nutriguide-checkpoint-", ignore_cleanup_errors=True) as staging:
        model.save_pretrained(staging)
        tokenizer.save_pretrained(staging)
        for path in Path(staging).iterdir():
            if path.is_file():
                for attempt in range(5):
                    try:
                        shutil.copyfile(path, output_dir / path.name)
                        break
                    except OSError:
                        if attempt == 4:
                            raise
                        time.sleep(0.5)
    meta = {"base_model": source, "role": "reviewed_evidence_selection", "steps": steps,
            "dataset_samples": len(rows), "train_sha256": hashlib.sha256(train_file.read_bytes()).hexdigest(),
            "assistant_only_loss": True, "native_chat_template": True, "seed": 42,
            "initial_loss": history[0], "final_loss": history[-1], "duration_seconds": time.perf_counter()-start,
            "validation_status": "candidate_not_qualified", "clinical_validation": False,
            "source_limitations": "The legacy SmolLM2 source previously used synthetic evaluation cases." if "nutriguide_adapted_slm" in str(source) else "Official base weights; training labels are synthetic evidence selections, not clinical cases."}
    (output_dir / "training_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2), flush=True)
    return meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--max-steps", type=int)
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.lr <= 0 or (args.max_steps is not None and args.max_steps < 1):
        parser.error("Training parameters must be positive")
    train_slm(args.model, args.epochs, args.batch_size, args.lr, args.output_dir, args.max_steps)


if __name__ == "__main__":
    main()
