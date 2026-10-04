"""Compare simple image requests using the real local vision checkpoint."""
import json
import time
from pathlib import Path
from PIL import Image
from model_runtime import generate_vision, model_status

ROOT = Path(__file__).parent
records = []
for name in ("meal_carrots_oatmeal.jpg", "meal_lentils_rice.jpg"):
    for prompt in ("Describe the food visible in this image in one short sentence.", 'List the visible foods. Answer only with food names separated by commas. If ingredients are unclear, say "unclear dish".'):
        with Image.open(ROOT / "static" / "samples" / name) as source:
            image = source.convert("RGB")
        messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
        start = time.perf_counter()
        raw = generate_vision(messages, max_new_tokens=40)[0]["generated_text"]
        result = {"sample": name, "prompt": prompt, "latency_seconds": round(time.perf_counter() - start, 2), "raw_text": raw}
        records.append(result)
        print(json.dumps(result), flush=True)
        (ROOT / "data" / "eval" / "vision_caption_probe.json").write_text(json.dumps({"accuracy_validated": False, "model": model_status()["vision"], "results": records}, indent=2), encoding="utf-8")
