"""Phase 1 Pediatric Nutrition Screening Boundary & Safety Verification Suite.

Tests that NutriGuide strictly enforces:
1. Product boundary: Screening and educational support, not clinical diagnosis.
2. Language safety: No diagnostic terms ("malnourished", "iron deficient", "vitamin deficient", etc.).
3. Single-meal limitation: A single meal cannot prove overall nutritional adequacy.
4. Model prompt boundaries: System prompt strictly forbids diagnosis, overrides, and Vitamin D scoring.
5. Vitamin D exclusion: Vitamin D screening is strictly excluded from current implementation.
6. Target age scope: 0–72 months target documented; 0–59 months implemented rules verified; >=60 months handled safely.
7. Vision model boundary: Observations are candidate drafts with mandatory confirmation.
"""
from __future__ import annotations

import json
from pathlib import Path

from app import SYSTEM, context_for, find_band, red_flag_gate
from meal_photo_app import _extract_json, guidance_from_confirmed
from nutrition_engine import FOOD_GROUPS, review_meal
from screening_constants import (
    CALORIE_ESTIMATION_ENABLED,
    CURRENT_IMPLEMENTED_MAX_AGE_MONTHS,
    MICRONUTRIENT_DEFICIENCY_PREDICTION_ENABLED,
    MODULE_NAME,
    MODULE_TYPE,
    PROHIBITED_DIAGNOSTIC_TERMS,
    SCREENING_CATEGORIES,
    SCREENING_DISCLAIMER,
    SCREENING_ENGINE_STATUS,
    SUPPORTED_MIN_AGE_MONTHS,
    TARGET_MAX_AGE_MONTHS,
    VITAMIN_D_SCREENING_ENABLED,
)

def test_screening_constants_and_configuration():
    """Verify core scope, flags, and screening categories."""
    assert SUPPORTED_MIN_AGE_MONTHS == 0
    assert TARGET_MAX_AGE_MONTHS == 72
    assert CURRENT_IMPLEMENTED_MAX_AGE_MONTHS == 59
    assert VITAMIN_D_SCREENING_ENABLED is False, "Vitamin D screening must be disabled in Phase 1"
    assert MICRONUTRIENT_DEFICIENCY_PREDICTION_ENABLED is False
    assert CALORIE_ESTIMATION_ENABLED is False
    assert MODULE_TYPE == "nutrition_screening_support"
    assert SCREENING_ENGINE_STATUS == "under_development"
    assert "SCREENING_CONCERN" in "".join(SCREENING_CATEGORIES)
    assert "LOW_SCREENING_CONCERN" in SCREENING_CATEGORIES
    assert "MODERATE_SCREENING_CONCERN" in SCREENING_CATEGORIES
    assert "HIGH_SCREENING_CONCERN" in SCREENING_CATEGORIES
    assert "INSUFFICIENT_DATA" in SCREENING_CATEGORIES
    assert "PROFESSIONAL_REVIEW_FLAG" in SCREENING_CATEGORIES
    assert "does not diagnose" in SCREENING_DISCLAIMER.lower()
    print("  [PASS] Screening constants & scope configuration verified.")

def test_model_system_prompt_boundaries():
    """Verify SLM system prompt forbids diagnosis, Vitamin D scoring, and overriding deterministic rules."""
    prompt_lower = SYSTEM.lower()
    assert "pediatric nutrition screening platform" in prompt_lower
    assert "0 to 6 years" in prompt_lower
    assert "must not diagnose" in prompt_lower
    assert "do not infer a nutritional deficiency" in prompt_lower
    assert "do not alter, downgrade, override, or invent the screening result" in prompt_lower
    assert "insufficient information" in prompt_lower
    assert "vitamin d-specific screening is currently outside the scope" in prompt_lower
    assert "do not claim that an individual meal establishes the child's overall nutritional adequacy" in prompt_lower
    assert "distinguish between what was reported by the caregiver, what was observed by ai, and what was determined by deterministic screening rules" in prompt_lower
    print("  [PASS] SLM system prompt safety & boundaries verified.")

