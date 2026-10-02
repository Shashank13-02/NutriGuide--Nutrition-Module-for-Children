"""NutriGuide Local Web Application Server

Serves a unified modern web UI on localhost with:
1. NutriGuide SLM: Text Q&A grounded in WHO/CDC pediatric guidelines with SmolLM2-360M-Instruct.
2. Meal Photo Companion: Meal image analysis using SmolVLM-500M-Instruct + Caregiver Confirmation & Safety Review.
"""
from __future__ import annotations

import base64
import io
import json
import mimetypes
import os
import re
import sys
import threading
from http.server import HTTPServer, ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from PIL import Image

# Ensure local cache is prioritized
BASE_DIR = Path(__file__).parent.resolve()
CACHE_DIR = BASE_DIR / ".hf_cache"
if CACHE_DIR.exists():
    os.environ.setdefault("HF_HOME", str(CACHE_DIR))

# Import domain logic
from app import KB, MODEL_ID, SYSTEM, find_band, context_for, red_flag_gate
from meal_photo_app import (
    VLM_ID,
    ALLOWED_TEXTURES,
    PHOTO_POLICY,
    _extract_json,
    guidance_from_confirmed,
)
from nutrition_engine import (
    FOOD_GROUPS,
    ALLERGEN_FLAGS,
    TEXTURES,
    PREPARATION_FLAGS,
    review_meal,
)

# Text Model Pipeline
_PIPELINE = None
_PIPELINE_LOCK = threading.Lock()
_PIPELINE_LOADING = False

# Vision Model Pipeline
_VLM_PIPELINE = None
_VLM_LOCK = threading.Lock()
_VLM_LOADING = False

def get_pipeline():
    global _PIPELINE, _PIPELINE_LOADING
    with _PIPELINE_LOCK:
        if _PIPELINE is not None:
            return _PIPELINE
        _PIPELINE_LOADING = True
    
    print(f"[*] Initializing local SLM model: {MODEL_ID}...")
    import torch
    from transformers import pipeline

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"[*] SLM Target device: {device}")
    
    try:
        pipe = pipeline(
            "text-generation",
            model=MODEL_ID,
            device=device,
            dtype=torch.float16 if device == "mps" else torch.float32,
        )
    except Exception as e:
        print(f"[!] Warning: SLM device-specific load fallback ({e})...")
        pipe = pipeline("text-generation", model=MODEL_ID)
        
    with _PIPELINE_LOCK:
        _PIPELINE = pipe
        _PIPELINE_LOADING = False
    print("[+] SLM Model loaded successfully into memory.")
    return _PIPELINE

def get_vision_pipeline():
    global _VLM_PIPELINE, _VLM_LOADING
    with _VLM_LOCK:
        if _VLM_PIPELINE is not None:
            return _VLM_PIPELINE
        _VLM_LOADING = True

    print(f"[*] Initializing local VLM model: {VLM_ID}...")
    import torch
    from transformers import pipeline

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"[*] VLM Target device: {device}")

    try:
        pipe = pipeline(
            "image-text-to-text",
            model=VLM_ID,
            device=device,
            dtype=torch.float16 if device == "mps" else torch.float32,
        )
    except Exception as e:
        print(f"[!] Warning: VLM device-specific load fallback ({e})...")
        pipe = pipeline("image-text-to-text", model=VLM_ID)

    with _VLM_LOCK:
        _VLM_PIPELINE = pipe
        _VLM_LOADING = False
    print("[+] Vision Model loaded successfully into memory.")
    return _VLM_PIPELINE

