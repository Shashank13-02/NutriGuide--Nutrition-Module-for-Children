# NutriGuide: intake screening and caregiver guidance

NutriGuide calculates previous-day feeding indicators from caregiver-confirmed intake.
It supports nutrition screening and education; it does not diagnose malnutrition,
nutrient deficiency, disease, or overall nutritional adequacy.

## What now produces an actual result

The web form works with or without a meal photo. Enter age, the groups actually
consumed yesterday (day and night), breastfeeding status, food-feeding count and
non-breast-milk feeding count. Confirm that the recall is complete.

For **6–23 completed months**, the deterministic engine calculates:

- Minimum dietary diversity (MDD): at least 5 of 8 food groups.
- Minimum meal frequency (MMF): breastfed 6–8m, at least 2 food feeds;
  breastfed 9–23m, at least 3; non-breastfed 6–23m, at least 4 food/milk feeds,
  including at least one solid, semi-solid or soft food feed.
- Minimum milk-feeding frequency (MMFF): at least 2 fluid milk and/or semi-solid yogurt feeds for non-breastfed children.
- Minimum acceptable diet (MAD): MDD and MMF, plus MMFF for non-breastfed children.
- Descriptive egg/flesh-food and zero fruit/vegetable consumption indicators.

Formula belongs to **Dairy**, not Breast milk. Counts are deduplicated. Missing
fields remain unknown; a photo or an incomplete recall does not imply a full-day
record. Conflicting records produce a correction request. Reported urgent symptoms
bypass confirmation and model inference and show referral guidance.

Results are `INDICATORS_MET`, `FEEDING_PATTERN_REVIEW`, `INSUFFICIENT_DATA`, or
`PROFESSIONAL_REVIEW_FLAG`. These are workflow outcomes, not validated individual
Low/Moderate/High risk classes. There is no arbitrary weighted severity score.

**Scope:** target platform 0–72 months; reviewed educational bands 0–59 months;
implemented quantitative intake indicators 6–23 months. Other ages return explicit
insufficient-data/scope messages. Vitamin D scoring, calorie estimation,
micronutrient prediction and clinical growth diagnosis remain outside scope.

