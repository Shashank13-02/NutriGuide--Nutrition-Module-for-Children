"""Local meal-photo companion for the NutriGuide educational prototype.

This app analyzes a MEAL photo only. It never estimates a child's age, body size,
nutrition status, health, or diagnosis from an image. Vision-model observations are
drafts that the caregiver must confirm or correct before guidance is displayed.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any

import gradio as gr
from PIL import Image

from nutrition_engine import ALLERGEN_FLAGS, FOOD_GROUPS, PREPARATION_FLAGS, TEXTURES, review_meal

VLM_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"
ALLOWED_TEXTURES = {"smooth puree", "mashed", "soft pieces", "finger food", "mixed/unclear"}
PHOTO_POLICY = """Upload only a photo of the meal, plate, bowl, or tray—never the child.
This tool does not assess a child’s body, face, health, growth, feeding ability, or nutritional status.
The model's food and texture observations can be wrong and require caregiver confirmation."""

@lru_cache(maxsize=1)
def get_vision_model():
    from transformers import pipeline
    return pipeline("image-text-to-text", model=VLM_ID)

def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort parse; unknown model output becomes a blank review form."""
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return {"visible_foods": [], "texture_cues": ["mixed/unclear"], "uncertain": True, "child_present": False}
    try:
        result = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"visible_foods": [], "texture_cues": ["mixed/unclear"], "uncertain": True, "child_present": False}
    foods = [str(x).strip() for x in result.get("visible_foods", []) if str(x).strip()][:8]
    textures = [str(x).strip().lower() for x in result.get("texture_cues", [])]
    textures = [x for x in textures if x in ALLOWED_TEXTURES] or ["mixed/unclear"]
    return {"visible_foods": foods, "texture_cues": textures, "uncertain": bool(result.get("uncertain", True)), "child_present": bool(result.get("child_present", False))}

def analyze_meal_photo(image: Image.Image | None):
    if image is None:
        return "Upload a meal photo first.", ""
    prompt = """Analyze only the meal, plate, bowl, or tray. Do NOT infer anything about a child.
Return JSON only with: visible_foods (up to 8 ordinary food names), texture_cues (only: smooth puree, mashed, soft pieces, finger food, mixed/unclear), uncertain (boolean), child_present (boolean). If a child or face is visible, set child_present true. If unclear, use empty foods and mixed/unclear."""
    messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
    try:
        result = get_vision_model()(text=messages, max_new_tokens=120, do_sample=False, return_full_text=False)
        draft = _extract_json(result[0]["generated_text"])
    except Exception as exc:
        return f"Could not analyze the photo: {exc}", ""
    if draft["child_present"]:
        return "A child or face may be visible. Do not submit this photo. Crop it to the meal only and try again.", ""
    status = "Draft observations only — please correct them before continuing."
    if draft["uncertain"]:
        status += " The model marked the photo as uncertain."
    return status, ", ".join(draft["visible_foods"])

def guidance_from_confirmed(age_months: int, foods: str, groups: list[str], textures: list[str], preparation: list[str], allergens: list[str], daily_groups: list[str], confirmed: bool):
    if not confirmed:
        return "Please confirm that you reviewed and corrected the model's observations."
    try:
        return review_meal(int(age_months), foods, groups, textures, preparation, allergens, daily_groups)
    except (ValueError, TypeError) as exc:
        return f"Please correct the form: {exc}"

with gr.Blocks(title="NutriGuide: meal-photo companion") as demo:
    gr.Markdown("# NutriGuide meal-photo companion\n" + PHOTO_POLICY)
    with gr.Row():
        image = gr.Image(label="Meal photo only", type="pil", sources=["upload", "webcam"])
        with gr.Column():
            analyze = gr.Button("1. Create a draft observation")
            status = gr.Textbox(label="Photo review status", interactive=False)
            foods = gr.Textbox(label="2. Confirm or correct visible foods", placeholder="Example: mashed lentils, soft rice, cooked carrot")
            groups = gr.CheckboxGroup(FOOD_GROUPS, label="3. Confirm food groups visible in this meal")
            textures = gr.CheckboxGroup(TEXTURES, label="4. Confirm texture(s)")
            preparation = gr.CheckboxGroup(PREPARATION_FLAGS, label="5. Confirm preparation/safety steps")
            allergens = gr.CheckboxGroup(ALLERGEN_FLAGS, label="6. Potential allergens present (select only if caregiver confirms)")
    age = gr.Slider(0, 59, value=12, step=1, label="Child age in completed months")
    daily_groups = gr.CheckboxGroup(FOOD_GROUPS, label="7. Caregiver-reported food groups offered over the day (not inferred from the photo)")
    confirmed = gr.Checkbox(label="I reviewed and corrected the photo observations; this is a meal-only photo.")
    generate = gr.Button("8. Get age-specific educational guidance", variant="primary")
    response = gr.Textbox(label="Guidance", lines=18)
    analyze.click(analyze_meal_photo, inputs=image, outputs=[status, foods])
    generate.click(guidance_from_confirmed, inputs=[age, foods, groups, textures, preparation, allergens, daily_groups, confirmed], outputs=response)

if __name__ == "__main__":
    # Keep photos in browser memory: no app-side file/database persistence is implemented.
    demo.launch(server_name="127.0.0.1", server_port=int(os.getenv("NUTRIGUIDE_PORT", "8899")))
