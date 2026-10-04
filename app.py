"""A constrained Hugging Face SLM component supporting child nutrition intake screening and caregiver education.

The target scope covers children from birth to 6 years of age (0 to 72 completed months;
current implemented evidence bands cover 0 to 59 completed months).
It retrieves only local, reviewed content before generating. It does not diagnose disease,
malnutrition, or nutrient deficiency, calculate a clinical diet, or replace a clinician.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import os
from screening_constants import (
    CURRENT_IMPLEMENTED_MAX_AGE_MONTHS,
    DEFAULT_TEXT_MODEL_ID,
    SCREENING_DISCLAIMER,
    SUPPORTED_MIN_AGE_MONTHS,
    TARGET_MAX_AGE_MONTHS,
)

ROOT = Path(__file__).parent
from model_runtime import configured_text_model, select_evidence
MODEL_ID = configured_text_model()
KB = json.loads((ROOT / "data" / "nutrition_knowledge.json").read_text(encoding="utf-8"))

SYSTEM = """You are a communication and caregiver-explanation component of a pediatric nutrition screening platform for children aged 0 to 6 years.
Your role is strictly communication and caregiver guidance; you are NOT a decision-maker and must NEVER calculate, invent, alter, upgrade, or downgrade screening risk.
Answer ONLY from CONTEXT and the provided deterministic screening findings.
Never invent a quantity, diagnosis, disease, treatment, supplement, recipe, or source.
You must not diagnose disease, malnutrition, anaemia, micronutrient deficiency, or medical conditions.
Do not infer a nutritional deficiency solely from reported foods or meal photographs.
Use screening-oriented language (e.g., potential dietary concerns, limited variety, feeding pattern requires review).
When deterministic screening findings are supplied, explain those findings clearly but do not alter, downgrade, override, or invent the screening result.
If the question is outside CONTEXT or evidence is insufficient, state that there is insufficient information to complete screening rather than guessing, and recommend a pediatrician or qualified dietitian.
Distinguish between what was reported by the caregiver, what was observed by AI, and what was determined by deterministic screening rules.
Do not recommend medication or therapeutic supplementation.
Do not generate a Vitamin D risk assessment. Vitamin D-specific screening is currently outside the scope of the module.
Do not claim that an individual meal establishes the child's overall nutritional adequacy.
State red flags if relevant. Use simple, age-appropriate, caregiver-friendly language, bullets, and end with the supplied [Source IDs]."""

def find_band(age_months: int) -> dict:
    if not (SUPPORTED_MIN_AGE_MONTHS <= age_months <= CURRENT_IMPLEMENTED_MAX_AGE_MONTHS):
        raise ValueError(
            f"Age must be between {SUPPORTED_MIN_AGE_MONTHS} and {CURRENT_IMPLEMENTED_MAX_AGE_MONTHS} completed months "
            f"for currently implemented screening bands (target scope: 0 to {TARGET_MAX_AGE_MONTHS} months; "
            f"60 to {TARGET_MAX_AGE_MONTHS} months screening rules planned for Phase 2)."
        )
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
    terms = r"chok|blue|breath|unconscious|unresponsive|floppy|dehydrat|letharg|vomit|allergic|hives|swelling|weight loss|los\w+ weight|fatigue|failure to thrive|premature|preterm"
    if re.search(terms, question, re.I):
        return ("This could need prompt clinical assessment. For breathing trouble, blue color, "
                "unconsciousness, or active choking, seek emergency help now. For other feeding, "
                "allergy, dehydration, or growth concerns, contact a pediatric clinician. "
                "This nutrition screening and educational support module cannot diagnose an individual child or replace clinical evaluation.")
    return None

def explain_screening_findings(
    screening_payload: dict,
    age_months: int,
    use_model: bool = False,
) -> str:
    """Takes deterministic rule engine output and uses the SLM strictly for communication/explanation.

    Architecture:
        Deterministic Rule Engine Output -> SLM -> Caregiver Explanation
        SLM = communication / explanation, NOT decision maker.
    """
    result_category = screening_payload.get("screening_result", "INSUFFICIENT_DATA")
    from screening_constants import SCREENING_CATEGORIES
    if result_category not in SCREENING_CATEGORIES:
        raise ValueError("Unknown screening_result")
    findings = screening_payload.get("findings", [])
    if not isinstance(findings, list) or any(not isinstance(f, str) for f in findings):
        raise ValueError("findings must be a list of strings")
    urgent_flag = screening_payload.get("professional_review_flag", False)

    if urgent_flag:
        return (
            "Screening Finding: PROFESSIONAL_REVIEW_FLAG\n\n"
            "This dietary or feeding pattern includes symptoms or indicators that require prompt clinical review. "
            "Please consult a pediatrician or qualified healthcare professional. "
            f"\n\nScreening Notice: {SCREENING_DISCLAIMER}"
        )

    context = context_for(age_months)
    findings_bullets = "\n".join(f"- {f}" for f in findings) if findings else "- No screening findings were supplied; this does not establish low concern."

    if not use_model:
        explanation_lines = [
            f"Screening Result: {result_category}",
            "\nKey Screening Observations:",
            findings_bullets,
            "\nCaregiver Guidance Summary:",
            f"For a child aged {age_months} months, feeding guidelines emphasize age-appropriate variety, responsive feeding, and regular meal cadence.",
            "- A single meal or photo cannot determine overall nutritional adequacy. Dietary diversity is evaluated across full-day patterns.",
            "- Note: Vitamin D-specific screening is outside the scope of this module.",
            f"\nScreening Notice: {SCREENING_DISCLAIMER}",
        ]
        return "\n".join(explanation_lines)

    # Conclusions and findings remain deterministic even when AI selection fails.
    explanation = explain_screening_findings(screening_payload, age_months, use_model=False)
    evidence = evidence_for(age_months)
    indices, mode = select_evidence("Explain these reported findings: " + "; ".join(findings), evidence)
    if indices:
        explanation += "\n\nRelevant feeding guidance:\n" + "\n".join("- " + evidence[i] for i in indices)
    return explanation


def evidence_for(age_months: int) -> list[str]:
    band = find_band(age_months)
    facts = list(band["core_guidance"]) + list(band["safety"])
    facts += [band["feeding_skills"], band.get("safe_textures", ""), band.get("meal_cadence", ""), band.get("variety_target", "")]
    facts += band.get("foods_to_avoid", [])
    return list(dict.fromkeys(f for f in facts if f))


def grounded_answer(age_months: int, question: str) -> tuple[str, str]:
    urgent = red_flag_gate(question)
    if urgent:
        return urgent, "red_flag_gate"
    facts = evidence_for(age_months)
    indices, mode = select_evidence(question, facts)
    band = find_band(age_months)
    if indices:
        text = "\n".join("- " + facts[i] for i in indices)
    else:
        text = "Model selection is unavailable or could not select a supported answer. Reviewed guidance for this age follows:\n" + context_for(age_months)
    return text + "\n\n" + SCREENING_DISCLAIMER + "\n[Source IDs: " + ", ".join(band["sources"]) + "]", mode


def answer(age_months: int, question: str, use_model: bool = True) -> str:
    urgent = red_flag_gate(question)
    if urgent:
        return urgent

    if age_months < SUPPORTED_MIN_AGE_MONTHS:
        raise ValueError(
            f"Age {age_months} completed months is invalid; age must be between "
            f"{SUPPORTED_MIN_AGE_MONTHS} and {CURRENT_IMPLEMENTED_MAX_AGE_MONTHS} completed months "
            f"(target scope: 0 to {TARGET_MAX_AGE_MONTHS} months)."
        )

    if CURRENT_IMPLEMENTED_MAX_AGE_MONTHS < age_months <= TARGET_MAX_AGE_MONTHS:
        return (
            f"Screening Notice: Age {age_months} completed months (5 to 6 years) is within the platform's "
            f"target scope (0 to {TARGET_MAX_AGE_MONTHS} months). Currently implemented evidence bands cover 0 to "
            f"{CURRENT_IMPLEMENTED_MAX_AGE_MONTHS} completed months; specific school-age screening rules for 60 to 72 months "
            "are scheduled for Phase 2.\n\n"
            "General 5–6 Year Nutrition Guidance:\n"
            "- Dietary variety: Offer foods across family food groups (whole grains, pulses, dairy, eggs, fish/poultry, vegetables, fruits).\n"
            "- Meal cadence: 3 regular meals and 1–2 healthy snacks daily.\n"
            "- Beverages: Prioritize water and plain milk; strictly limit sugar-sweetened drinks and juices.\n"
            f"\nScreening Notice: {SCREENING_DISCLAIMER}\n"
            "[Source IDs: WHO-CF-2023, CDC-FOOD-SAFETY]"
        )

    if age_months > TARGET_MAX_AGE_MONTHS:
        return (
            f"Out of Scope Notice: Age {age_months} completed months exceeds the platform's pediatric target scope "
            f"(0 to {TARGET_MAX_AGE_MONTHS} completed months / birth to 6 completed years). "
            f"\n\nScreening Notice: {SCREENING_DISCLAIMER}"
        )

    context = context_for(age_months)
    if not use_model:
        return context
    return grounded_answer(age_months, question)[0]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Constrained child nutrition SLM demo")
    parser.add_argument("--age-months", required=True, type=int)
    parser.add_argument("--question", required=True)
    parser.add_argument("--context-only", action="store_true", help="Test the curated layer without downloading a model")
    args = parser.parse_args()
    print(answer(args.age_months, args.question, use_model=not args.context_only))
