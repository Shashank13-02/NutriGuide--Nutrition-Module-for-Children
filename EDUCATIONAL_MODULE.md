# Caregiver Education & Guidance Module (0–6 Years Target Scope)

## Purpose and Product Boundary

This educational component serves as a downstream explanation and caregiver-support layer within the **Child Nutrition Screening Platform**. 

The conceptual flow of the platform is:
$$\text{Dietary Information} \longrightarrow \text{Screening Engine} \longrightarrow \text{Structured Findings} \longrightarrow \text{Caregiver-Friendly Explanation}$$

The educational assistant explains evidence-linked, age-appropriate feeding principles after dietary information is confirmed by the caregiver. It is **not** a clinical diagnostic tool, calorie/portion calculator, growth assessor, allergy evaluator, or treatment system.

Target population for the screening platform is **children aged 0 to 6 years (0 to 72 completed months)**; the current educational knowledge base is implemented for 0 to 59 completed months, with 60 to 72 months scheduled for subsequent phases.

## Learning & Screening Support Flow

1. Select the child's completed age in months (0–59 months currently implemented; 0–72 months target scope).
2. Review age-stage foundations: milk feeding, starting complementary foods, texture progression, family-food adaptation, or family eating.
3. Upload a **meal-only** image, if applicable. The vision model generates candidate food and texture observations only.
4. Confirm the foods, food groups, textures, preparation, and possible allergens yourself.
5. Review transparent, age-specific screening prompts and educational guidance with auditable source citations.
6. Escalate red flags or clinical concerns to a clinician or emergency care; do not rely on AI models to evaluate medical emergencies.

## Taxonomy

### Age and developmental stages

| Completed age | Educational focus |
|---|---|
| 0–5 months | Milk feeding; no meal-photo assessment |
| 6–8 months | Complementary foods around 6 months; small amounts and smooth/mashed texture |
| 9–11 months | More texture/variety; safe self-feeding skills |
| 12–23 months | Adapted family foods; diversity across the day |
| 24–59 months | Varied family diet, responsive feeding, appropriate supervision |

### Food groups for 6–23 months

The eight caregiver-selectable groups follow the UNICEF/WHO minimum dietary diversity indicator: breast milk; grains, roots and tubers; pulses, nuts and seeds; dairy; flesh foods; eggs; vitamin-A-rich fruits and vegetables; and other fruits and vegetables. This is a **previous-day** diversity indicator, not a score for one image or a personal diagnosis.

### Additional caregiver-confirmed fields

- Texture: smooth purée, mashed, lumpy/soft pieces, safe finger food, or unclear.
- Preparation: softening/cooking, mashing, pit/bone removal, safe cutting, thinly spread nut butter, pasteurization, honey avoidance under 12 months, and no added sugar.
- Potential allergens: egg, dairy, peanut/tree nut, wheat, soy, fish/shellfish.
- Daily food groups: a separate caregiver log; an image cannot establish daily dietary intake.

## Evaluation protocol

Before changing sources, prompts, model, or rules:

1. Run `python evaluate.py` and `python evaluate_framework.py`.
2. Test all five age bands, photo refusal at 0–5 months, missing confirmation, a potentially allergenic food, a risky preparation, and emergency/red-flag terms.
3. Review at least 30 de-identified meal-photo cases with two qualified pediatric nutrition reviewers. Record agreement for visible-food labels and texture labels separately.
4. Treat all unconfirmed, low-confidence, or ambiguous visual outputs as “unknown”; do not convert them into advice.
5. Track false reassurance and unsafe omission as critical failures. Do not deploy to care without clinical, privacy, security, legal, and regulatory review.

## Source basis

- [WHO: Infant and young child feeding](https://www.who.int/news-room/fact-sheets/detail/infant-and-young-child-feeding)
- [WHO: complementary feeding guideline, 6–23 months (2023)](https://www.who.int/publications/b/70981)
- [UNICEF DATA: diets and IYCF indicators](https://data.unicef.org/topic/nutrition/diets/)
- [WHO: child growth standards](https://www.who.int/news-room/questions-and-answers/item/child-growth-standards)
- [CDC: solid-food introduction](https://www.cdc.gov/infant-toddler-nutrition/foods-and-drinks/when-what-and-how-to-introduce-solid-foods.html)
- [CDC: choking hazards](https://www.cdc.gov/infant-toddler-nutrition/foods-and-drinks/choking-hazards.html)
