"""A deliberately constrained Hugging Face SLM demo for child-nutrition education.

It retrieves only local, reviewed content before generating. It does not diagnose,
calculate a diet, or replace a clinician.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MODEL_ID = "HuggingFaceTB/SmolLM2-360M-Instruct"
ROOT = Path(__file__).parent
KB = json.loads((ROOT / "data" / "nutrition_knowledge.json").read_text())

SYSTEM = """You are NutriGuide, an educational assistant. Answer ONLY from CONTEXT.
Never invent a quantity, diagnosis, treatment, supplement, recipe, or source.
If the question is outside CONTEXT or needs individualized medical advice, say so and
recommend a pediatrician or qualified dietitian. State red flags if relevant. Use simple
language, bullets, and end with the supplied [Source IDs]."""

def find_band(age_months: int) -> dict:
    if not 0 <= age_months <= 59:
        raise ValueError("Age must be between 0 and 59 completed months.")
    bounds = [(0, 5), (6, 8), (9, 11), (12, 23), (24, 59)]
    for band, (low, high) in zip(KB["age_bands"], bounds):
        if low <= age_months <= high:
            return band
    raise AssertionError("Unreachable")

def context_for(age_months: int) -> str:
    band = find_band(age_months)
    lines = [
        f"Age group: {band['label']} ({band.get('stage_title', '')})",
        "Guidance: " + " ".join(band["core_guidance"]),
        "Meal pattern/cadence: " + band.get("meal_cadence", ""),
        "Dietary variety target: " + band.get("variety_target", ""),
        "Skills: " + band["feeding_skills"],
        "Safe textures: " + band.get("safe_textures", ""),
        "Safety: " + " ".join(band["safety"]),
    ]
    if "food_categories" in band:
        food_cat_summary = "; ".join([f"{c['group_name']}: {', '.join(c['examples'])}" for c in band["food_categories"]])
        lines.append(f"Recommended food categories & examples: {food_cat_summary}")
    if "foods_to_avoid" in band:
        lines.append("Foods to avoid or limit: " + "; ".join(band["foods_to_avoid"]))
    lines.extend([
        "Red flags needing clinician or emergency assessment: " + "; ".join(KB["red_flags"]),
        "[Source IDs: " + ", ".join(band["sources"]) + "]",
    ])
    return "\n".join(lines)

def red_flag_gate(question: str) -> str | None:
    terms = r"chok|blue|breath|unconscious|dehydrat|letharg|vomit|allergic|hives|swelling|weight loss|premature|preterm"
    if re.search(terms, question, re.I):
        return ("This could need prompt clinical assessment. For breathing trouble, blue color, "
                "unconsciousness, or active choking, seek emergency help now. For other feeding, "
                "allergy, dehydration, or growth concerns, contact a pediatric clinician. "
                "This educational module cannot assess an individual child.")
    return None

def answer(age_months: int, question: str, use_model: bool = True) -> str:
    urgent = red_flag_gate(question)
    if urgent:
        return urgent
    context = context_for(age_months)
    if not use_model:
        return context
    from transformers import pipeline
    generator = pipeline("text-generation", model=MODEL_ID)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"CONTEXT\n{context}\n\nQUESTION\n{question}"},
    ]
    output = generator(messages, max_new_tokens=220, do_sample=False)
    return output[0]["generated_text"][-1]["content"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Constrained child nutrition SLM demo")
    parser.add_argument("--age-months", required=True, type=int)
    parser.add_argument("--question", required=True)
    parser.add_argument("--context-only", action="store_true", help="Test the curated layer without downloading a model")
    args = parser.parse_args()
    print(answer(args.age_months, args.question, use_model=not args.context_only))