def parse_vision_output(generated_text: Any) -> dict:
    if isinstance(generated_text, list) and generated_text:
        last = generated_text[-1]
        if isinstance(last, dict) and "content" in last:
            generated_text = last["content"]
        else:
            generated_text = str(last)
    elif not isinstance(generated_text, str):
        generated_text = str(generated_text)

    draft = _extract_json(generated_text)
    raw_clean = generated_text.strip()
    
    # If JSON extraction didn't extract foods, attempt natural language extraction
    if not draft["visible_foods"] and len(raw_clean) > 0:
        if re.search(r"\b(child|baby|infant|kid|face|toddler|person|hand|arm)\b", raw_clean, re.I):
            draft["child_present"] = True
            
        text_lower = raw_clean.lower()
        textures = []
        if "puree" in text_lower or "smooth" in text_lower:
            textures.append("smooth puree")
        if "mash" in text_lower:
            textures.append("mashed")
        if "soft" in text_lower or "piece" in text_lower or "cooked" in text_lower:
            textures.append("soft pieces")
        if "finger" in text_lower or "strip" in text_lower or "stick" in text_lower:
            textures.append("finger food")
        if textures:
            draft["texture_cues"] = textures
            
        foods_found = []
        # Check visible_foods [...] bracket format
        bracket_match = re.search(r"visible_foods\s*\[(.*?)\]", raw_clean, re.I)
        if bracket_match:
            raw_items = [s.strip(" '\"") for s in bracket_match.group(1).split(",") if s.strip(" '\"")]
            for it in raw_items:
                cl = it.lower()
                if cl and cl not in foods_found and len(cl) > 2:
                    foods_found.append(cl)

        items = re.findall(r"(?:bowl of|plate of|\d+\.|\*|-)\s*([a-zA-Z\s]+?)(?::|\.|\n|,|$)", raw_clean)
        for it in items:
            cl = it.strip().lower()
            if cl and cl not in {"food", "texture", "color", "plate", "bowl", "the food is", "is a"} and len(cl) > 2:
                cl = re.sub(r"^(the|a|an|bowl of|plate of)\s+", "", cl).strip()
                if cl and cl not in foods_found:
                    foods_found.append(cl)

        if not foods_found and len(raw_clean) < 100:
            cleaned = re.sub(r"[^\w\s,]", "", raw_clean).strip()
            if cleaned:
                for s in cleaned.split(","):
                    item = s.strip()
                    if item and len(item) > 2 and item.lower() not in {"yes", "no", "true", "false"}:
                        foods_found.append(item)
        if foods_found:
            draft["visible_foods"] = foods_found[:8]

    return draft

def analyze_photo_bytes(image: Image.Image) -> dict:
    prompt = """Analyze only the meal, plate, bowl, or tray. Do NOT infer anything about a child.
Return JSON only with: visible_foods (up to 8 ordinary food names), texture_cues (only: smooth puree, mashed, soft pieces, finger food, mixed/unclear), uncertain (boolean), child_present (boolean). If a child or face is visible, set child_present true. If unclear, use empty foods and mixed/unclear."""
    messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
    try:
        pipe = get_vision_pipeline()
        result = pipe(text=messages, max_new_tokens=140, do_sample=False, return_full_text=False)
        raw_text = result[0]["generated_text"]
        draft = parse_vision_output(raw_text)
    except Exception as exc:
        return {
            "status": f"Could not analyze the photo: {exc}",
            "raw_text": "",
            "visible_foods": [],
            "texture_cues": ["mixed/unclear"],
            "uncertain": True,
            "child_present": False,
        }

    if draft["child_present"]:
        return {
            "status": "A child or face may be visible. Do not submit this photo. Crop it to the meal only and try again.",
            "raw_text": raw_text,
            "visible_foods": [],
            "texture_cues": ["mixed/unclear"],
            "uncertain": True,
            "child_present": True,
        }

    status = "Draft observations only — please correct them before continuing."
    if draft["uncertain"]:
        status += " The model marked the photo as uncertain."

    return {
        "status": status,
        "raw_text": raw_text,
        "visible_foods": draft["visible_foods"],
        "texture_cues": draft["texture_cues"],
        "uncertain": draft["uncertain"],
        "child_present": False,
    }

