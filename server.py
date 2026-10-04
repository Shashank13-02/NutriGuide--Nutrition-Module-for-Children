"""NutriGuide Child Nutrition Screening & Caregiver Education Platform Server

Serves a unified modern web UI on localhost with:
1. Intake indicators: deterministic WHO/UNICEF calculations for ages 6–23 months.
2. Text SLM: constrained selection of reviewed caregiver guidance.
3. Meal Photo Companion: SmolVLM observations with caregiver confirmation.
Target: 0–72 months; educational bands 0–59 months; intake indicators 6–23 months.
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
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from typing import Any
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from PIL import Image

# Ensure local cache is prioritized
BASE_DIR = Path(__file__).parent.resolve()
CACHE_DIR = BASE_DIR / ".hf_cache"
if CACHE_DIR.exists():
    os.environ.setdefault("HF_HOME", str(CACHE_DIR))

# Import domain logic and screening constants
from screening_constants import (
    CURRENT_IMPLEMENTED_MAX_AGE_MONTHS,
    MODULE_NAME,
    MODULE_TYPE,
    SCREENING_DISCLAIMER,
    SCREENING_ENGINE_STATUS,
    SUPPORTED_MIN_AGE_MONTHS,
    TARGET_MAX_AGE_MONTHS,
    VITAMIN_D_SCREENING_ENABLED,
)
from app import KB, MODEL_ID, SYSTEM, find_band, context_for, red_flag_gate, explain_screening_findings, grounded_answer
from meal_photo_app import (
    VLM_ID,
    ALLOWED_TEXTURES,
    PHOTO_POLICY,
    _extract_json,
    create_photo_draft,
    guidance_from_confirmed,
)
from nutrition_engine import (
    FOOD_GROUPS,
    ALLERGEN_FLAGS,
    TEXTURES,
    PREPARATION_FLAGS,
    review_meal,
)

from intake_screening import screen_intake, format_screening
from model_runtime import load_pipeline, generate_vision, model_status

MAX_REQUEST_BYTES = 16 * 1024 * 1024


def get_pipeline():
    return load_pipeline("text")


def get_vision_pipeline():
    return load_pipeline("vision")


def decode_meal_image(source) -> Image.Image:
    with Image.open(source) as image:
        if image.width * image.height > 12_000_000:
            raise ValueError("Meal images must be at most 12 megapixels.")
        image.thumbnail((1536, 1536))
        return image.convert("RGB")


def parse_vision_output(generated_text: Any) -> dict:
    if isinstance(generated_text, list) and generated_text:
        last = generated_text[-1]
        if isinstance(last, dict) and "content" in last:
            generated_text = last["content"]
        else:
            generated_text = str(last)
    elif not isinstance(generated_text, str):
        generated_text = str(generated_text)

    return _extract_json(generated_text)


def analyze_photo_bytes(image: Image.Image) -> dict:
    try:
        raw_text, draft = create_photo_draft(image, generate=generate_vision)
    except Exception as exc:
        return {
            "success": False,
            "parse_valid": False,
            "status": f"Could not analyze the photo: {exc}",
            "raw_text": "",
            "candidate_foods": [],
            "visible_foods": [],
            "observations": ["mixed/unclear"],
            "texture_cues": ["mixed/unclear"],
            "uncertain_items": [],
            "uncertain": True,
            "child_present": False,
            "requires_confirmation": True,
            "diagnostic": False,
            "module_type": MODULE_TYPE,
            "screening_notice": SCREENING_DISCLAIMER,
        }

    if draft["child_present"]:
        return {
            "success": False,
            "parse_valid": draft["parse_valid"],
            "status": "A child or face may be visible. Do not submit this photo. Crop it to the meal only and try again.",
            "raw_text": raw_text,
            "candidate_foods": [],
            "visible_foods": [],
            "observations": ["mixed/unclear"],
            "texture_cues": ["mixed/unclear"],
            "uncertain_items": [],
            "uncertain": True,
            "child_present": True,
            "requires_confirmation": True,
            "diagnostic": False,
            "module_type": MODULE_TYPE,
            "screening_notice": SCREENING_DISCLAIMER,
        }

    status = "Food suggestions ready to review. Correct any food names and confirm preparation and texture."
    if not draft["parse_valid"]:
        status = "The model could not produce readable food observations. Try a clearer meal photo or enter foods manually."
    elif draft["uncertain"]:
        status += " Hidden ingredients and softness cannot be confirmed from the photo."

    return {
        "success": draft["parse_valid"],
        "parse_valid": draft["parse_valid"],
        "model": model_status()["vision"]["loaded_model"],
        "status": status,
        "raw_text": raw_text,
        "candidate_foods": draft.get("candidate_foods", draft["visible_foods"]),
        "visible_foods": draft["visible_foods"],
        "observations": draft.get("observations", draft["texture_cues"]),
        "texture_cues": draft["texture_cues"],
        "uncertain_items": draft.get("uncertain_items", []),
        "uncertain": draft["uncertain"],
        "child_present": False,
        "requires_confirmation": True,
        "diagnostic": False,
        "module_type": MODULE_TYPE,
        "screening_notice": SCREENING_DISCLAIMER,
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
            models = model_status()
            self.send_json(200, {
                "status": "ok",
                "module_name": MODULE_NAME,
                "module_type": MODULE_TYPE,
                "scope": "children_0_to_6_years",
                "target_scope": f"0_to_{TARGET_MAX_AGE_MONTHS}_months",
                "implemented_rule_scope": "6_to_23_months",
                "educational_guidance_scope": f"0_to_{CURRENT_IMPLEMENTED_MAX_AGE_MONTHS}_months",
                "screening_engine_status": SCREENING_ENGINE_STATUS,
                "diagnostic": False,
                "vitamin_d_screening_enabled": VITAMIN_D_SCREENING_ENABLED,
                "screening_notice": SCREENING_DISCLAIMER,
                "lm_model": models["text"]["loaded_model"] or models["text"]["configured_model"],
                "lm_ready": models["text"]["ready"],
                "lm_loading": models["text"]["loading"],
                "models": models,
                "vlm_model": models["vision"]["loaded_model"] or models["vision"]["configured_model"],
                "vlm_ready": models["vision"]["ready"],
                "vlm_loading": models["vision"]["loading"],
                "sources_count": len(SOURCES_INFO),
            })
            return

        if path == "/api/bands":
            self.send_json(200, {
                "module_type": MODULE_TYPE,
                "diagnostic": False,
                "screening_notice": SCREENING_DISCLAIMER,
                "target_scope_months": TARGET_MAX_AGE_MONTHS,
                "implemented_scope_months": CURRENT_IMPLEMENTED_MAX_AGE_MONTHS,
                "age_bands": KB.get("age_bands", []),
                "red_flags": KB.get("red_flags", []),
                "sources": SOURCES_INFO,
            })
            return

        if path == "/api/meal-meta":
            self.send_json(200, {
                "module_type": MODULE_TYPE,
                "diagnostic": False,
                "screening_notice": SCREENING_DISCLAIMER,
                "food_groups": list(FOOD_GROUPS),
                "textures": list(TEXTURES),
                "preparation_flags": list(PREPARATION_FLAGS),
                "allergen_flags": list(ALLERGEN_FLAGS),
                "photo_policy": PHOTO_POLICY,
                "vlm_model": VLM_ID,
                "vlm_ready": model_status()["vision"]["ready"],
            })
            return

        if path == "/" or not path:
            self.path = "/index.html"
            return super().do_GET()
        
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length < 0:
                raise ValueError("Content-Length must not be negative")
        except ValueError:
            self.close_connection = True
            self.send_json(400, {"error": "Invalid Content-Length."})
            return
        if content_length > MAX_REQUEST_BYTES:
            self.close_connection = True
            self.send_json(413, {"error": "Request exceeds the 16 MiB limit."})
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}
            if not isinstance(data, dict):
                raise ValueError("JSON payload must be an object")
        except (ValueError, UnicodeDecodeError) as e:
            self.send_json(400, {"error": f"Invalid JSON payload: {e}"})
            return

        if parsed.path == "/api/screen-intake":
            try:
                result = screen_intake(data)
                # The canonical result is always rendered before optional AI selection.
                result["explanation"] = format_screening(result)
                if data.get("use_model") is True and not result["professional_review_flag"] and 6 <= result["age_months"] <= 23:
                    result["explanation"] += "\n\n" + explain_screening_findings(result, result["age_months"], use_model=True)
                self.send_json(200, result)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
            return

        if parsed.path == "/api/query":
            age_months = data.get("age_months")
            question = data.get("question", "")
            if not isinstance(question, str):
                self.send_json(400, {"error": "question must be a string."})
                return
            question = question.strip()
            use_model = data.get("use_model", False)
            if type(use_model) is not bool:
                self.send_json(400, {"error": "use_model must be true or false."})
                return

            if age_months is None or type(age_months) is not int or not (SUPPORTED_MIN_AGE_MONTHS <= age_months <= CURRENT_IMPLEMENTED_MAX_AGE_MONTHS):
                self.send_json(400, {
                    "error": f"age_months must be an integer between {SUPPORTED_MIN_AGE_MONTHS} and {CURRENT_IMPLEMENTED_MAX_AGE_MONTHS} for currently implemented screening bands (target scope: 0 to {TARGET_MAX_AGE_MONTHS} months; 60 to {TARGET_MAX_AGE_MONTHS} months screening rules planned for Phase 2)."
                })
                return

            if not question:
                self.send_json(400, {"error": "question must not be empty."})
                return
            if len(question) > 4000:
                self.send_json(400, {"error": "question must be at most 4000 characters."})
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
                    "module_type": MODULE_TYPE,
                    "diagnostic": False,
                    "screening_notice": SCREENING_DISCLAIMER,
                    "screening_engine_status": SCREENING_ENGINE_STATUS,
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
                    "module_type": MODULE_TYPE,
                    "diagnostic": False,
                    "screening_notice": SCREENING_DISCLAIMER,
                    "screening_engine_status": SCREENING_ENGINE_STATUS,
                })
                return

            try:
                answer_text, answer_mode = grounded_answer(age_months, question)

                self.send_json(200, {
                    "is_red_flag": False,
                    "answer": answer_text,
                    "age_months": age_months,
                    "band": band,
                    "context": context,
                    "sources": sources_meta,
                    "mode": answer_mode,
                    "model": model_status()["text"]["loaded_model"],
                    "module_type": MODULE_TYPE,
                    "diagnostic": False,
                    "screening_notice": SCREENING_DISCLAIMER,
                    "screening_engine_status": SCREENING_ENGINE_STATUS,
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
                try:
                    if not isinstance(sample_name, str):
                        raise ValueError("sample must be a file name.")
                    sample_path = BASE_DIR / "static" / "samples" / Path(sample_name).name
                    if sample_path.exists():
                        pil_img = decode_meal_image(sample_path)
                except (ValueError, OSError) as exc:
                    self.send_json(400, {"error": f"Could not decode sample image: {exc}"})
                    return
            elif img_data:
                try:
                    if "," in img_data:
                        img_data = img_data.split(",", 1)[1]
                    raw_bytes = base64.b64decode(img_data, validate=True)
                    pil_img = decode_meal_image(io.BytesIO(raw_bytes))
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
            confirmed = data.get("confirmed") is True

            try:
                if type(age_months) is not int or not 0 <= age_months <= 72:
                    raise ValueError("age_months must be a whole number from 0 to 72.")
                guidance_text = guidance_from_confirmed(
                    age_months=age_months,
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
                    "module_type": MODULE_TYPE,
                    "diagnostic": False,
                    "screening_notice": SCREENING_DISCLAIMER,
                    "screening_engine_status": SCREENING_ENGINE_STATUS,
                })
            except Exception as e:
                self.send_json(400, {"error": str(e)})
            return

        elif parsed.path == "/api/explain-screening":
            age_months = data.get("age_months", 12)
            screening_result = data.get("screening_result", "INSUFFICIENT_DATA")
            findings = data.get("findings", [])
            use_model = data.get("use_model", False)
            if type(use_model) is not bool:
                self.send_json(400, {"error": "use_model must be true or false."})
                return

            if age_months is None or type(age_months) is not int or not (SUPPORTED_MIN_AGE_MONTHS <= age_months <= CURRENT_IMPLEMENTED_MAX_AGE_MONTHS):
                self.send_json(400, {
                    "error": f"age_months must be an integer between {SUPPORTED_MIN_AGE_MONTHS} and {CURRENT_IMPLEMENTED_MAX_AGE_MONTHS} for currently implemented screening bands (target scope: 0 to {TARGET_MAX_AGE_MONTHS} months)."
                })
                return

            try:
                explanation = explain_screening_findings(
                    screening_payload={
                        "screening_result": screening_result,
                        "findings": findings,
                        "professional_review_flag": data.get("professional_review_flag", False),
                    },
                    age_months=age_months,
                    use_model=use_model,
                )
                self.send_json(200, {
                    "success": True,
                    "screening_result": screening_result,
                    "explanation": explanation,
                    "age_months": age_months,
                    "module_type": MODULE_TYPE,
                    "diagnostic": False,
                    "screening_notice": SCREENING_DISCLAIMER,
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
    
    if os.getenv("NUTRIGUIDE_WARMUP") == "1":
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
