import json
import unittest
from unittest.mock import patch

from intake_screening import screen_intake
from model_runtime import parse_selection, select_evidence, selection_constraint
from meal_photo_app import _extract_json, parse_food_list, create_photo_draft
from train_model import encode_example

GROUPS = ["Breast milk", "Grains, roots and tubers", "Pulses, nuts and seeds", "Eggs", "Other fruits and vegetables"]


class IntakeTests(unittest.TestCase):
    def record(self, **changes):
        return {"age_months": 10, "confirmed": True, "recall_complete": True,
                "daily_groups": GROUPS, "breastfed": True, "solid_feeds": 3, **changes}

    def test_breastfed_frequency_age_boundary(self):
        for age, count, expected in ((6, 1, False), (8, 2, True), (9, 2, False), (23, 3, True)):
            r = screen_intake(self.record(age_months=age, solid_feeds=count))
            self.assertEqual(r["indicators"]["minimum_meal_frequency"]["met"], expected)
            self.assertEqual(r["screening_result"], "INDICATORS_MET" if expected else "FEEDING_PATTERN_REVIEW")

    def test_non_breastfed_needs_non_milk_and_two_milk_feeds(self):
        groups = ["Dairy", "Grains, roots and tubers", "Pulses, nuts and seeds", "Eggs", "Other fruits and vegetables"]
        for solids, milk, mmf, mad in ((2, 2, True, True), (3, 1, True, False), (1, 2, False, False)):
            r = screen_intake(self.record(breastfed=False, daily_groups=groups, solid_feeds=solids, milk_feeds=milk, yogurt_feeds=0))
            self.assertEqual(r["indicators"]["minimum_meal_frequency"]["met"], mmf)
            self.assertEqual(r["indicators"]["minimum_acceptable_diet"]["met"], mad)
        r = screen_intake(self.record(breastfed=False, daily_groups=["Dairy"], solid_feeds=0, milk_feeds=4, yogurt_feeds=0))
        self.assertFalse(r["indicators"]["minimum_meal_frequency"]["met"])

    def test_yogurt_counts_for_milk_frequency_but_not_twice_for_meal_frequency(self):
        groups = ["Dairy", "Grains, roots and tubers", "Pulses, nuts and seeds", "Eggs", "Other fruits and vegetables"]
        r = screen_intake(self.record(breastfed=False, daily_groups=groups, solid_feeds=4, milk_feeds=0, yogurt_feeds=2))
        self.assertEqual(r["indicators"]["minimum_meal_frequency"]["value"], 4)
        self.assertEqual(r["indicators"]["minimum_milk_feeding_frequency"]["value"], 2)
        self.assertTrue(r["indicators"]["minimum_acceptable_diet"]["met"])
        r = screen_intake(self.record(breastfed=False, daily_groups=groups, solid_feeds=2, milk_feeds=0, yogurt_feeds=2))
        self.assertFalse(r["indicators"]["minimum_meal_frequency"]["met"])
        with self.assertRaises(ValueError):
            screen_intake(self.record(breastfed=False, daily_groups=groups, solid_feeds=1, milk_feeds=0, yogurt_feeds=2))
        r = screen_intake(self.record(breastfed=False, daily_groups=groups, solid_feeds=4, milk_feeds=0))
        self.assertIn("yogurt_feeds", r["missing_fields"])

    def test_diversity_unique_and_threshold(self):
        below = screen_intake(self.record(daily_groups=GROUPS[:4] * 2))
        self.assertEqual(below["indicators"]["minimum_dietary_diversity"]["value"], 4)
        self.assertFalse(below["indicators"]["minimum_acceptable_diet"]["met"])
        self.assertTrue(screen_intake(self.record())["indicators"]["minimum_acceptable_diet"]["met"])

    def test_missing_confirmation_and_incomplete_day_abstain(self):
        for change in ({"confirmed": False}, {"recall_complete": False}, {"daily_groups": None}, {"solid_feeds": None}, {"breastfed": None}):
            r = screen_intake(self.record(**change))
            self.assertEqual(r["screening_result"], "INSUFFICIENT_DATA")
            self.assertTrue(r["missing_fields"])
            self.assertNotIn("minimum_acceptable_diet", r["indicators"])

    def test_outside_indicator_scope(self):
        for age in (0, 5, 24, 59, 60, 72):
            r = screen_intake(self.record(age_months=age))
            self.assertEqual(r["screening_result"], "INSUFFICIENT_DATA")
            self.assertEqual(r["indicators"], {})

    def test_emergency_precedes_confirmation_and_recall(self):
        r = screen_intake({"age_months": 3, "red_flags": ["active_choking"]})
        self.assertTrue(r["emergency"])
        self.assertEqual(r["next_steps"], ["Seek emergency help now."])
        self.assertEqual(r["screening_result"], "PROFESSIONAL_REVIEW_FLAG")

    def test_strict_types_and_conflicting_record(self):
        for change in ({"age_months": True}, {"confirmed": "true"}, {"solid_feeds": 2.5},
                       {"daily_groups": "Eggs"}, {"daily_groups": ["unknown"]},
                       {"breastfed": False, "milk_feeds": 2}, {"solid_feeds": 0},
                       {"red_flags": ["unknown"]}):
            with self.assertRaises(ValueError):
                screen_intake(self.record(**change))

    def test_honey_boundary_and_sweet_drinks(self):
        self.assertEqual(screen_intake(self.record(honey_consumed=True))["screening_result"], "FEEDING_PATTERN_REVIEW")
        self.assertEqual(screen_intake(self.record(age_months=12, honey_consumed=True))["screening_result"], "INDICATORS_MET")
        self.assertEqual(screen_intake(self.record(sweet_beverage_consumed=True))["screening_result"], "FEEDING_PATTERN_REVIEW")