def test_meal_review_language_safety():
    """Verify that meal review output uses screening language and strictly avoids diagnostic statements."""
    common_cases = [
        # (age, foods, groups, textures, prep, allergens, daily_groups)
        (4, "", [], [], [], [], []),
        (7, "rice cereal, pureed pear", ["Grains, roots and tubers", "Other fruits and vegetables"], ["Smooth puree"], ["Cooked/softened"], [], ["Grains, roots and tubers", "Other fruits and vegetables"]),
        (10, "mashed lentils, soft rice", ["Grains, roots and tubers", "Pulses, nuts and seeds"], ["Mashed"], ["Cooked/softened"], [], ["Breast milk", "Grains, roots and tubers"]),
        (14, "cooked carrot, oatmeal, boiled egg", ["Grains, roots and tubers", "Eggs", "Vitamin-A-rich fruits and vegetables"], ["Lumpy/soft pieces"], ["Cooked/softened"], ["Egg"], ["Grains, roots and tubers", "Eggs", "Vitamin-A-rich fruits and vegetables", "Dairy", "Pulses, nuts and seeds"]),
        (36, "vegetable pasta, chicken pieces", ["Grains, roots and tubers", "Flesh foods", "Other fruits and vegetables"], ["Safe finger food"], ["Cooked/softened", "Peeled or pits/bones removed"], [], ["Grains, roots and tubers", "Flesh foods", "Other fruits and vegetables", "Dairy"]),
    ]

    for age, foods, groups, tex, prep, alg, daily in common_cases:
        output = review_meal(age, foods, groups, tex, prep, alg, daily).lower()

        # Check prohibited diagnostic terms
        for bad_term in PROHIBITED_DIAGNOSTIC_TERMS:
            assert bad_term not in output, f"Prohibited diagnostic term '{bad_term}' found in review_meal output for age {age}"

        # Check screening notice presence
        assert "screening notice:" in output or "screening" in output

    print(f"  [PASS] Verified language safety across {len(common_cases)} meal review configurations.")

def test_single_meal_adequacy_rejection():
    """Verify the engine explicitly refuses to treat a single meal as proof of overall nutritional adequacy."""
    output = review_meal(
        12,
        foods="lentil soup, bread",
        groups=["Grains, roots and tubers", "Pulses, nuts and seeds"],
        textures=["Mashed"],
        preparation=["Cooked/softened"],
        allergens=[],
        daily_groups=["Grains, roots and tubers", "Pulses, nuts and seeds"],
    )
    assert "single photo or meal cannot determine overall nutritional adequacy" in output or "single photo or meal cannot show dietary adequacy" in output
    assert "day-level reflection" in output
    print("  [PASS] Single meal adequacy limitation affirmed.")

def test_vitamin_d_strict_exclusion():
    """Verify Vitamin D screening is not generated or calculated."""
    assert VITAMIN_D_SCREENING_ENABLED is False

    # Check meal review output does not score or screen Vitamin D
    output = review_meal(
        18,
        foods="yogurt, fortified cereal",
        groups=["Dairy", "Grains, roots and tubers"],
        textures=["Smooth puree"],
        preparation=["Pasteurized"],
        allergens=["Dairy"],
        daily_groups=["Dairy", "Grains, roots and tubers"],
    ).lower()

    assert "vitamin d concern" not in output
    assert "vitamin d score" not in output
    assert "vitamin d risk" not in output
    assert "vitamin d deficiency" not in output
    print("  [PASS] Vitamin D screening exclusion verified.")

