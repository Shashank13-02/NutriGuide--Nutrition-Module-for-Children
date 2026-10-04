"""Small real-inference smoke check; these samples do not establish model accuracy."""
import json
import time
from pathlib import Path
from PIL import Image
from model_runtime import generate_vision, model_status
from meal_photo_app import _extract_json

ROOT = Path(__file__).parent
BASELINE = """Analyze only the meal, plate, bowl, or tray. Do NOT infer anything about a child, health status, or nutritional deficiency.
Return candidate observations only as JSON with: visible_foods (up to 8 ordinary food names), texture_cues (only: smooth puree, mashed, soft pieces, finger food, mixed/unclear), uncertain (boolean), child_present (boolean). If a child or face is visible, set child_present true. If unclear, use empty foods and mixed/unclear."""
OPTIMIZED = """Identify the visible foods in this meal photo. Describe only what the image shows. Do not guess hidden ingredients, portions, nutrition, cooking method, softness or whether food is safe.
Use common food names; describe an ambiguous dish by appearance rather than guessing ingredients. If no food is visible, return an empty food list. Mark uncertain true for ambiguous foods. Set child_present true if a person or face is visible.
Return ONLY a JSON object with this structure:
{"visible_foods": [], "texture_cues": ["mixed/unclear"], "uncertain_items": [], "uncertain": true, "child_present": false}
Put up to 8 visible food names in visible_foods. Texture labels allowed: smooth puree, mashed, soft pieces, finger food, mixed/unclear. Use mixed/unclear if softness cannot be determined. List ambiguous items in uncertain_items."""

def main():
    outputs = []
    for version, prompt in (("baseline", BASELINE), ("optimized", OPTIMIZED)):
        for name in ("meal_carrots_oatmeal.jpg", "meal_lentils_rice.jpg"):
            with Image.open(ROOT / "static" / "samples" / name) as source:
                image = source.convert("RGB")
            messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
            start = time.perf_counter()
            raw = generate_vision(messages)[0]["generated_text"]
            record = {"prompt_version": version, "sample": name, "latency_seconds": round(time.perf_counter() - start, 2), "raw_text": raw, "draft": _extract_json(raw)}
            outputs.append(record)
            print(json.dumps(record), flush=True)
            (ROOT / "data" / "eval" / "vision_live_smoke_results.json").write_text(json.dumps({"evaluation_kind": "real_sample_smoke_check", "accuracy_validated": False, "models": model_status(), "results": outputs}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
