from nutrition_engine import FOOD_GROUPS, review_meal

common = dict(foods="soft rice, lentils, cooked carrot", groups=["Grains, roots and tubers", "Pulses, nuts and seeds", "Other fruits and vegetables"], textures=["Mashed", "Lumpy/soft pieces"], preparation=["Cooked/softened", "Mashed/pureed"], allergens=[], daily_groups=["Breast milk", "Grains, roots and tubers", "Pulses, nuts and seeds", "Other fruits and vegetables", "Eggs"])

assert "milk feeding" in review_meal(4, **common).lower()
assert "2–3 meals" in review_meal(7, **common)
assert "3–4 meals" in review_meal(10, **common)
assert "5 of 8 groups" in review_meal(18, **common)
assert "varied family diet" in review_meal(36, **common).lower()
assert "Allergen note" in review_meal(12, **(common | {"allergens": ["Egg"]}))
try:
    review_meal(12, **(common | {"groups": ["invented group"]}))
    raise AssertionError("Unknown food group was accepted")
except ValueError:
    pass
assert len(FOOD_GROUPS) == 8
print("Passed 8 educational-framework checks.")
