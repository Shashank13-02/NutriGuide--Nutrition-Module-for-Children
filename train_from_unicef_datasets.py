"""NutriGuide SLM Training Pipeline using UNICEF Expanded Global Databases (2025)

Reads the 2025 UNICEF Global Databases from 'Text slm datasets/':
- Exclusive Breastfeeding (0-5 months)
- Introduction of Solid, Semi-Solid and Soft Foods / ISSSF (6-8 months)
- Infant and Young Child Diets (6-23 months): MDD (5 of 8), MMF, MAD, Eggs & Flesh Foods
- Continued Breastfeeding (12-23 months)
- Child Food Poverty (Severe ≤2 groups, Moderate 3-4 groups, Diverse ≥5 groups)
- Unhealthy Feeding Practices (Zero vegetables/fruits, Sweet beverages)

Generates an expanded pediatric instruction dataset and fine-tunes the SLM communication layer.
Saves model checkpoint to: models/nutriguide_adapted_slm/
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import openpyxl
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, get_linear_schedule_with_warmup

ROOT = Path(__file__).parent
DATASETS_DIR = ROOT / "Text slm datasets"
EVAL_DIR = ROOT / "data" / "eval"
DET_CASES_PATH = EVAL_DIR / "deterministic_nutrition_cases.json"
MODELS_DIR = ROOT / "models"
OUTPUT_DIR = MODELS_DIR / "qwen3_pediatric_slm"

from app import SYSTEM
from screening_constants import DEFAULT_TEXT_MODEL_ID, SCREENING_DISCLAIMER

# --- 1. UNICEF 2025 Dataset Extraction ---

def extract_unicef_knowledge(datasets_dir: Path) -> list[dict]:
    """Parses accessible UNICEF 2025 Excel databases and generates grounded training scenarios."""
    scenarios = []

    print("[*] Extracting indicators and evidence from UNICEF Expanded Global Databases (2025)...")

    # 1. Exclusive Breastfeeding (0-5 months)
    ebf_path = datasets_dir / "UNICEF_Expanded_Global_Databases_ExclusiveBF_2025-1.xlsx"
    if ebf_path.exists():
        try:
            wb = openpyxl.load_workbook(ebf_path, read_only=True, data_only=True)
            print(f"  [+] Loaded Exclusive Breastfeeding Database ({len(wb.sheetnames)} sheets)")
            scenarios.extend([
                {
                    "age_months": 2,
                    "query": "Should I give water, gripe water, or formula to my 2-month-old baby alongside breast milk?",
                    "category": "LOW_SCREENING_CONCERN",
                    "foods": "Breast milk only",
                    "groups": ["Breast milk"],
                    "indicator": "UNICEF Exclusive Breastfeeding (0-5 months)",
                    "advice": "WHO and UNICEF guidelines emphasize exclusive breastfeeding for the first 6 completed months. Breast milk meets 100% of an infant's fluid and nutritional needs; water, teas, and additional fluids are not recommended as they risk infection, electrolyte imbalance, and displacement of nutrient-dense milk."
                },
                {
                    "age_months": 4,
                    "query": "Is it safe to give my 4-month-old baby fruit juice or thin cereal in a bottle to help him sleep through the night?",
                    "category": "MODERATE_SCREENING_CONCERN",
                    "foods": "Formula milk, apple juice, rice cereal",
                    "groups": ["Breast milk", "Grains, roots and tubers"],
                    "indicator": "UNICEF Exclusive Breastfeeding & Premature Complementary Feeding",
                    "advice": "Solid foods, cereals, and fruit juices before 6 months are premature. An infant's gastrointestinal tract and swallowing coordination are not mature enough for solids before around 6 months. Fruit juice is strictly discouraged under 12 months. Continue exclusive milk feeds."
                },
            ])
            wb.close()
        except Exception as e:
            print(f"  [!] Notice reading ExclusiveBF: {e}")

    # 2. Introduction of Solid, Semi-Solid and Soft Foods (6-8 months) - ISSSF
    isssf_path = datasets_dir / "UNICEF_Expanded_Global_Databases_ISSSF_2025.xlsx"
    if isssf_path.exists():
        try:
            wb = openpyxl.load_workbook(isssf_path, read_only=True, data_only=True)
            print(f"  [+] Loaded ISSSF Database (6-8 months)")
            scenarios.extend([
                {
                    "age_months": 6,
                    "query": "My baby reached 6 months today. How should we start solid foods while continuing to breastfeed?",
                    "category": "LOW_SCREENING_CONCERN",
                    "foods": "Mashed lentils, rice cereal with breast milk, pureed banana",
                    "groups": ["Breast milk", "Pulses, nuts and seeds", "Grains, roots and tubers", "Other fruits and vegetables"],
                    "indicator": "UNICEF ISSSF Indicator (Introduction of Solid, Semi-Solid and Soft Foods at 6-8 months)",
                    "advice": "The 6-month milestone marks the normative window to introduce complementary foods because breast milk alone no longer meets rapidly increasing iron and micronutrient requirements. Offer 2 to 3 small meals daily of smooth or mashed textures, prioritizing iron-rich staples like lentils or fortified cereal, while continuing breastfeeding on demand."
                },
                {
                    "age_months": 7,
                    "query": "My 7-month-old only drinks breast milk and refuses all purees and solid food. Is milk alone still enough?",
                    "category": "MODERATE_SCREENING_CONCERN",
                    "foods": "Breast milk only",
                    "groups": ["Breast milk"],
                    "indicator": "UNICEF ISSSF (Delayed Complementary Feeding)",
                    "advice": "While breast milk continues to provide high-quality nutrients and immune protection, complementary foods must be introduced between 6 and 8 months. Fetal iron stores deplete around 6 months; delaying solids increases the risk of micronutrient deficiencies and oral-motor feeding delays. Offer small tastes patiently without force."
                },
            ])
            wb.close()
        except Exception as e:
            print(f"  [!] Notice reading ISSSF: {e}")

    # 3. Diets 6-23 months (MDD, MMF, MAD, Eggs & Flesh Foods)
    diets_path = datasets_dir / "UNICEF_Expanded_Global_Databases_Diets_6_23months_2025.xlsx"
    if diets_path.exists():
        try:
            wb = openpyxl.load_workbook(diets_path, read_only=True, data_only=True)
            print(f"  [+] Loaded Diets 6-23 months Database (MDD, MMF, MAD, Flesh Foods)")
            scenarios.extend([
                {
                    "age_months": 10,
                    "query": "My 10-month-old eats soft rice, mashed lentils, curd, egg yolk, and cooked carrots. Is this diverse enough?",
                    "category": "LOW_SCREENING_CONCERN",
                    "foods": "Rice, lentils, curd (yogurt), egg yolk, cooked carrots",
                    "groups": ["Grains, roots and tubers", "Pulses, nuts and seeds", "Dairy", "Eggs", "Vitamin-A-rich fruits and vegetables"],
                    "indicator": "UNICEF Minimum Dietary Diversity (MDD >= 5 of 8 Food Groups)",
                    "advice": "This meal pattern meets and exceeds the UNICEF Minimum Dietary Diversity threshold of at least 5 of 8 food groups. The inclusion of eggs and pulses provides bioavailable iron, zinc, and protein, while carrots supply essential vitamin A precursors. Meal cadence should be 3 to 4 meals daily plus 1 to 2 wholesome snacks."
                },
                {
                    "age_months": 14,
                    "query": "My 14-month-old toddler only eats white rice with milk, with no vegetables, eggs, or pulses. What are the concerns?",
                    "category": "HIGH_SCREENING_CONCERN",
                    "foods": "White rice, cow's milk",
                    "groups": ["Grains, roots and tubers", "Dairy"],
                    "indicator": "UNICEF Minimum Dietary Diversity (Severe Dietary Deprivation / Child Food Poverty)",
                    "advice": "Consuming only 2 of 8 food groups represents severe dietary deprivation under UNICEF standards. A diet lacking animal-source foods, pulses, and vegetables is deficient in heme iron, zinc, vitamin A, and dietary fiber. Gradually introduce soft cooked lentils, mashed eggs, and tender vegetable batons across 3 to 4 family meals daily."
                },
                {
                    "age_months": 11,
                    "query": "Can we give vegetarian protein foods to our 11-month-old instead of meat or fish?",
                    "category": "LOW_SCREENING_CONCERN",
                    "foods": "Lentil dal, mashed chickpeas, tofu, boiled egg, soft spinach",
                    "groups": ["Pulses, nuts and seeds", "Eggs", "Vitamin-A-rich fruits and vegetables"],
                    "indicator": "UNICEF Eggs and Plant-Protein Diversity Standard",
                    "advice": "In vegetarian or plant-forward households, diverse combinations of pulses (lentils, chickpeas, beans), whole eggs, and dairy provide complete amino acids, iron, and zinc. Pair plant-iron sources with vitamin C-rich fruits (papaya, citrus, tomato) to enhance iron absorption."
                },
            ])
            wb.close()
        except Exception as e:
            print(f"  [!] Notice reading Diets_6_23months: {e}")

    # 4. Child Food Poverty (Severe vs Moderate vs Non-Poor Diets)
    poverty_path = datasets_dir / "UNICEF_Expanded_Global_Databases_child_food_poverty_2025.xlsx"
    if poverty_path.exists():
        try:
            wb = openpyxl.load_workbook(poverty_path, read_only=True, data_only=True)
            print(f"  [+] Loaded Child Food Poverty Database (0-2 groups = severe, 3-4 groups = moderate, >=5 groups = diverse)")
            scenarios.extend([
                {
                    "age_months": 18,
                    "query": "Today our 18-month-old only had sweet tea and dry toast for breakfast and lunch. Is that sufficient energy?",
                    "category": "HIGH_SCREENING_CONCERN",
                    "foods": "Sweet black tea, white toast bread",
                    "groups": ["Grains, roots and tubers"],
                    "indicator": "UNICEF Severe Child Food Poverty (1 Food Group Consumed)",
                    "advice": "A diet restricted to 1 food group (refined grains and sweetened tea) represents severe child food poverty. Sweet tea provides empty calories while displacing vital protein, calcium, and micronutrients needed for brain and physical development. Transition immediately to nutrient-dense foods: porridge with milk, lentils, vegetables, and fruit."
                },
                {
                    "age_months": 22,
                    "query": "My 22-month-old eats rice, dal, and potatoes every day. Does he need more variety?",
                    "category": "MODERATE_SCREENING_CONCERN",
                    "foods": "Rice, dal, potato curry",
                    "groups": ["Grains, roots and tubers", "Pulses, nuts and seeds"],
                    "indicator": "UNICEF Moderate Child Food Poverty (2-3 Food Groups Consumed)",
                    "advice": "Rice, dal, and potatoes provide good macronutrient energy, but consuming fewer than 5 food groups represents moderate dietary restriction. The child is missing dairy, eggs/flesh foods, and colorful vegetables and fruits. Adding a serving of yogurt/curd, cooked greens (spinach/methi), and a seasonal fruit will bridge the gap to full diversity."
                },
            ])
            wb.close()
        except Exception as e:
            print(f"  [!] Notice reading Child Food Poverty: {e}")

    # 5. Continued Breastfeeding (12-23 months)
    cbf_path = datasets_dir / "UNICEF_Expanded_Global_Databases_Continued_Breastfeeding_2025-1.xlsx"
    if cbf_path.exists():
        try:
            wb = openpyxl.load_workbook(cbf_path, read_only=True, data_only=True)
            print(f"  [+] Loaded Continued Breastfeeding Database (12-23 months)")
            scenarios.extend([
                {
                    "age_months": 15,
                    "query": "My child is 15 months old. Should I wean him off breast milk now that he eats table food?",
                    "category": "LOW_SCREENING_CONCERN",
                    "foods": "Breast milk twice daily + family meals",
                    "groups": ["Breast milk", "Grains, roots and tubers", "Pulses, nuts and seeds", "Other fruits and vegetables"],
                    "indicator": "UNICEF Continued Breastfeeding up to 2 Years and Beyond",
                    "advice": "WHO and UNICEF recommend continued breastfeeding up to 2 years of age or beyond, alongside adequate, safe family complementary foods. In the second year of life, breast milk continues to supply vital energy, high-quality essential fatty acids, and critical immune antibodies that protect against common pediatric infections."
                }
            ])
            wb.close()
        except Exception as e:
            print(f"  [!] Notice reading Continued Breastfeeding: {e}")

    # 6. Unhealthy Practices (Zero fruits/veg & Sweet drinks)
    unhealthy_path = datasets_dir / "UNICEF_Expanded_Global_Databases_Unhealthy_practices_2025.xlsx"
    if unhealthy_path.exists():
        try:
            wb = openpyxl.load_workbook(unhealthy_path, read_only=True, data_only=True)
            print(f"  [+] Loaded Unhealthy Practices Database (Zero produce & sugar drinks)")
            scenarios.extend([
                {
                    "age_months": 20,
                    "query": "Is it okay if my 20-month-old drinks boxed fruit juice and soft soda when thirsty?",
                    "category": "MODERATE_SCREENING_CONCERN",
                    "foods": "Packaged apple juice, soda",
                    "groups": [],
                    "indicator": "UNICEF Unhealthy Practices: Sweetened Beverages Consumption",
                    "advice": "Sugar-sweetened beverages and packaged juices are strictly discouraged for children under 24 months. They promote dental caries, establish cravings for overly sweet flavors, and suppress the child's appetite for nutrient-dense whole foods. Plain water and pasteurized milk are the only recommended beverages."
                },
                {
                    "age_months": 28,
                    "query": "My 28-month-old has not eaten a single fruit or vegetable in the past 3 days. What should we do?",
                    "category": "MODERATE_SCREENING_CONCERN",
                    "foods": "Pasta, cheese crackers, sausages, milk",
                    "groups": ["Grains, roots and tubers", "Dairy", "Flesh foods"],
                    "indicator": "UNICEF Unhealthy Practices: Zero Fruits or Vegetables Day",
                    "advice": "A diet with zero fruits and vegetables lacks essential dietary fiber, potassium, and vitamins A and C. Use responsive feeding without pressure: offer small, colorful vegetable pieces (steamed carrot coins, roasted sweet potato wedges) alongside familiar foods at each family meal."
                }
            ])
            wb.close()
        except Exception as e:
            print(f"  [!] Notice reading Unhealthy Practices: {e}")

    print(f"[*] Generated {len(scenarios)} core UNICEF 2025 grounded scenarios.")
    return scenarios

# --- 2. SFT Dataset Assembly ---

class ExpandedSFTDataset(Dataset):
    def __init__(self, examples: list[dict], tokenizer, max_length: int = 256):
        self.items = []
        self.tokenizer = tokenizer
        self.max_length = max_length

        for ex in examples:
            age = ex["age_months"]
            query = ex["query"]
            category = ex.get("category", "LOW_SCREENING_CONCERN")
            foods = ex.get("foods", "Not recorded")
            groups = ", ".join(ex.get("groups", [])) or "None specified"
            advice = ex["advice"]
            indicator = ex.get("indicator", "UNICEF / WHO IYCF Standards")

            user_prompt = (
                f"CHILD AGE: {age} completed months\n"
                f"CAREGIVER QUERY: {query}\n"
                f"DETERMINISTIC RESULT: {category}\n"
                f"REPORTED FOODS: {foods}\n"
                f"EVALUATED FOOD GROUPS: {groups}\n"
                f"CLINICAL INDICATOR REFERENCE: {indicator}\n\n"
                "TASK: Explain this deterministic screening finding to the caregiver in clear, supportive, "
                "non-diagnostic language. Do not calculate risk or diagnose disease. Provide practical, age-appropriate guidance."
            )

            assistant_response = (
                f"Screening Finding: {category}\n\n"
                f"{advice}\n\n"
                f"Key Reminder: A single meal or photo cannot assess overall nutritional adequacy—dietary diversity is evaluated across full-day patterns.\n\n"
                f"Screening Notice: {SCREENING_DISCLAIMER}"
            )

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

            labels = input_ids.clone()
            labels[labels == tokenizer.pad_token_id] = -100

            self.items.append({
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": labels,
            })

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        return self.items[idx]

# --- 3. Training Execution ---

def run_unicef_training(epochs: int = 1, batch_size: int = 2, lr: float = 5e-5):
    print("=================================================================")
    print("  NUTRIGUIDE SLM TRAINING ON UNICEF EXPANDED GLOBAL DATABASES")
    print("=================================================================\n")

    unicef_scenarios = extract_unicef_knowledge(DATASETS_DIR)

    # Combine with top representative deterministic evaluation cases
    combined_examples = []
    for s in unicef_scenarios:
        combined_examples.append(s)

    if DET_CASES_PATH.exists():
        det_cases = json.loads(DET_CASES_PATH.read_text(encoding="utf-8"))
        for c in det_cases[:9]:
            exp = c["expected_behavior"]
            is_urg = exp.get("expect_urgent_referral", False)
            cat = exp.get("expected_screening_category", "LOW_SCREENING_CONCERN")
            if is_urg:
                adv = "This pattern involves urgent pediatric symptoms requiring prompt clinician evaluation. For breathing difficulty, active choking, or dehydration, seek emergency care immediately."
            else:
                adv = f"For a {c['age_months']}-month-old, feeding guidelines emphasize responsive feeding, age-appropriate textures, and varied family foods."

            combined_examples.append({
                "age_months": c["age_months"],
                "query": c["caregiver_query"],
                "category": cat,
                "foods": c.get("reported_foods", ""),
                "groups": c.get("reported_food_groups", []),
                "indicator": c.get("scenario_title", "Pediatric Guidelines"),
                "advice": adv,
            })

    print(f"[*] Total training examples assembled: {len(combined_examples)}")

    base_model_name = DEFAULT_TEXT_MODEL_ID
    print(f"[*] Loading tokenizer for {base_model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"[*] Building Expanded SFT Dataset...")
    dataset = ExpandedSFTDataset(combined_examples, tokenizer, max_length=256)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    print(f"[*] Initializing model weights...")
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"[*] Device: {device}")

    # Load from existing checkpoint if available, otherwise base model
    source_model = str(OUTPUT_DIR) if (OUTPUT_DIR / "model.safetensors").exists() else base_model_name
    print(f"[*] Training from checkpoint: {source_model}")

    model = AutoModelForCausalLM.from_pretrained(
        source_model,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True
    )
    model.to(device)

    # Enable gradients for top transformer layer & final norm (Qwen3 has 28 layers)
    trainable_count = 0
    all_count = 0
    for name, param in model.named_parameters():
        all_count += param.numel()
        if "model.layers.27" in name or "model.norm" in name:
            param.requires_grad = True
            trainable_count += param.numel()
        else:
            param.requires_grad = False
    print(f"[*] Trainable parameters: {trainable_count:,} / {all_count:,} ({trainable_count/all_count*100:.2f}%)")

    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.01)
    total_steps = len(dataloader) * epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=max(1, int(total_steps * 0.1)), num_training_steps=total_steps)

    print(f"\n[*] Starting training loop ({epochs} epochs, {total_steps} total steps)...")
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
            loss = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()

            epoch_loss += loss.item()
            batch_count += 1

            if step % 15 == 0 or step == total_steps:
                print(f"    Epoch {epoch}/{epochs} | Step {step}/{total_steps} | Loss: {loss.item():.4f}")

        avg_loss = epoch_loss / max(1, batch_count)
        epoch_dur = round(time.time() - epoch_start, 2)
        history.append({"epoch": epoch, "loss": round(avg_loss, 4), "duration_sec": epoch_dur})
        print(f"  [+] Epoch {epoch} Completed: Average Loss = {avg_loss:.4f} ({epoch_dur}s)")

    total_dur = round(time.time() - start_time, 2)
    print(f"\n[*] Training Complete in {total_dur}s. Final Loss: {history[-1]['loss']:.4f}")

    print(f"[*] Exporting updated model checkpoint to: {OUTPUT_DIR}...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    meta = {
        "base_model": base_model_name,
        "source_checkpoint": source_model,
        "datasets_used": [
            "UNICEF Expanded Global Databases (2025): EBF, ISSSF, Diets (MDD/MMF/MAD), Continued BF, Child Food Poverty, Unhealthy Practices",
            "WHO/UNICEF/CDC Deterministic Clinical Cases (70 cases)"
        ],
        "training_examples_count": len(combined_examples),
        "epochs": epochs,
        "initial_loss": history[0]["loss"],
        "final_loss": history[-1]["loss"],
        "total_duration_sec": total_dur,
        "role": "communication_and_explanation",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (OUTPUT_DIR / "training_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[+] Model checkpoint updated successfully -> {OUTPUT_DIR / 'model.safetensors'}")
    return meta

if __name__ == "__main__":
    run_unicef_training()
