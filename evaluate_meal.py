from meal_photo_app import _extract_json, guidance_from_confirmed

assert _extract_json('{"visible_foods":["rice"],"texture_cues":["mashed"],"uncertain":false,"child_present":false}')["visible_foods"] == ["rice"]
assert _extract_json("not JSON")["uncertain"] is True
args = (12, "rice, lentils", ["Grains, roots and tubers", "Pulses, nuts and seeds"], ["Mashed"], ["Cooked/softened"], [], ["Grains, roots and tubers", "Pulses, nuts and seeds"])
assert "confirm" in guidance_from_confirmed(*args, False).lower()
assert "Source IDs" in guidance_from_confirmed(*args, True)
print("Passed 4 meal-photo workflow checks.")