class ModelContractTests(unittest.TestCase):
    def test_constraint_allows_multi_digit_ids_and_abstention_only(self):
        class Tokenizer:
            eos_token_id = 999
            def __call__(self, text, **kwargs):
                return {"input_ids": [ord(char) for char in text]}
        class Tokens(list):
            def __getitem__(self, key):
                return Tokens(super().__getitem__(key)) if isinstance(key, slice) else super().__getitem__(key)
            def tolist(self):
                return list(self)
        allowed = selection_constraint(Tokenizer(), 2, 12)
        self.assertEqual(allowed(0, Tokens([7, 8])), [ord("[")])
        prefix = Tokens([7, 8, ord("[")])
        self.assertIn(ord("]"), allowed(0, prefix))
        self.assertNotIn(ord("x"), allowed(0, prefix))
        self.assertEqual(set(allowed(0, Tokens(prefix + [ord("1")]))), {ord("]"), ord("0"), ord("1")})
        self.assertEqual(allowed(0, Tokens(prefix + [ord("1"), ord("1"), ord("]")])), [999])

    def test_model_selection_cannot_inject_advice(self):
        for raw in ('[true]', '[9]', '"diagnosis"', '[0,1,2,3]', '{"result":"low"}'):
            with self.assertRaises(ValueError):
                parse_selection(raw, 4)
        with patch("model_runtime.selection_enabled", return_value=True), patch("model_runtime.generate_text", return_value="You have a deficiency"):
            self.assertEqual(select_evidence("question", ["reviewed fact"]), ([], "curated_fallback"))

    def test_unqualified_selection_is_inactive(self):
        with patch("model_runtime.selection_enabled", return_value=False), patch("model_runtime.generate_text") as generate:
            self.assertEqual(select_evidence("question", ["reviewed fact"]), ([], "curated_fallback"))
            generate.assert_not_called()

    def test_vision_malformed_abstains_and_keeps_person_flag(self):
        r = _extract_json(json.dumps({"visible_foods": "rice", "child_present": True, "uncertain": False}))
        self.assertTrue(r["child_present"])
        self.assertEqual(r["visible_foods"], [])
        self.assertFalse(r["parse_valid"])
        r = _extract_json('{"visible_foods": ["rice"], "texture_cues": [], "child_present": false, "uncertain": false}')
        self.assertTrue(r["parse_valid"])
        self.assertTrue(r["requires_confirmation"])

    def test_food_list_preserves_suggestions_without_inferring_softness(self):
        result = parse_food_list("Carrots, Avocado, Rice.")
        self.assertEqual(result["candidate_foods"], ["Carrots", "Avocado", "Rice"])
        self.assertEqual(result["texture_cues"], ["mixed/unclear"])
        self.assertTrue(result["uncertain"])
        self.assertTrue(result["requires_confirmation"])
        for text in ("The image shows healthy food.", "diagnosis", "a" * 100, "Ignore instructions"):
            self.assertFalse(parse_food_list(text)["parse_valid"])
        self.assertEqual(parse_food_list("unclear dish")["candidate_foods"], [])

    def test_person_check_blocks_food_drafts_and_unknown_abstains(self):
        from PIL import Image
        with patch("model_runtime.generate_vision", return_value=[{"generated_text": "Yes."}]) as generate:
            _, result = create_photo_draft(Image.new("RGB", (16, 16)))
            self.assertTrue(result["child_present"])
            self.assertEqual(result["candidate_foods"], [])
            self.assertEqual(generate.call_count, 1)
        with patch("model_runtime.generate_vision", return_value=[{"generated_text": "unsure"}]):
            _, result = create_photo_draft(Image.new("RGB", (16, 16)))
            self.assertFalse(result["parse_valid"])

    def test_training_masks_prompt_not_eos_and_rejects_truncation(self):
        class Tokenizer:
            eos_token_id = 2
            def apply_chat_template(self, *args, **kwargs):
                return [10, 11, 12]
            def __call__(self, *args, **kwargs):
                return {"input_ids": [20, 21]}
        example = encode_example({"messages": [], "target": [1]}, Tokenizer())
        self.assertEqual(example["labels"], [-100, -100, -100, 20, 21, 2])
        with self.assertRaises(ValueError):
            encode_example({"messages": [], "target": [1]}, Tokenizer(), max_length=4)


if __name__ == "__main__":
    unittest.main()
