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
from model_runtime import configured_vision_model

VLM_ID = configured_vision_model()
ALLOWED_TEXTURES = {"smooth puree", "mashed", "soft pieces", "finger food", "mixed/unclear"}
PHOTO_POLICY = f"""Upload only a photo of the meal, plate, bowl, or tray—never the child.
This screening tool does not diagnose disease or assess a child’s body, face, health, growth, feeding ability, or nutritional status.
The vision model's candidate food and texture observations are drafts and require caregiver confirmation before screening guidance is displayed.
Screening notice: {SCREENING_DISCLAIMER}"""

def get_vision_model():
    from model_runtime import load_pipeline
    return load_pipeline("vision")


def _extract_json(text: str) -> dict[str, Any]:
    """Only schema-valid observations become editable drafts; malformed output abstains."""
    blank = {"visible_foods": [], "candidate_foods": [], "texture_cues": ["mixed/unclear"],
             "observations": ["mixed/unclear"], "uncertain_items": [], "uncertain": True,
             "child_present": False, "requires_confirmation": True, "parse_valid": False}
    if not isinstance(text, str):
        return blank
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return blank
    try:
        result = json.loads(match.group(0))
        if not isinstance(result, dict):
            return blank
        # Preserve a positive person flag even if the food fields are malformed.
        blank["child_present"] = result.get("child_present") is True
        foods = result.get("visible_foods", result.get("candidate_foods", []))
        textures = result.get("texture_cues", result.get("observations", []))
        uncertain_items = result.get("uncertain_items", [])
        if any(not isinstance(v, list) or any(not isinstance(x, str) for x in v) for v in (foods, textures, uncertain_items)):
            return blank
        if type(result.get("uncertain")) is not bool or type(result.get("child_present")) is not bool:
            return blank
        foods = list(dict.fromkeys(x.strip()[:100] for x in foods if x.strip()))[:8]
        textures = [x.strip().lower() for x in textures if x.strip().lower() in ALLOWED_TEXTURES] or ["mixed/unclear"]
        return {**blank, "visible_foods": foods, "candidate_foods": foods,
                "texture_cues": textures, "observations": textures,
                "uncertain_items": uncertain_items[:8], "uncertain": result["uncertain"],
                "child_present": result["child_present"], "parse_valid": True}
    except (ValueError, TypeError):
        return blank


FOOD_LIST_PROMPT = 'List the visible foods. Answer only with food names separated by commas. If ingredients are unclear, say "unclear dish".'
PERSON_PROMPT = "Is a person or a face visible in this image? Answer only yes or no."


def parse_food_list(text: str) -> dict[str, Any]:
    """Convert a short model list into an editable draft without inventing foods."""
    blank = _extract_json("")
    if not isinstance(text, str) or not text.strip():
        return blank
    cleaned = re.sub(r"^\s*(?:foods?|visible foods?)\s*:\s*", "", text, flags=re.I).strip().strip('"').rstrip(".")
    if cleaned.lower() in {"none", "no food", "no foods", "unclear", "unclear dish"}:
        return {**blank, "parse_valid": True, "uncertain_items": ["Food ingredients could not be identified."]}
    items = re.split(r"[,;\n]+", cleaned)
    foods = []
    for item in items:
        item = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", item).strip().strip('"[]').rstrip(".")
        if not item:
            continue
        if len(item) > 60 or len(item.split()) > 5 or not re.fullmatch(r"[\w '\-()/]+", item):
            return blank
        if re.search(r"\b(?:image|photo|child|person|face|diagnos\w*|deficien\w*|calories|healthy|unhealthy|safe|unsafe|visible|there|contains|shows|cannot|instructions)\b", item, re.I):
            return blank
        if item.casefold() not in {food.casefold() for food in foods}:
            foods.append(item)
    if not foods or len(foods) > 8:
        return blank
    return {**blank, "visible_foods": foods, "candidate_foods": foods, "parse_valid": True,
            "uncertain_items": ["Confirm food identities and any hidden ingredients.", "Confirm texture and softness yourself."]}


def create_photo_draft(image: Image.Image, generate=None):
    """Use two short visual questions; JSON formatting is handled in code."""
    if generate is None:
        from model_runtime import generate_vision
        generate = generate_vision

    def ask(prompt, budget):
        messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
        return generate(messages, max_new_tokens=budget)[0]["generated_text"].strip()

    person = ask(PERSON_PROMPT, 6)
    person_answer = person.lower().strip().rstrip(".! ")
    if person_answer == "yes":
        return f"Person check: {person}", {**_extract_json(""), "child_present": True, "parse_valid": True}
    if person_answer != "no":
        return f"Person check: {person}", _extract_json("")
    raw = ask(FOOD_LIST_PROMPT, 40)
    draft = parse_food_list(raw)
    return f"Person check: {person}\nVisible foods: {raw}", draft


def analyze_meal_photo(image: Image.Image | None):
    if image is None:
        return "Upload a meal photo first.", ""
    try:
        raw, draft = create_photo_draft(image)
    except Exception as exc:
        return f"Could not analyze the photo: {exc}", ""
    if draft["child_present"]:
        return "A child or face may be visible. Do not submit this photo. Crop it to the meal only and try again.", ""
    if not draft["parse_valid"]:
        return "The photo could not be read reliably. Try a clearer meal photo or enter foods manually.", ""
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
