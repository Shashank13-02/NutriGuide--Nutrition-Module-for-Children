"""Centralized screening constants, safety boundaries, and terminology for NutriGuide.

Defines the product boundary for the Child Nutrition Screening Platform (0 to 6 years / 0 to 72 months).
Phase 1 establishes the product boundary, terminology, and safety rules without implementing
clinical diagnosis, arbitrary scoring, or Vitamin D screening.
"""
from __future__ import annotations

# Scope & Age Boundaries
SUPPORTED_MIN_AGE_MONTHS: int = 0
TARGET_MAX_AGE_MONTHS: int = 72  # 0–6 completed years target scope
CURRENT_IMPLEMENTED_MAX_AGE_MONTHS: int = 59  # 60–72 month screening rules planned for Phase 2

MODULE_NAME: str = "Child Nutrition Screening Module"
MODULE_TYPE: str = "nutrition_screening_support"
SCREENING_ENGINE_STATUS: str = "iycf_indicators_implemented_6_to_23_months"

# Mandatory Safety & Screening Disclaimers
SCREENING_DISCLAIMER: str = (
    "This module supports nutrition screening and education. "
    "It does not diagnose malnutrition, nutrient deficiency, or disease."
)

SCREENING_NOTICE: str = SCREENING_DISCLAIMER

SCREENING_POLICY_SUMMARY: str = (
    "The Nutrition Screening Module assesses whether a child's recent dietary intake pattern "
    "shows potential nutritional concerns based on age-appropriate feeding practices, dietary "
    "diversity, meal patterns, food-group exposure, and other screening indicators. It is "
    "intended to support early identification of dietary patterns that may require attention. "
    "It does not diagnose malnutrition, nutrient deficiency, disease, or any medical condition."
)

# Vitamin Screening Scope Flags
# IMPORTANT: Vitamin D-specific screening is intentionally excluded from the current implementation.
VITAMIN_D_SCREENING_ENABLED: bool = False
MICRONUTRIENT_DEFICIENCY_PREDICTION_ENABLED: bool = False
CALORIE_ESTIMATION_ENABLED: bool = False

# Model Architecture Constants & Roles
# Strict architecture rule: SLM = communication / explanation, NOT decision maker
SLM_ROLE: str = "communication_and_explanation"
DECISION_MAKER: str = "deterministic_rule_engine"

# Model Registry (Qwen3-1.7B selected as primary text communication SLM)
DEFAULT_TEXT_MODEL_ID: str = "Qwen/Qwen3-1.7B"
FALLBACK_TEXT_MODEL_ID: str = "HuggingFaceTB/SmolLM2-360M-Instruct"
BENCHMARK_CANDIDATE_TEXT_MODEL_ID: str = DEFAULT_TEXT_MODEL_ID

DEFAULT_VISION_MODEL_ID: str = "HuggingFaceTB/SmolVLM-500M-Instruct"
BENCHMARK_CANDIDATE_VISION_MODELS = (
    "Qwen/Qwen2-VL-2B-Instruct",
    "Qwen/Qwen3-VL-2B-Instruct",
    "Qwen/Qwen2.5-VL-3B-Instruct",
)

# Planned Standardized Screening Terminology (Phase 1 Taxonomy)
SCREENING_CATEGORIES = (
    "INDICATORS_MET",
    "FEEDING_PATTERN_REVIEW",
    "LOW_SCREENING_CONCERN",
    "MODERATE_SCREENING_CONCERN",
    "HIGH_SCREENING_CONCERN",
    "INSUFFICIENT_DATA",
    "PROFESSIONAL_REVIEW_FLAG",
)

# Screening Finding Language (Non-diagnostic, screening-oriented phrases)
SCREENING_FINDINGS = {
    "LOW_CONCERN": "Low nutrition intake concern based on reported dietary pattern.",
    "MODERATE_CONCERN": "Moderate nutrition intake concern; dietary pattern may benefit from review.",
    "HIGH_CONCERN": "High nutrition intake concern; feeding pattern requires prompt review.",
    "INSUFFICIENT_DATA": "Insufficient information to complete dietary intake screening.",
    "LIMITED_IRON_RICH": "The reported diet contains limited iron-rich foods.",
    "LIMITED_PROTEIN_RICH": "The reported diet shows limited protein-rich food exposure.",
    "LIMITED_VARIETY": "The reported dietary intake appears to have limited food-group variety.",
    "MEAL_PATTERN_ATTENTION": "Meal pattern or feeding cadence may require attention.",
    "PROFESSIONAL_REVIEW": "Professional clinical review recommended for identified feeding or growth concern.",
}

# Diagnostic Terms Prohibited in AI / Model Screening Explanations
PROHIBITED_DIAGNOSTIC_TERMS = (
    "malnourished",
    "child is malnourished",
    "severe malnutrition",
    "iron deficient",
    "iron deficiency anemia",
    "vitamin deficient",
    "vitamin d deficient",
    "anaemic",
    "anemic",
    "protein deficient",
    "calcium deficient",
    "micronutrient deficient",
    "has a nutritional disorder",
    "has a disease",
    "diagnosed with",
    "suffers from",
    "clinically healthy",
    "clinically unhealthy",
)

