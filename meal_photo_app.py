"""Local meal-photo companion for the NutriGuide child nutrition screening prototype.

This app analyzes a MEAL photo only to propose candidate foods and texture observations.
It never estimates a child's age, body size, nutrition status, health, or clinical diagnosis
from an image. Vision-model observations are drafts that the caregiver must confirm or correct
before screening guidance is displayed.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any

from PIL import Image

try:
    import gradio as gr
except ImportError:
    gr = None

import os
from nutrition_engine import ALLERGEN_FLAGS, FOOD_GROUPS, PREPARATION_FLAGS, TEXTURES, review_meal
from screening_constants import DEFAULT_VISION_MODEL_ID, SCREENING_DISCLAIMER

VLM_ID = os.getenv("NUTRIGUIDE_VISION_MODEL", DEFAULT_VISION_MODEL_ID)
ALLOWED_TEXTURES = {"smooth puree", "mashed", "soft pieces", "finger food", "mixed/unclear"}
PHOTO_POLICY = f"""Upload only a photo of the meal, plate, bowl, or tray—never the child.
This screening tool does not diagnose disease or assess a child’s body, face, health, growth, feeding ability, or nutritional status.
The vision model's candidate food and texture observations are drafts and require caregiver confirmation before screening guidance is displayed.
Screening notice: {SCREENING_DISCLAIMER}"""

@lru_cache(maxsize=1)
def get_vision_model():
    from transformers import pipeline
    return pipeline("image-text-to-text", model=VLM_ID)

def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort parse; unknown model output becomes a blank review form with mandatory confirmation."""
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return {
            "visible_foods": [],
            "candidate_foods": [],
            "texture_cues": ["mixed/unclear"],
            "observations": ["mixed/unclear"],
            "uncertain_items": [],
            "uncertain": True,
            "child_present": False,
            "requires_confirmation": True,
        }
    try:
        result = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {
            "visible_foods": [],
            "candidate_foods": [],
            "texture_cues": ["mixed/unclear"],
            "observations": ["mixed/unclear"],
            "uncertain_items": [],
            "uncertain": True,
            "child_present": False,
            "requires_confirmation": True,
        }
    foods = [str(x).strip() for x in result.get("visible_foods", result.get("candidate_foods", [])) if str(x).strip()][:8]
    textures = [str(x).strip().lower() for x in result.get("texture_cues", result.get("observations", []))]
    textures = [x for x in textures if x in ALLOWED_TEXTURES] or ["mixed/unclear"]
    uncertain = bool(result.get("uncertain", True))
    uncertain_items = [str(x).strip() for x in result.get("uncertain_items", []) if str(x).strip()]
    return {
        "visible_foods": foods,
        "candidate_foods": foods,
        "texture_cues": textures,
        "observations": textures,
        "uncertain_items": uncertain_items,
        "uncertain": uncertain,
        "child_present": bool(result.get("child_present", False)),
        "requires_confirmation": True,
    }

def analyze_meal_photo(image: Image.Image | None):
    if image is None:
        return "Upload a meal photo first.", ""
    prompt = """Analyze only the meal, plate, bowl, or tray. Do NOT infer anything about a child, health status, or nutritional deficiency.
Return candidate observations only as JSON with: visible_foods (up to 8 ordinary food names), texture_cues (only: smooth puree, mashed, soft pieces, finger food, mixed/unclear), uncertain (boolean), child_present (boolean). If a child or face is visible, set child_present true. If unclear, use empty foods and mixed/unclear."""
    messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
    try:
        result = get_vision_model()(text=messages, max_new_tokens=120, do_sample=False, return_full_text=False)
        draft = _extract_json(result[0]["generated_text"])
    except Exception as exc:
        return f"Could not analyze the photo: {exc}", ""
    if draft["child_present"]:
        return "A child or face may be visible. Do not submit this photo. Crop it to the meal only and try again.", ""
    status = "Draft observations only — requires caregiver confirmation before screening guidance."
    if draft["uncertain"]:
        status += " The model marked the photo as uncertain."
    return status, ", ".join(draft["visible_foods"])

def guidance_from_confirmed(age_months: int, foods: str, groups: list[str], textures: list[str], preparation: list[str], allergens: list[str], daily_groups: list[str], confirmed: bool):
    if not confirmed:
        return "Please confirm that you reviewed and corrected the model's draft observations before screening review."
    try:
        return review_meal(int(age_months), foods, groups, textures, preparation, allergens, daily_groups)
    except (ValueError, TypeError) as exc:
        return f"Please correct the form: {exc}"

demo = None
if gr is not None:
    with gr.Blocks(title="NutriGuide: Meal Photo Screening Companion") as demo:
        gr.Markdown("# NutriGuide Meal Photo Screening Companion\n" + PHOTO_POLICY)
        with gr.Row():
            image = gr.Image(label="Meal photo only", type="pil", sources=["upload", "webcam"])
            with gr.Column():
                analyze = gr.Button("1. Create draft candidate observations")
                status = gr.Textbox(label="Photo review status", interactive=False)
                foods = gr.Textbox(label="2. Confirm or correct visible foods", placeholder="Example: mashed lentils, soft rice, cooked carrot")
                groups = gr.CheckboxGroup(FOOD_GROUPS, label="3. Confirm food groups visible in this meal")
                textures = gr.CheckboxGroup(TEXTURES, label="4. Confirm texture(s)")
                preparation = gr.CheckboxGroup(PREPARATION_FLAGS, label="5. Confirm preparation/safety steps")
                allergens = gr.CheckboxGroup(ALLERGEN_FLAGS, label="6. Potential allergens present (select only if caregiver confirms)")
        age = gr.Slider(0, 59, value=12, step=1, label="Child age in completed months (0-59m implemented; 0-72m target scope)")
        daily_groups = gr.CheckboxGroup(FOOD_GROUPS, label="7. Caregiver-reported food groups offered over the day (not inferred from photo)")
        confirmed = gr.Checkbox(label="I reviewed and corrected the photo observations; this is a meal-only photo.")
        generate = gr.Button("8. Review meal screening guidance", variant="primary")
        response = gr.Textbox(label="Screening & Educational Guidance", lines=18)
        analyze.click(analyze_meal_photo, inputs=image, outputs=[status, foods])
        generate.click(guidance_from_confirmed, inputs=[age, foods, groups, textures, preparation, allergens, daily_groups, confirmed], outputs=response)

if __name__ == "__main__":
    if gr is None:
        raise ImportError(
            "Gradio is required to run the standalone meal_photo_app.py interface. "
            "Please install gradio with: pip install gradio"
        )
    # Keep photos in browser memory: no app-side file/database persistence is implemented.
    demo.launch(server_name="127.0.0.1", server_port=int(os.getenv("NUTRIGUIDE_PORT", "8899")))