SOURCES_INFO = {
    "WHO-IYCF": {
        "title": "WHO: Infant and young child feeding",
        "url": "https://www.who.int/news-room/fact-sheets/detail/infant-and-young-child-feeding",
        "description": "Exclusive breastfeeding, complementary feeding timing/frequency, responsive feeding"
    },
    "WHO-BF": {
        "title": "WHO: Breastfeeding Q&A",
        "url": "https://www.who.int/news-room/questions-and-answers/item/breastfeeding",
        "description": "Definition of exclusive breastfeeding and early initiation"
    },
    "WHO-CF-2023": {
        "title": "WHO Guideline: Complementary feeding (6–23 months)",
        "url": "https://www.who.int/publications/b/70981",
        "description": "Normative global guideline for solid food introduction and diversity"
    },
    "WHO-EARLY-FOODS": {
        "title": "WHO: Recommended food for the very early years",
        "url": "https://www.who.int/news-room/questions-and-answers/item/child-health-recommended-food-for-the-very-early-years",
        "description": "Texture progression, energy density, and family table meals"
    },
    "UNICEF-DIET": {
        "title": "UNICEF DATA: Infant and Young Child Diets",
        "url": "https://data.unicef.org/topic/nutrition/diets/",
        "description": "5-of-8 food-group minimum dietary diversity indicator"
    },
    "WHO-GROWTH": {
        "title": "WHO: Child growth standards",
        "url": "https://www.who.int/news-room/questions-and-answers/item/child-growth-standards",
        "description": "0–5 year growth curve and nutrition monitoring"
    },
    "CDC-SOLIDS": {
        "title": "CDC: When, what, and how to introduce solid foods",
        "url": "https://www.cdc.gov/infant-toddler-nutrition/foods-and-drinks/when-what-and-how-to-introduce-solid-foods.html",
        "description": "Developmental readiness, allergen exposure, and safe textures"
    },
    "CDC-CHOKING": {
        "title": "CDC: Choking hazards prevention",
        "url": "https://www.cdc.gov/infant-toddler-nutrition/foods-and-drinks/choking-hazards.html",
        "description": "Food preparation safeguards, high-risk foods, and active supervision"
    },
    "CDC-LIMITS": {
        "title": "CDC: Foods and drinks to avoid or limit",
        "url": "https://www.cdc.gov/infant-toddler-nutrition/foods-and-drinks/foods-and-drinks-to-avoid-or-limit.html",
        "description": "Honey, added sugars, unpasteurized items, and whole milk timing"
    },
    "CDC-FOOD-SAFETY": {
        "title": "CDC: Safer food choices under 5",
        "url": "https://www.cdc.gov/food-safety/foods/children-under-5.html",
        "description": "Foodborne illness risks and pathogen prevention for young children"
    },
}

class NutriGuideHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR / "static"), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/api/health":
            self.send_json(200, {
                "status": "ok",
                "lm_model": MODEL_ID,
                "lm_ready": _PIPELINE is not None,
                "lm_loading": _PIPELINE_LOADING,
                "vlm_model": VLM_ID,
                "vlm_ready": _VLM_PIPELINE is not None,
                "vlm_loading": _VLM_LOADING,
                "sources_count": len(SOURCES_INFO),
            })
            return

        if path == "/api/bands":
            self.send_json(200, {
                "age_bands": KB.get("age_bands", []),
                "red_flags": KB.get("red_flags", []),
                "sources": SOURCES_INFO,
            })
            return

        if path == "/api/meal-meta":
            self.send_json(200, {
                "food_groups": list(FOOD_GROUPS),
                "textures": list(TEXTURES),
                "preparation_flags": list(PREPARATION_FLAGS),
                "allergen_flags": list(ALLERGEN_FLAGS),
                "photo_policy": PHOTO_POLICY,
                "vlm_model": VLM_ID,
                "vlm_ready": _VLM_PIPELINE is not None,
            })
            return

        if path == "/" or not path:
            self.path = "/index.html"
            return super().do_GET()
        
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        
        try:
            data = json.loads(body) if body else {}
        except Exception as e:
            self.send_json(400, {"error": f"Invalid JSON payload: {e}"})
            return

        if parsed.path == "/api/query":
            age_months = data.get("age_months")
            question = data.get("question", "").strip()
            use_model = bool(data.get("use_model", False))

            if age_months is None or not isinstance(age_months, int) or not (0 <= age_months <= 59):
                self.send_json(400, {"error": "age_months must be an integer between 0 and 59."})
                return

            if not question:
                self.send_json(400, {"error": "question must not be empty."})
                return

            urgent = red_flag_gate(question)
            try:
                band = find_band(age_months)
                context = context_for(age_months)
            except Exception as e:
                self.send_json(400, {"error": str(e)})
                return

            sources_meta = [
                {"id": sid, **SOURCES_INFO.get(sid, {"title": sid, "url": "#", "description": ""})}
                for sid in band.get("sources", [])
            ]

            if urgent:
                self.send_json(200, {
                    "is_red_flag": True,
                    "answer": urgent,
                    "age_months": age_months,
                    "band": band,
                    "context": context,
                    "sources": sources_meta,
                    "mode": "red_flag_gate",
                })
                return

            if not use_model:
                self.send_json(200, {
                    "is_red_flag": False,
                    "answer": context,
                    "age_months": age_months,
                    "band": band,
                    "context": context,
                    "sources": sources_meta,
                    "mode": "curated_context",
                })
                return

            try:
                generator = get_pipeline()
                messages = [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"CONTEXT\n{context}\n\nQUESTION\n{question}"},
                ]
                output = generator(messages, max_new_tokens=240, do_sample=False)
                answer_text = output[0]["generated_text"][-1]["content"]

                self.send_json(200, {
                    "is_red_flag": False,
                    "answer": answer_text,
                    "age_months": age_months,
                    "band": band,
                    "context": context,
                    "sources": sources_meta,
                    "mode": "slm_generated",
                })
            except Exception as e:
                self.send_json(500, {"error": f"Model inference error: {str(e)}"})
            return

        elif parsed.path == "/api/analyze-meal":
            # Image analysis with SmolVLM
            img_data = data.get("image")
            sample_name = data.get("sample")

            pil_img = None
            if sample_name:
                sample_path = BASE_DIR / "static" / "samples" / Path(sample_name).name
                if sample_path.exists():
                    pil_img = Image.open(sample_path).convert("RGB")
            elif img_data:
                try:
                    if "," in img_data:
                        img_data = img_data.split(",", 1)[1]
                    raw_bytes = base64.b64decode(img_data)
                    pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
                except Exception as e:
                    self.send_json(400, {"error": f"Could not decode image: {e}"})
                    return

            if pil_img is None:
                self.send_json(400, {"error": "No valid image provided."})
                return

            analysis_result = analyze_photo_bytes(pil_img)
            self.send_json(200, analysis_result)
            return

        elif parsed.path == "/api/review-meal":
            age_months = data.get("age_months", 12)
            foods = str(data.get("foods", "")).strip()
            groups = data.get("groups", [])
            textures = data.get("textures", [])
            preparation = data.get("preparation", [])
            allergens = data.get("allergens", [])
            daily_groups = data.get("daily_groups", [])
            confirmed = bool(data.get("confirmed", False))

            try:
                guidance_text = guidance_from_confirmed(
                    age_months=int(age_months),
                    foods=foods,
                    groups=groups,
                    textures=textures,
                    preparation=preparation,
                    allergens=allergens,
                    daily_groups=daily_groups,
                    confirmed=confirmed,
                )
                self.send_json(200, {
                    "success": True,
                    "guidance": guidance_text,
                    "age_months": age_months,
                })
            except Exception as e:
                self.send_json(400, {"error": str(e)})
            return

        self.send_json(404, {"error": "Not Found"})

    def send_json(self, status_code: int, data: dict):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(payload)

def warm_up_models_in_background():
    def _warmup():
        try:
            get_pipeline()
        except Exception as e:
            print(f"[!] SLM warmup error: {e}")
        try:
            get_vision_pipeline()
        except Exception as e:
            print(f"[!] Vision model warmup error: {e}")

    threading.Thread(target=_warmup, daemon=True).start()

def run_server(port: int = 8080):
    static_dir = BASE_DIR / "static"
    static_dir.mkdir(exist_ok=True)
    
    print("[*] Starting background models warmup (SLM + VLM)...")
    warm_up_models_in_background()

    server = ThreadingHTTPServer(("127.0.0.1", port), NutriGuideHandler)
    print(f"\n=======================================================")
    print(f"  NutriGuide SLM + Meal-Photo Web App running at:")
    print(f"  --> http://localhost:{port}")
    print(f"  --> http://127.0.0.1:{port}")
    print(f"=======================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server.")
        server.server_close()

if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port=port)
