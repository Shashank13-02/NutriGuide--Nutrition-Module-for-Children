"""Transparent, non-diagnostic rules for the child nutrition screening and meal review module.

All food and food-group data used here must be caregiver-confirmed. Image-model output is never
treated as a confirmed fact. This code deliberately does not diagnose malnutrition, micronutrient
deficiencies, or disease, calculate calories, portions, or nutrients, or assess clinical growth status.
"""
from __future__ import annotations

from dataclasses import dataclass

from app import KB, find_band
from screening_constants import (
    CURRENT_IMPLEMENTED_MAX_AGE_MONTHS,
    SCREENING_DISCLAIMER,
    SUPPORTED_MIN_AGE_MONTHS,
    TARGET_MAX_AGE_MONTHS,
)

FOOD_GROUPS = (
    "Breast milk",
    "Grains, roots and tubers",
    "Pulses, nuts and seeds",
    "Dairy",
    "Flesh foods",
    "Eggs",
    "Vitamin-A-rich fruits and vegetables",
    "Other fruits and vegetables",
)

ALLERGEN_FLAGS = ("Egg", "Dairy", "Peanut/tree nut", "Wheat", "Soy", "Fish/shellfish")
TEXTURES = ("Smooth puree", "Mashed", "Lumpy/soft pieces", "Safe finger food", "Family-food texture", "Mixed/unclear")
PREPARATION_FLAGS = (
    "Cooked/softened", "Mashed/pureed", "Peeled or pits/bones removed",
    "Round foods cut lengthwise/quartered", "Nut butter thinly spread",
    "Pasteurized", "No honey (<12 months)", "No added sugar",
)

AGE_DESIGN = {
    "0_5_months": {
        "stage": "Milk feeding",
        "image_use": "No meal-photo analysis. This module provides nutrition intake screening and educational support; milk-feeding questions need clinician support when there are concerns.",
        "texture": "Not applicable: complementary-food texture is not assessed in this band.",
        "focus": "Exclusive breastfeeding guidance where applicable; no food or water is needed for exclusively breastfed infants in the first 6 months.",
    },
    "6_8_months": {
        "stage": "Starting complementary foods",
        "image_use": "Meal photos may be used only for caregiver-confirmed candidate food and texture review.",
        "texture": "Start smooth/mashed foods and progress only with the child's observed feeding skills.",
        "focus": "Small amounts, variety including iron-rich foods, and 2–3 meals daily while breastfeeding continues where applicable.",
    },
    "9_11_months": {
        "stage": "Building texture and self-feeding skills",
        "image_use": "Meal photos may support caregiver review of confirmed foods, textures, and safe preparation.",
        "texture": "Progress to thicker/lumpier foods and appropriately prepared soft pieces/finger foods as skills develop.",
        "focus": "Variety, responsive feeding, 3–4 meals daily, and safe texture progression.",
    },
    "12_23_months": {
        "stage": "Family foods adapted for the child",
        "image_use": "Meal photos may support caregiver review of confirmed foods, textures, and safe preparation.",
        "texture": "Adapt family foods for chewing ability and choking safety; encourage self-feeding without force.",
        "focus": "Variety over the day, 3–4 meals daily and 1–2 nutritious snacks as needed.",
    },
    "24_59_months": {
        "stage": "Early-childhood family eating",
        "image_use": "Meal photos may support dietary-pattern screening and safe-preparation education, not clinical nutrient or growth diagnosis.",
        "texture": "Use developmentally appropriate family-food textures and supervise meals.",
        "focus": "A varied family diet, responsive feeding, regular meals/snacks, and professional growth monitoring when needed.",
    },
}

def age_key(age_months: int) -> str:
    find_band(age_months)  # validates input
    if age_months <= 5: return "0_5_months"
    if age_months <= 8: return "6_8_months"
    if age_months <= 11: return "9_11_months"
    if age_months <= 23: return "12_23_months"
    return "24_59_months"

def validate_selection(selected: list[str], allowed: tuple[str, ...], label: str) -> list[str]:
    unknown = sorted(set(selected) - set(allowed))
    if unknown:
        raise ValueError(f"Unknown {label}: {', '.join(unknown)}")
    return list(dict.fromkeys(selected))