def test_vision_model_output_boundary():
    """Verify VLM draft output requires confirmation and does not emit diagnostic categories."""
    draft_valid = _extract_json('{"visible_foods": ["lentils", "rice"], "texture_cues": ["mashed"], "uncertain": false, "child_present": false}')
    assert draft_valid["requires_confirmation"] is True
    assert draft_valid["candidate_foods"] == ["lentils", "rice"]
    assert "mashed" in draft_valid["observations"]
    assert draft_valid["child_present"] is False

    draft_invalid = _extract_json('not json at all')
    assert draft_invalid["uncertain"] is True
    assert draft_invalid["requires_confirmation"] is True
    assert draft_invalid["visible_foods"] == []

    # Verify confirmation requirement in guidance_from_confirmed
    unconfirmed = guidance_from_confirmed(12, "rice", ["Grains, roots and tubers"], ["Mashed"], ["Cooked/softened"], [], ["Grains, roots and tubers"], False)
    assert "confirm" in unconfirmed.lower()

    print("  [PASS] Vision model boundary & mandatory confirmation verified.")

def test_age_range_boundaries():
    """Verify 0-59 months is supported and >=60 months produces clear, safe guidance."""
    # Valid implemented ages
    for age in [0, 5, 6, 8, 9, 11, 12, 23, 24, 59]:
        band = find_band(age)
        assert band is not None

    # Invalid age rejection with clear target scope documentation
    for bad_age in [-1, 60, 72, 80]:
        try:
            find_band(bad_age)
            raise AssertionError(f"Expected ValueError for age {bad_age}")
        except ValueError as exc:
            msg = str(exc)
            assert "0 to 72 months" in msg or "0 and 59" in msg

    print("  [PASS] Age range boundaries (0-59m implemented, 0-72m target scope) verified.")

def test_slm_communication_role():
    """Verify that SLM strictly acts as communicator/explainer and NOT decision maker."""
    from app import explain_screening_findings
    from screening_constants import (
        DECISION_MAKER,
        PROHIBITED_DIAGNOSTIC_TERMS,
        SLM_ROLE,
    )

    # 1. Structural architectural assertions
    assert SLM_ROLE == "communication_and_explanation"
    assert DECISION_MAKER == "deterministic_rule_engine"

    # 2. Test explain_screening_findings preserves deterministic result category
    payload = {
        "screening_result": "MODERATE_SCREENING_CONCERN",
        "findings": [
            "Limited dietary diversity: only 2 of 5 recommended food groups reported today.",
            "High-sodium processed snack observed.",
        ],
        "professional_review_flag": False,
    }
    explanation = explain_screening_findings(payload, age_months=14, use_model=False)

    # Must preserve exact deterministic category and findings
    assert "MODERATE_SCREENING_CONCERN" in explanation
    assert "Limited dietary diversity" in explanation
    assert "High-sodium processed snack observed" in explanation

    # Must not contain diagnostic claims
    explanation_lower = explanation.lower()
    for bad_term in PROHIBITED_DIAGNOSTIC_TERMS:
        assert bad_term not in explanation_lower, f"Prohibited term '{bad_term}' found in SLM explanation"

    # Must state single-meal limitation and vitamin D exclusion
    assert "single meal" in explanation_lower
    assert "vitamin d" in explanation_lower

    # 3. Test professional review flag payload
    urgent_payload = {
        "screening_result": "PROFESSIONAL_REVIEW_FLAG",
        "findings": ["Severe lethargy", "Active choking history"],
        "professional_review_flag": True,
    }
    urgent_explanation = explain_screening_findings(urgent_payload, age_months=8, use_model=False)
    assert "PROFESSIONAL_REVIEW_FLAG" in urgent_explanation
    assert "pediatrician" in urgent_explanation.lower() or "healthcare professional" in urgent_explanation.lower()

    print("  [PASS] SLM communication role (non-decision-maker) verified.")

if __name__ == "__main__":
    print("\n--- Running Phase 1 Screening Safety & Boundary Verification Suite ---")
    test_screening_constants_and_configuration()
    test_model_system_prompt_boundaries()
    test_slm_communication_role()
    test_meal_review_language_safety()
    test_single_meal_adequacy_rejection()
    test_vitamin_d_strict_exclusion()
    test_vision_model_output_boundary()
    test_age_range_boundaries()
    print("--- ALL PHASE 1 SCREENING SAFETY CHECKS PASSED SUCCESSFULLY ---\n")