# Critical Age Boundaries to Test Aggressively
AGE_BOUNDARY_PAIRS = (
    (5, 6),    # Exclusive milk vs early complementary start
    (8, 9),    # 2-3 meals (smooth/mashed) vs 3-4 meals (finger foods/lumps)
    (11, 12),  # Honey strictly forbidden & milk drink caution vs honey safe & whole milk drink allowed
    (23, 24),  # Zero added sugar strict rule & whole milk vs family diet & low-fat milk transition
    (35, 36),  # Late toddler chewing/choking risk vs 3-year preschooler mealtime milestone
    (59, 60),  # Upper bound of Phase 1 implemented rules vs School-age Phase 2 deferred scope
    (71, 72),  # Platform target scope boundary (5y 11m vs 6y 0m completed months)
)

def classify_age_scope(age_months: int) -> dict:
    """Classifies age in completed months across product scope and developmental stages.

    Target product scope: 0 to 72 completed months (0 to 6 years).
    Current implemented rule scope: 0 to 59 completed months.
    Phase 2 deferred rule scope: 60 to 72 completed months.
    """
    if age_months < SUPPORTED_MIN_AGE_MONTHS:
        return {
            "age_months": age_months,
            "status": "invalid_negative",
            "in_target_scope": False,
            "implemented_in_phase1": False,
            "stage_id": "invalid",
            "stage_name": "Invalid Negative Age",
            "message": f"Age {age_months}m is invalid; age cannot be negative.",
        }
    if age_months <= 5:
        return {
            "age_months": age_months,
            "status": "supported_implemented",
            "in_target_scope": True,
            "implemented_in_phase1": True,
            "stage_id": "0_5_months",
            "stage_name": "Infant Milk Feeding (0–5 months)",
            "message": "Exclusive milk feeding (breast milk or infant formula); no solids, no water.",
        }
    if age_months <= 8:
        return {
            "age_months": age_months,
            "status": "supported_implemented",
            "in_target_scope": True,
            "implemented_in_phase1": True,
            "stage_id": "6_8_months",
            "stage_name": "Early Complementary Feeding (6–8 months)",
            "message": "Introduction of smooth/mashed complementary foods, 2–3 meals/day, continue milk feeds.",
        }
    if age_months <= 11:
        return {
            "age_months": age_months,
            "status": "supported_implemented",
            "in_target_scope": True,
            "implemented_in_phase1": True,
            "stage_id": "9_11_months",
            "stage_name": "Late Complementary Feeding (9–11 months)",
            "message": "Finger foods and lumpy textures, 3–4 meals/day + 1–2 snacks, NO honey (<12m).",
        }
    if age_months <= 23:
        return {
            "age_months": age_months,
            "status": "supported_implemented",
            "in_target_scope": True,
            "implemented_in_phase1": True,
            "stage_id": "12_23_months",
            "stage_name": "Toddler Family Foods Transition (12–23 months)",
            "message": "Family foods adapted for chewing, whole cow's milk allowed, honey safe, ZERO added sugars (<24m).",
        }
    if age_months <= 35:
        return {
            "age_months": age_months,
            "status": "supported_implemented",
            "in_target_scope": True,
            "implemented_in_phase1": True,
            "stage_id": "24_35_months",
            "stage_name": "Early Childhood Toddler (24–35 months)",
            "message": "Family meals (3 meals + 2 snacks), transition to low-fat milk possible, high choking risk on whole nuts/hard items.",
        }
    if age_months <= 59:
        return {
            "age_months": age_months,
            "status": "supported_implemented",
            "in_target_scope": True,
            "implemented_in_phase1": True,
            "stage_id": "36_59_months",
            "stage_name": "Preschool Child (36–59 months)",
            "message": "Preschool family diet, chewing maturation, active eating, supervised meals.",
        }
    if age_months <= TARGET_MAX_AGE_MONTHS:
        return {
            "age_months": age_months,
            "status": "supported_deferred_phase2",
            "in_target_scope": True,
            "implemented_in_phase1": False,
            "stage_id": "60_72_months",
            "stage_name": "School-Age Transition (60–72 months)",
            "message": (
                f"Age {age_months}m is within the 0–72 months target scope (0–6 years), "
                "but specific deterministic screening rules for 60–72 months are scheduled for Phase 2."
            ),
        }
    return {
        "age_months": age_months,
        "status": "out_of_scope_overage",
        "in_target_scope": False,
        "implemented_in_phase1": False,
        "stage_id": "out_of_scope",
        "stage_name": "Out of Scope (>72 months / >6 years)",
        "message": f"Age {age_months}m exceeds the maximum target scope of 72 completed months (6 years).",
    }

