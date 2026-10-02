# Educational nutrition module: children 0–59 months

## Purpose and boundary

This is a food-literacy and caregiver-education module. It explains evidence-linked, age-appropriate feeding principles after the caregiver confirms the meal record. It is **not** a diagnostic tool, calorie/portion calculator, growth assessor, allergy evaluator, or treatment system.

## Learning flow

1. Select the child's completed age in months.
2. Learn the age-stage foundations: milk feeding, starting complementary foods, texture progression, family-food adaptation, or family eating.
3. Upload a **meal-only** image, if applicable. The vision model makes a draft visual description only.
4. Confirm the foods, food groups, textures, preparation, and possible allergens yourself.
5. Review transparent, age-specific educational and safety prompts with sources.
6. Escalate red flags to a clinician or emergency care; do not ask the model to decide.

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