Source: [WHO/UNICEF 2021 definitions and measurement methods](https://data.unicef.org/wp-content/uploads/2021/04/Indicators-for-assessing-infant-and-young-child-feeding-practices.pdf),
feeding indicators and their calculation methods. Semi-solid yogurt is included in
the food-feeding count for MMF and the milk-frequency count for MMFF; it is not
added a second time to MMF. The API uses separate `milk_feeds` (fluid) and
`yogurt_feeds` (semi-solid) fields; enter explicit zero when none was consumed.
Honey and added-sugar prompts use
[CDC foods and drinks to avoid or limit](https://www.cdc.gov/infant-toddler-nutrition/foods-and-drinks/foods-and-drinks-to-avoid-or-limit.html).
These population indicators do not validate an individual clinical diagnosis.

## Model roles and selection

| Model | Role and activation |
|---|---|
| Qwen/Qwen3-1.7B | Official text base for task adaptation; local copy in models/qwen3_base. Thinking is disabled through its native chat template. Selection requires qualification. |
| HuggingFaceTB/SmolLM2-360M-Instruct | Automatic text-load fallback if the primary checkpoint fails to load. |
| models/nutrition_evidence_candidate | New task adaptation candidate. Used automatically only after measured held-out selection passes promotion and creates models/deployment.json. |
| models/qwen_nutrition_evidence_candidate | Qwen adaptation candidate; automatic selection requires qualification. The local testing launcher enables an explicit research override. |
| models/nutriguide_adapted_slm | Legacy SmolLM2 source checkpoint. Previously trained on synthetic evaluation cases; not automatically selected or represented as validated. |
| HuggingFaceTB/SmolVLM-500M-Instruct | Meal-photo candidate food and texture observations. Not a text SLM or nutrition classifier. |

All entry points share a lazy runtime: one load per model, separate inference
locks, CUDA/MPS when available, and CPU float32 text inference with bfloat16 loading followed by conversion of individual modules to limit peak memory. Aggressive CPU int8 changed model answers in measured trials and is not enabled by default. Vision CPU inference uses float32. Health reports actual
loaded model, configured model, fallback, loading status and load errors. Model
weights are not downloaded at server startup unless warmup is enabled.

The text model selects the single most relevant reviewed excerpt. A token trie
constrains decoding to one valid ID in a JSON array or an empty array for abstention.
Schema compliance is enforced; answer selection accuracy is measured separately. The app
renders those original statements and canonical deterministic results. Invalid
model output falls back to reviewed guidance. This constrains factual output;
it does not guarantee that the selected statements answer every question. Unqualified
checkpoints and load fallbacks stay inactive for selection; reviewed guidance is
returned instead. `NUTRIGUIDE_ALLOW_UNQUALIFIED=1` is an explicit research override.

Vision uses two short image questions: a person/face check, then a food-name list.
Code validates the list and constructs editable observation fields. Malformed output becomes an empty,
uncertain draft. Person flags block use of the draft; the detector is not a
validated privacy guarantee. Caregivers must use meal-only images and confirm
food groups independently. Photo groups are never automatically counted as a
previous-day record. No real labelled image dataset is included for VLM training
or accuracy claims; vision weights have not been retrained.
The local vision checkpoint is selected automatically when complete. CPU image
processing uses a 1024px longest edge; generation uses deterministic settings and
a repetition penalty. See [VISION_TESTING.md](VISION_TESTING.md) for measured
sample outputs, latency, and remaining identification errors.

## Run locally (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py 8080
```

Open http://127.0.0.1:8080. Curated guidance and intake screening work without
model inference. Generated selection requires cached weights or network access.

Optional overrides:

```powershell
$env:NUTRIGUIDE_TEXT_MODEL = "Qwen/Qwen3-1.7B"
$env:NUTRIGUIDE_VISION_MODEL = "HuggingFaceTB/SmolVLM-500M-Instruct"
$env:NUTRIGUIDE_WARMUP = "1"
# Experimental only: quantify accuracy again before using MLP int8
# $env:NUTRIGUIDE_CPU_INT8 = "1"
```

Models are cached under `.hf_cache`. Overrides are explicit; a qualified local
checkpoint otherwise takes precedence over the default Qwen model.

**Repository contents:** source, training/evaluation data, checkpoint metadata and
browser screenshots are included. Multi-gigabyte `.safetensors` weights, download
temporaries, model caches and the virtual environment are Git-ignored and remain
local. A fresh clone needs model downloads or training before model inference.
Metadata-only checkpoint directories are not usable weights.

Download the pinned official vision model with:

```powershell
.\.venv\Scripts\python.exe download_vision_model.py
```

Once both the trained Qwen candidate and vision weights exist, `./start_testing.ps1`
starts the testing configuration at http://127.0.0.1:8088 with both models warmed
up and offline inference. The text candidate is explicitly enabled for research
testing; this does not change its failed qualification status. Photo suggestions
remain editable and require review. Repeated notices and raw source-ID lines are
removed from guidance cards; the footer notice and readable source links remain.

## Training and honest evaluation

```powershell
.\.venv\Scripts\python.exe build_task_training_data.py
.\.venv\Scripts\python.exe train_model.py --model Qwen/Qwen3-1.7B --output-dir models/qwen_nutrition_evidence_candidate --epochs 2 --batch-size 2
.\.venv\Scripts\python.exe benchmark_models.py --live --text-only --baseline Qwen/Qwen3-1.7B --candidate models/qwen_nutrition_evidence_candidate --promote
.\.venv\Scripts\python.exe run_all_tests.py
```

Training uses reproducible synthetic selections from reviewed local guideline
statements: 60 train prompts and 20 held-out wording prompts. The native tokenizer
chat template and assistant-only loss preserve prompt masking and EOS supervision;
oversize examples are rejected rather than losing the answer to truncation.
The final two actual transformer blocks are adapted. The completed local trial improved valid JSON but reached only 25% exact held-out selection and was rejected; its actual training records and metadata are preserved in the candidate directory. The source is preserved.
The completed Qwen trial trained for 60 steps across two epochs. Exact selection
improved from 50% to 75% on the development questions, but reached 60% on the
separate confirmation set and failed all three unsupported-question abstentions.
It was rejected for automatic activation; the local testing launcher can explicitly enable it. Both trials used synthetic selection labels;
neither establishes clinical screening accuracy. Further qualification requires
reviewed representative questions, supported-answer labels and unsupported examples.
Training computes vocabulary logits only at supervised assistant prediction positions,
reducing Qwen's training memory use without changing which tokens contribute to loss.
Aggregate UNICEF country spreadsheets are not individual diagnostic labels and
are not represented as clinical training examples.

The 20 wording prompts were used during prompt tuning and are now a development
benchmark. A separate 15-prompt confirmation set contains new wording and ages,
including unsupported questions; it is excluded from training and prompt tuning.
Promotion requires 100% valid selection JSON, at least 90% exact development selection,
improvement over the source checkpoint, at least 90% confirmation selection, and
correct abstention on every unsupported confirmation question. Detailed actual generations and
measured latency are saved in `data/eval/model_evaluation_results.json` and
`BENCHMARK_REPORT.md`. A failed candidate stays inactive. These are engineering
selection checks on synthetic labels, not clinical validation. The existing
70 nutrition and 110 photo JSON fixtures remain workflow/safety regression tests;
the latter do not contain 110 real image files. No simulated model scores are used.

## HTTP API

- GET `/api/health`: configured/loaded model identity and readiness.
- GET `/api/bands`, `/api/meal-meta`: reviewed guidance and form taxonomy.
- POST `/api/screen-intake`: computes confirmed previous-day intake indicators.
- POST `/api/query`: curated evidence or constrained model evidence selection.
- POST `/api/analyze-meal`: editable vision draft, never a screening conclusion.
- POST `/api/review-meal`: legacy caregiver-confirmed meal education.
- POST `/api/explain-screening`: explains externally supplied findings; it does
  not verify that the supplied category came from the rule engine. Prefer
  `/api/screen-intake` for actual calculations.

Example intake payload:

```json
{
  "age_months": 10,
  "confirmed": true,
  "recall_complete": true,
  "recall_period": "previous_day",
  "breastfed": true,
  "solid_feeds": 3,
  "daily_groups": ["Breast milk", "Grains, roots and tubers", "Pulses, nuts and seeds", "Eggs", "Other fruits and vegetables"],
  "red_flags": []
}
```

This returns MDD met (5/8), MMF met (3 feeds) and MAD met. It does not establish
clinical nutritional adequacy. Unknown counts should be null, not zero. JSON
requests are limited to 16 MiB. Screening records are processed in memory and
are not stored by the server. Model-load errors are visible through health.
