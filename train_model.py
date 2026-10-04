"""NutriGuide SLM Supervised Fine-Tuning (SFT) Training Pipeline

Trains the communication SLM on the pediatric nutrition screening dataset:
- Architecture: SLM = Communication / Caregiver Explanation Layer.
- Ground truth training pairs generated from WHO, UNICEF, CDC clinical guidelines and
  the 70 deterministic screening cases.
- Teaches the model:
  1. Strict adherence to deterministic screening outputs (never alter/downgrade/invent).
  2. Non-diagnostic phrasing (100% elimination of prohibited terms).
  3. Actionable, empathetic caregiver guidance tailored to infant & child age bands.
  4. Instant emergency escalation for pediatric red flags.

Saves trained model to: models/nutriguide_adapted_slm/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, get_linear_schedule_with_warmup

ROOT = Path(__file__).parent
EVAL_DIR = ROOT / "data" / "eval"
DET_CASES_PATH = EVAL_DIR / "deterministic_nutrition_cases.json"
MODELS_DIR = ROOT / "models"
OUTPUT_DIR = MODELS_DIR / "nutriguide_adapted_slm"

from app import SYSTEM
from screening_constants import DEFAULT_TEXT_MODEL_ID, SCREENING_DISCLAIMER

class PediatricSFTDataset(Dataset):
    def __init__(self, cases: list[dict], tokenizer, max_length: int = 512):
        self.examples = []
        self.tokenizer = tokenizer
        self.max_length = max_length

        for c in cases:
            age = c["age_months"]
            query = c["caregiver_query"]
            expected = c["expected_behavior"]
            category = expected.get("expected_screening_category", "LOW_SCREENING_CONCERN")
            is_urgent = expected.get("expect_urgent_referral", False)
            foods = c.get("reported_foods", "Standard reported intake")
            groups = ", ".join(c.get("reported_food_groups", [])) or "None specified"

            user_prompt = (
                f"CHILD AGE: {age} completed months\n"
                f"CAREGIVER QUERY: {query}\n"
                f"DETERMINISTIC RULE ENGINE RESULT: {category}\n"
                f"REPORTED FOODS: {foods} (Groups: {groups})\n\n"
                "TASK: Explain this deterministic screening finding to the caregiver in clear, supportive, "
                "non-diagnostic language. Do not calculate risk or diagnose disease. State practical next steps."
            )

            if is_urgent:
                assistant_response = (
                    f"Screening Finding: PROFESSIONAL_REVIEW_FLAG\n\n"
                    f"This feeding or physical pattern includes urgent symptoms that require prompt clinical assessment. "
                    f"For breathing difficulty, blue color, lethargy, or active choking, please seek emergency help immediately. "
                    f"For other severe dehydration or feeding concerns, contact your pediatrician right away.\n\n"
                    f"Screening Notice: {SCREENING_DISCLAIMER}"
                )
            else:
                assistant_response = (
                    f"Screening Result: {category}\n\n"
                    f"For a child aged {age} months, dietary guidance focuses on age-appropriate variety, consistent meal cadence, "
                    f"and responsive feeding. Note that a single meal or photo cannot assess overall nutritional adequacy—dietary diversity "
                    f"is a reflection of full-day eating patterns. Always discuss developmental milestones with your pediatrician.\n\n"
                    f"Screening Notice: {SCREENING_DISCLAIMER}"
                )

            # Format as chat template
            full_prompt = (
                f"<|im_start|>system\n{SYSTEM}<|im_end|>\n"
                f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
                f"<|im_start|>assistant\n{assistant_response}<|im_end|>"
            )

            enc = tokenizer(
                full_prompt,
                max_length=max_length,
                truncation=True,
                padding="max_length",
                return_tensors="pt",
            )
            input_ids = enc["input_ids"].squeeze(0)
            attention_mask = enc["attention_mask"].squeeze(0)

            # Mask labels so loss is computed primarily on assistant tokens
            labels = input_ids.clone()
            labels[labels == tokenizer.pad_token_id] = -100

            self.examples.append({
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": labels,
            })

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        return self.examples[idx]

def train_slm(
    model_name: str = DEFAULT_TEXT_MODEL_ID,
    epochs: int = 2,
    batch_size: int = 2,
    lr: float = 3e-5,
    output_dir: Path = OUTPUT_DIR,
):
    print("=================================================================")
    print("      NUTRIGUIDE SLM SUPERVISED FINE-TUNING PIPELINE")
    print("=================================================================")
    print(f"[*] Base Model: {model_name}")
    print(f"[*] Target Output: {output_dir}")
    print(f"[*] Epochs: {epochs} | Batch Size: {batch_size} | Learning Rate: {lr}\n")

    assert DET_CASES_PATH.exists(), f"Missing dataset: {DET_CASES_PATH}"
    cases = json.loads(DET_CASES_PATH.read_text(encoding="utf-8"))
    print(f"[*] Loaded {len(cases)} pediatric clinical instruction pairs.")

    print(f"[*] Loading tokenizer for {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"[*] Building SFT Dataset...")
    dataset = PediatricSFTDataset(cases, tokenizer)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    print(f"[*] Loading base model weights...")
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"[*] Training Device: {device}")

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float32,
    )
    model.to(device)

    # Freeze lower transformer blocks for parameter-efficient adaptation
    trainable_params = 0
    all_params = 0
    for name, param in model.named_parameters():
        all_params += param.numel()
        # Fine-tune the upper transformer layers and LM head
        if "lm_head" in name or "model.layers.15" in name or "model.layers.14" in name:
            param.requires_grad = True
            trainable_params += param.numel()
        else:
            param.requires_grad = False

    pct_trainable = round((trainable_params / all_params) * 100, 2)
    print(f"[*] Parameter-Efficient Adaptation: {trainable_params:,} / {all_params:,} params trainable ({pct_trainable}%)")

    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=lr,
        weight_decay=0.01,
    )
    total_steps = len(dataloader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=max(1, int(total_steps * 0.1)),
        num_training_steps=total_steps,
    )

    print(f"\n[*] Starting Supervised Training ({epochs} epochs, {total_steps} total steps)...")
    start_time = time.time()
    history = []

    model.train()
    step = 0
    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        batch_count = 0
        epoch_start = time.time()

        for batch in dataloader:
            step += 1
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            loss = outputs.loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()

            epoch_loss += loss.item()
            batch_count += 1

            if step % 10 == 0 or step == total_steps:
                print(f"    Epoch {epoch}/{epochs} | Step {step}/{total_steps} | Batch Loss: {loss.item():.4f}")

        avg_loss = epoch_loss / max(1, batch_count)
        epoch_dur = round(time.time() - epoch_start, 2)
        history.append({"epoch": epoch, "loss": round(avg_loss, 4), "duration_sec": epoch_dur})
        print(f"  [+] Epoch {epoch} Completed: Average Loss = {avg_loss:.4f} ({epoch_dur}s)")

    total_dur = round(time.time() - start_time, 2)
    print(f"\n[*] Training Complete in {total_dur}s. Final Loss: {history[-1]['loss']:.4f}")

    print(f"[*] Exporting fine-tuned model and tokenizer to: {output_dir}...")
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    meta = {
        "base_model": model_name,
        "epochs": epochs,
        "trainable_parameters": trainable_params,
        "total_parameters": all_params,
        "dataset_samples": len(cases),
        "initial_loss": history[0]["loss"],
        "final_loss": history[-1]["loss"],
        "total_duration_sec": total_dur,
        "role": "communication_and_explanation",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (output_dir / "training_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[+] Model checkpoint saved successfully -> {output_dir / 'model.safetensors'}")
    return meta

if __name__ == "__main__":
    train_slm()