def review_meal(age_months: int, foods: str, groups: list[str], textures: list[str], preparation: list[str], allergens: list[str], daily_groups: list[str]) -> str:
    age_int = int(age_months)
    if CURRENT_IMPLEMENTED_MAX_AGE_MONTHS < age_int <= TARGET_MAX_AGE_MONTHS:
        groups = validate_selection(groups, FOOD_GROUPS, "food group")
        daily_groups = validate_selection(daily_groups, FOOD_GROUPS, "daily food group")
        textures = validate_selection(textures, TEXTURES, "texture")
        preparation = validate_selection(preparation, PREPARATION_FLAGS, "preparation flag")
        allergens = validate_selection(allergens, ALLERGEN_FLAGS, "allergen flag")
        return "\n".join([
            f"Age stage: School-age transition (60 to 72 months / 5 to 6 years).",
            f"Scope notice: Age {age_int} months is within the 0 to {TARGET_MAX_AGE_MONTHS} months target platform scope; specific school-age screening rules are scheduled for Phase 2.",
            "Caregiver-confirmed meal record (not a model conclusion):",
            f"- Foods described: {foods.strip() or 'Not recorded'}",
            f"- Food groups in this meal: {', '.join(groups) or 'Not recorded'}",
            f"- Textures: {', '.join(textures) or 'Not recorded'}",
            f"- Preparation steps: {', '.join(preparation) or 'Not recorded'}",
            f"- Potential allergens present: {', '.join(allergens) or 'None selected / not recorded'}",
            "\nScreening & educational interpretation:",
            "- General 5–6 year guidance: Support dietary variety across family meals, encourage independent eating, prioritize whole foods, and ensure regular meal cadence.",
            "- A single photo or meal cannot determine overall nutritional adequacy. Dietary diversity is a day-level reflection, not a single meal score.",
            f"- Caregiver-reported food groups across the day: {', '.join(daily_groups) or 'Not recorded'} ({len(daily_groups)} of 8 categories selected).",
            f"Screening notice: {SCREENING_DISCLAIMER}",
            "[Source IDs: WHO-CF-2023, CDC-FOOD-SAFETY]",
        ])

    key = age_key(age_int)
    band = find_band(age_int)
    design = AGE_DESIGN[key]
    groups = validate_selection(groups, FOOD_GROUPS, "food group")
    daily_groups = validate_selection(daily_groups, FOOD_GROUPS, "daily food group")
    textures = validate_selection(textures, TEXTURES, "texture")
    preparation = validate_selection(preparation, PREPARATION_FLAGS, "preparation flag")
    allergens = validate_selection(allergens, ALLERGEN_FLAGS, "allergen flag")

    if key == "0_5_months":
        return "\n".join([
            "Age stage: Birth to 5 months — milk feeding.", design["image_use"],
            design["focus"],
            "This module cannot diagnose nutritional status or deficiency, or assess breastfeeding, formula preparation, intake, hydration, or growth from a photo.",
            f"Screening notice: {SCREENING_DISCLAIMER}",
            "[Source IDs: WHO-IYCF, WHO-BF, CDC-SOLIDS]",
        ])

    lines = [
        f"Age stage: {design['stage']} ({band['label']})",
        "Caregiver-confirmed meal record (not a model conclusion):",
        f"- Foods described: {foods.strip() or 'Not recorded'}",
        f"- Food groups in this meal: {', '.join(groups) or 'Not recorded'}",
        f"- Textures: {', '.join(textures) or 'Not recorded'}",
        f"- Preparation steps: {', '.join(preparation) or 'Not recorded'}",
        f"- Potential allergens present: {', '.join(allergens) or 'None selected / not recorded'}",
        "\nScreening & educational interpretation:",
        f"- {design['focus']}", f"- Texture principle: {design['texture']}",
        "- A single photo or meal cannot determine overall nutritional adequacy. Dietary diversity is a day-level reflection, not a single meal score.",
        f"- Caregiver-reported food groups across the day: {', '.join(daily_groups) or 'Not recorded'} ({len(daily_groups)} of 8 categories selected).",
    ]
    if age_months <= 23:
        lines.append("- For 6–23 months, the UNICEF indicator defines minimum dietary diversity as foods from at least 5 of 8 groups during the previous day; it is a population screening indicator and not a clinical diagnosis or meal-by-meal prescription.")
    if allergens:
        lines.append("- Allergen note: this screening tool cannot determine whether a food is clinically safe for this child. For severe eczema, prior reaction, diagnosed allergy, or concern about introduction, consult a clinician.")
    lines.extend([
        "\nSafety review prompts:",
        "- Confirm the child is seated upright and continuously supervised while eating.",
        "- Check food shape, size, texture, and preparation for choking risk; the screening tool cannot verify safety from an image.",
        "- Use pasteurized foods and safe food handling; avoid raw/undercooked animal foods and unwashed produce.",
        "- Honey is not for children younger than 12 months; avoid added sugars for infants and young children.",
        f"\nScreening notice: {SCREENING_DISCLAIMER}",
        "Seek prompt clinical advice for feeding pain, swallowing difficulty, poor growth, dehydration, persistent vomiting, suspected allergy reaction, or a special medical diet. For choking, breathing trouble, blue color, or unresponsiveness, seek emergency help.",
        f"[Source IDs: {', '.join(band['sources'])}, UNICEF-DIET, CDC-CHOKING, CDC-FOOD-SAFETY]",
    ])
    return "\n".join(lines)
