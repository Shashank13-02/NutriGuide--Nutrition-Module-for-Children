# NutriGuide: Child Nutrition Screening & Caregiver Education Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![SmolLM2](https://img.shields.io/badge/SLM-SmolLM2--360M--Instruct-orange.svg)](https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct)
[![SmolVLM](https://img.shields.io/badge/VLM-SmolVLM--500M--Instruct-purple.svg)](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct)
[![Guidelines](https://img.shields.io/badge/Clinical%20Grounding-WHO%20%7C%20UNICEF%20%7C%20CDC-green.svg)](https://www.who.int/news-room/fact-sheets/detail/infant-and-young-child-feeding)
[![Privacy](https://img.shields.io/badge/Execution-100%25%20Local%20%26%20Private-success.svg)](#privacy--safety-boundaries)

NutriGuide is being extended into a nutrition-intake screening platform for children from birth to 6 years of age. The platform is designed to identify dietary patterns that may warrant attention using age-aware feeding information, caregiver-confirmed food intake, food-group analysis, and deterministic screening logic.

The platform is a screening and educational support tool. It does not diagnose malnutrition, nutrient deficiencies, disease, or other medical conditions.

The architecture combines **Nutrition Screening + Caregiver Education**: deterministic screening rules evaluate reported intake against authoritative pediatric guidelines, while an SLM conversational assistant provides downstream evidence-grounded explanations.

---

## Screening vs Diagnosis

| Dimension | Nutrition Screening (This Platform) | Medical / Clinical Diagnosis (Healthcare Provider) |
|---|---|---|
| **Goal** | Early identification of dietary intake patterns that may warrant attention or review. | Definitive determination of the presence or absence of clinical disease or pathology. |
| **Data Evaluated** | Caregiver-reported food items, meal cadence, dietary diversity (5-of-8 groups), textures, preparation safety. | Physical examination, clinical history, anthropometrics (growth curves, stunting/wasting), biochemical & laboratory tests (blood panels, serum ferritin, micronutrient levels). |
| **Output Wording** | Screening concern categories (e.g., *Low concern*, *Limited iron-rich food intake*, *Meal pattern requires review*, *Insufficient data*). | Clinical diagnostic statements (e.g., *Severe acute malnutrition*, *Iron-deficiency anemia*, *Failure to thrive*). |
| **Role of AI** | Observation proposal (vision model) and explanation generation (language model) strictly bounded by deterministic rules. | Never replaces a physician, pediatrician, or registered pediatric dietitian. |
| **Action** | Recommending positive feeding adjustments, dietary diversity improvements, or prompt referral to healthcare services. | Formulating medical treatment, prescribing therapeutic supplements, or specialized medical diets. |

---

## Current Development Status

- **Phase 1 Transition:** The repository is transitioning from an educational nutrition module to a structured child nutrition screening platform.
- **Target Population Scope:** Children from birth through 6 completed years (0 to 72 completed months).
- **Current Implemented Rules:** Currently implemented evidence bands cover 0 to 59 completed months. Rules for 60 to 72 completed months will be designed in subsequent implementation phases.
- **Screening Engine Status:** The deterministic Low/Moderate/High scoring engine has not yet been implemented in Phase 1. Phase 1 defines product boundaries, terminology, and safety gates without inventing arbitrary scores.
- **Vitamin Scope Exclusion:** **Vitamin D assessment is not part of the current implementation scope.** The system does not compute Vitamin D scores, track Vitamin D supplements, or predict Vitamin D deficiency. Vitamin-specific screening will be evaluated separately in a future phase.

---

## Table of Contents

1. [Screening vs Diagnosis](#screening-vs-diagnosis)
2. [Current Development Status](#current-development-status)
3. [Important Pediatric & Safety Boundaries](#important-pediatric--safety-boundaries)
4. [What NutriGuide Does](#what-nutriguide-does)
5. [The 8-Dimensional Pediatric Nutrition Taxonomy](#the-8-dimensional-pediatric-nutrition-taxonomy)
6. [System Architecture](#system-architecture)
7. [Models & Hardware Acceleration](#models--hardware-acceleration)
8. [Repository Structure](#repository-structure)
9. [Getting Started & Installation](#getting-started--installation)
10. [Running the Applications](#running-the-applications)
    - [Unified Web Application (Port 8080)](#1-unified-web-application-recommended)
    - [Gradio Photo Companion (Port 8899)](#2-standalone-gradio-photo-companion)
    - [Command-Line Evidence Inspector](#3-command-line-evidence-inspector)
11. [Automated Verification & Evaluation Suites](#automated-verification--evaluation-suites)
12. [REST API Documentation](#rest-api-documentation)
13. [Authoritative Source Registry](#authoritative-source-registry)

---

## Important Pediatric & Safety Boundaries

1. **Non-Diagnostic:** The platform does not diagnose disease, malnutrition, or specific nutrient deficiencies.
2. **Single-Meal Limitation:** A single meal or photo cannot determine a child's overall nutritional adequacy; dietary diversity is evaluated across full-day patterns.
3. **Deterministic Primacy:** AI models never invent or override screening categories; deterministic clinical rules govern all evaluations.
4. **Mandatory Confirmation:** Observations from the vision model are drafts that require caregiver confirmation before guidance is issued.
5. **Red-Flag Escalation:** Potential medical emergencies or severe feeding distress are immediately directed to clinical or emergency care.

---

## What NutriGuide Does

NutriGuide provides a modern, dual-tab web interface designed with sleek glassmorphic aesthetics and responsive controls:

### Tab 1: Nutrition Assistant (SLM Chat & Diversity Guidelines)
- **Continuous Age Slider (0–59 Months)**: Smoothly transitions through 5 pediatric developmental stages with 1-click preset buttons (`0–5m`, `6–8m`, `9–11m`, `12–23m`, `24–59m`).
- **Interactive Food & Variety Guidelines Explorer**:
  - **Variety Target Banner**: Explains the exact nutritional diversity focus for the selected month (e.g., UNICEF's 5-of-8 groups indicator for 12–23m).
  - **Meal Cadence Indicator**: Highlights age-appropriate daily meal and snack frequencies.
  - **Recommended Food Category Cards**: Shows food group names, micronutrient rationales (iron, zinc, vitamins A & C), and safe food examples.
  - **Safe Textures & Foods to Avoid**: Clearly articulates developmental texture milestones alongside hazard items (e.g., honey under 12 months, unpasteurized products).
- **Dual Inference Engine**:
  - **SmolLM2-360M Generated**: Runs prompt-grounded local SLM text generation on Apple Silicon MPS or CPU.
  - **Curated Evidence Context**: Instant zero-latency retrieval of exact WHO and CDC evidence sentences.
- **Evidence Drawer & Citations**: Clickable source cards linking directly to normative publications from the WHO and CDC.

### Tab 2: Meal Photo Companion (Vision AI)
- **Meal Image Input**: Drag-and-drop or file upload for plate, bowl, or high-chair tray photos.
- **Built-In Sample Meals**:
  - **Sample 1**: Mashed Lentils & Rice (Khichdi) in a bowl (10 months) — pre-linked to real food photography.
  - **Sample 2**: Steamed Carrots & Oatmeal (14 months).
- **Local Vision Analysis**: 1-click inference using `SmolVLM-500M` to propose visible food names and texture cues.
- **8-Step Caregiver Review Form**: Enables the caregiver to edit visible foods, confirm food groups, textures, preparation steps, and allergen exposure.
- **UNICEF Minimum Dietary Diversity Indicator**:
  - Live **0–8 progress bar** tracking daily dietary diversity.
  - Dynamically updates as daily food groups are selected, visually celebrating when the target of &ge;5 groups is reached.
- **Safe Educational Interpretation**: Compiles caregiver-verified meal records into tailored feeding guidance and choking hazard prompts.

---

## The 8-Dimensional Pediatric Nutrition Taxonomy

NutriGuide organizes pediatric nutrition around an 8-dimensional framework grounded in normative WHO, UNICEF, and CDC clinical standards:

| # | Category | Examples / Formats | Why It Matters in Pediatric Care | Enforced In |
|---|---|---|---|---|
| **1** | **Age / development** | `0–5`, `6–8`, `9–11`, `12–23`, `24–59` months | Determines whether complementary feeding and certain textures are developmentally appropriate. | `data/nutrition_knowledge.json`, `app.py`, `server.py` |
| **2** | **Food groups** | Breast milk; grains/roots/tubers; pulses/nuts/seeds; dairy; flesh foods; eggs; vitamin-A-rich fruit/veg; other fruit/veg | WHO/UNICEF 6–23-month dietary diversity framework uses **8 distinct groups** to prevent micronutrient deficiencies. | `nutrition_engine.py`, `server.py`, `index.html` |
| **3** | **Texture** | Purée, mashed, lumpy/soft pieces, safe finger food, family-food texture | Must fit oral motor feeding skill—**not age alone**. Prevents choking while advancing self-feeding development. | `nutrition_engine.py`, `meal_photo_app.py` |
| **4** | **Preparation / safety** | Cooked, peeled, mashed, thinly spread, cut lengthwise / quartered | Choking hazard prevention. Round firm foods (grapes, cherry tomatoes, hot dogs) must be quartered lengthwise; hard vegetables steamed or grated. | `nutrition_engine.py`, `evaluate_meal.py` |
| **5** | **Allergen flag** | Egg, dairy, peanut/tree nut, wheat, soy, fish/shellfish | Prompts early, single-ingredient introduction at home with guidance to consult clinician if personal or family history of atopy exists. | `nutrition_engine.py`, `data/nutrition_knowledge.json` |
| **6** | **Added ingredients** | Honey, added sugar, excess salt, unpasteurized/raw foods | Enforces strict toxicological and clinical limits: **Honey is strictly forbidden <12 months** (infant botulism); **zero added sugars <24 months**. | `data/nutrition_knowledge.json`, `app.py` |
| **7** | **Meal pattern / cadence** | 2–3 meals (6–8m); 3–4 meals + 1–2 snacks (9–23m); 3 meals + 2 snacks (24–59m) | A single plate cannot reflect daily nutritional adequacy. Supports day-level feeding cadence complementary to milk intake. | `data/nutrition_knowledge.json`, `index.html` |
| **8** | **Confidence / verification** | Clearly visible / uncertain / caregiver-corrected | **Prevents treating model guesses as facts**. VLM observations are treated purely as drafts requiring mandatory caregiver confirmation. | `server.py`, `meal_photo_app.py`, `static/app.js` |

---

## System Architecture: SLM as Communicator, Not Decision Maker

A core architectural principle of NutriGuide is:
> **SLM = Communication & Caregiver Explanation, NOT Decision Maker**

The SLM is **strictly prohibited** from calculating, modifying, upgrading, or downgrading screening risk. Screening risks and clinical rule flags are computed entirely by a deterministic pediatric rule engine. The SLM receives the structured output and explains it in empathetic, accessible language to the caregiver:

```
Deterministic Rule Engine Output:
{
  "screening_result": "MODERATE_SCREENING_CONCERN",
  "findings": ["Limited dietary diversity: 2 of 5 recommended food groups reported today", "High-sodium snack observed"]
}
                          │
                          ▼
            Small Language Model (SLM)
         "Explain this to the caregiver in simple language."
                          │
                          ▼
Empathetic, clear caregiver guidance with actionable next steps (No diagnosis, no score alteration)
```

```mermaid
flowchart TD
    User([Caregiver / User]) -->|Enters Query| InputQuery[Input Question & Age]
    User -->|Uploads Plate Image| InputPhoto[Meal Photo Only]

    subgraph SafetyGate [Safety & Privacy Layer]
        InputQuery --> RedFlagGate{Red-Flag Gate}
        RedFlagGate -->|Urgent Symptoms| DirectER[Immediate Medical Emergency Advice]
        InputPhoto --> ChildCheck{Child Face/Body Check}
        ChildCheck -->|Person Detected| BlockImage[Block Photo & Request Meal Only]
    end

    subgraph VisionPipeline [VLM Meal Photo Pipeline]
        ChildCheck -->|Meal Only| SmolVLM[HuggingFaceTB/SmolVLM-500M-Instruct]
        SmolVLM --> DraftObs[Draft Food & Texture Observations]
        DraftObs --> CaregiverForm[Caregiver Review & Confirmation Form]
    end

    subgraph DeterministicEngine [Deterministic Screening & Rule Engine (Decision Maker)]
        CaregiverForm -->|Caregiver Confirms| RuleEngine[Deterministic Screening Engine]
        RuleEngine --> StructuredResult["Structured Output: { screening_result, findings }"]
    end

    subgraph SLMCommunication [SLM Explanation Layer (Communicator)]
        StructuredResult --> SLMExplanation[SmolLM2-360M / Qwen3-1.7B]
        RetrieveKB[Retrieve Age-Band Knowledge] --> SLMExplanation
        SLMExplanation --> CaregiverGuidance["Caregiver-Friendly Explanation (No Risk Calculation)"]
    end

    CaregiverGuidance --> UI[Glassmorphic Web App UI :8080]
    DirectER --> UI
    BlockImage --> UI
```

---

## Models & Hardware Acceleration

| Model | Hugging Face ID | License | Parameters | Role in Architecture |
|---|---|---|---|---|
| **SmolLM2** *(Current)* | `HuggingFaceTB/SmolLM2-360M-Instruct` | Apache 2.0 | ~360 Million | **Communication & explanation only** (Explaining deterministic findings to caregivers) |
| **SmolVLM** *(Current)* | `HuggingFaceTB/SmolVLM-500M-Instruct` | Apache 2.0 | ~500 Million | Zero-shot meal-photo candidate draft observations (Requires caregiver confirmation) |

### Model Upgrade Roadmap

1. **Text SLM Upgrade Benchmark (Post-Deterministic Engine):**
   - **Candidate**: [`Qwen/Qwen3-1.7B`](https://huggingface.co/Qwen/Qwen3-1.7B) (Apache 2.0).
   - **Role**: Benchmark against `SmolLM2-360M` strictly for communication clarity, caregiver empathy, and prompt constraint adherence.
   - **Timing**: Benchmarked *after* the deterministic screening rule engine is fully tested and verified. The model will never calculate risk.

2. **Phase 19 — Vision Model Upgrade (Separate Evaluation):**
   - Vision quality is critical for accurate meal plate observation.
   - **Candidates**:
     - [`Qwen/Qwen3-VL-2B-Instruct`](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct) (Apache 2.0)
     - [`Qwen/Qwen3-VL-4B-Instruct`](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) (Apache 2.0)
   - **Comparison Strategy**: `SmolVLM-500M` vs `Qwen3-VL-2B` vs `Qwen3-VL-4B`.
   - **Benchmark Criteria**: Evaluated directly against the curated **pediatric meal-image dataset** (plate/bowl food identification and texture cues), rather than generic multimodal benchmarks.

- **Local Cache Management**: Models are downloaded once and cached in `./.hf_cache` via `HF_HOME="$PWD/.hf_cache"`. The application can run completely air-gapped without internet access once weights are cached.
- **Apple Silicon Acceleration**: On macOS devices with M1/M2/M3/M4 chips, PyTorch automatically binds to the Metal Performance Shaders (`mps`) backend in `float16`, providing text generation in ~3s and vision inference in ~2s.


---

## Repository Structure

```
NutriGuide--Nutrition-Module-for-Children/
├── SCREENING_MODULE.md         # Product boundary, screening taxonomy & safety specification
├── screening_constants.py      # Centralized screening terminology, age constants & disclaimers
├── app.py                      # Core CLI application & prompt-grounding engine
├── server.py                   # High-performance HTTP server & REST API
├── meal_photo_app.py           # Standalone Gradio interface for meal photo reviews
├── nutrition_engine.py         # Deterministic pediatric rule engine & taxonomy validator
├── requirements.txt            # Python dependencies (transformers, torch, pillow, gradio)
├── README.md                   # Comprehensive platform documentation
├── EDUCATIONAL_MODULE.md       # Caregiver education curriculum & clinical rationale
│
├── data/
│   ├── nutrition_knowledge.json # Ground truth evidence across all pediatric age bands
│   └── eval/                   # Benchmark evaluation dataset suite
│       ├── deterministic_nutrition_cases.json # 70 pediatric cases (CNNS, NFHS-5, UNICEF, NHANES, FITS)
│       └── meal_photo_cases.json              # 110 meal photos (IndianFoodNet30, UECFoodPix, UEC-Food)
│
├── static/                     # Web application frontend assets
│   ├── index.html              # Modern, semantic single-page application markup
│   ├── style.css               # Rich glassmorphic dark theme (vanilla CSS, responsive)
│   ├── app.js                  # Client-side reactivity, slider sync, and API wiring
│   └── samples/                # Pre-packaged sample meal images
│       ├── meal_lentils_rice.jpg    # Sample 1: Mashed lentils & rice (10 months)
│       └── meal_carrots_oatmeal.jpg # Sample 2: Steamed carrots & oatmeal (14 months)
│
├── evaluate.py                 # Automated regression suite for SLM knowledge context
├── evaluate_meal.py            # Automated test suite for meal-photo review logic
├── evaluate_framework.py       # Automated test suite for the 8-category taxonomy
├── evaluate_screening_boundaries.py # Automated verification of screening safety & boundaries
└── evaluate_dataset.py         # Comprehensive evaluation runner (70 deterministic + 110 photo cases)
```

---

## Getting Started & Installation

### Prerequisites
- Python **3.10** or higher
- pip and virtual environment support (`python3 -m venv`)
- ~3.5 GB of free disk space for PyTorch and cached Hugging Face model weights

### 1. Set Up Virtual Environment
```bash
# Navigate to the module directory
cd outputs/nutrition_slm_module

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies into virtual environment
pip install -r requirements.txt
```

---

## Running the Applications

### 1. Unified Web Application (Recommended)

The primary application combines both the **Nutrition Assistant (SLM Chat)** and the **Meal Photo Companion (VLM)** into a single, unified web interface:

```bash
# Start the web server (defaults to port 8080)
HF_HOME="$PWD/.hf_cache" .venv/bin/python server.py 8080
```

Open your browser and navigate to:
```
http://localhost:8080
```

- **Tab 1: Nutrition Assistant**:
  - Drag the completed-months slider from 0 to 59.
  - Review the dynamically rendered variety targets, meal cadence, and food categories.
  - Ask questions in either **SmolLM2-360M Generated** mode or **Curated Evidence** mode.
  - Click **"📋 Framework Taxonomy"** in the top bar to inspect the complete 8-dimensional architecture table.
- **Tab 2: Meal Photo Companion**:
  - Click **"🥣 Sample 1: Mashed Lentils & Rice (10m)"** or upload an image.
  - Click **"1. Analyze Photo with SmolVLM-500M"** to run on-device vision inference.
  - Edit or confirm the observations in the caregiver review form.
  - Watch the **UNICEF Minimum Dietary Diversity Indicator** calculate the day-level score (target: &ge;5 of 8 groups).
  - Click **"8. Get Age-Specific Educational Guidance"** to generate the evidence-backed feeding interpretation.

---

### 2. Standalone Gradio Photo Companion

If you prefer testing the meal photo companion inside Gradio's standard interface:

```bash
HF_HOME="$PWD/.hf_cache" .venv/bin/python meal_photo_app.py
```

Navigate to `http://127.0.0.1:8899` (or the port defined by `NUTRIGUIDE_PORT`).

---

### 3. Command-Line Evidence Inspector

You can inspect the exact evidence context or run SLM text generation directly from your terminal:

```bash
# Inspect curated evidence for a 7-month-old (Zero model download needed)
.venv/bin/python app.py --age-months 7 --question "What is safe to introduce?" --context-only

# Run SmolLM2-360M inference for an 18-month-old
HF_HOME="$PWD/.hf_cache" .venv/bin/python app.py --age-months 18 --question "What textures and meal frequency should we offer?"
```

---

## Automated Verification & Evaluation Suites

NutriGuide includes five deterministic evaluation test suites to prevent regressions, enforce screening boundaries, test age transitions, and verify compliance with clinical guidelines:

```bash
# 1. Knowledge Base & Context Checks (5 tests)
python evaluate.py

# 2. Meal-Photo Workflow & Policy Checks (4 tests)
python evaluate_meal.py

# 3. 8-Dimensional Educational Framework Checks (8 tests)
python evaluate_framework.py

# 4. Screening Safety & Boundary Verification Suite (Phase 1 Boundaries)
python evaluate_screening_boundaries.py

# 5. Comprehensive Pediatric Dataset Benchmark Suite (70 deterministic + 110 meal photos)
python evaluate_dataset.py
```

All automated tests run deterministically without requiring network access or external API calls.

---

## Ground Truth & Vision Evaluation Datasets

NutriGuide's 180 evaluation benchmark cases (`data/eval/`) are systematically grounded in normative pediatric health surveys and computer vision food recognition datasets:

### 1. Deterministic Nutrition Datasets & Clinical Standards (0–6 Years)

- **[CNNS 2016–18 (Government of India – NHM)](https://nhm.gov.in/index1.php?lang=1&level=2&lid=713&sublinkid=1332):** Comprehensive National Nutrition Survey reports and [CNNS Data Note](https://healthnutritionindia.in/reports/documents/25/CNNS-v1.0-Data-Note-for-MoHFW.pdf) (`CNNS_04`, `CNNS_59`). Prime India-specific benchmark for stunting, wasting, micronutrient exposure, and food group transitions from infancy to school age.
- **[NFHS-5 India 2019–21 (World Bank Microdata)](https://microdata.worldbank.org/catalog/4482) & [DHS India Report](https://www.dhsprogram.com/publications/publication-FR375-DHS-Final-Reports.cfm):** Benchmark for infant and young child feeding (IYCF) indicators: exclusive breastfeeding under 6m, timely complementary food introduction (6–8m), minimum meal frequency, and junk food exposure.
- **[UNICEF IYCF Datasets](https://data.unicef.org/resources/dataset/infant-young-child-feeding/) & [Indicator Portal](https://data.unicef.org/topic/nutrition/infant-and-young-child-feeding/):** Global WHO/UNICEF standards for 0–23 months: Minimum Dietary Diversity (MDD &ge;5 of 8 food groups), Minimum Acceptable Diet (MAD), and zero-fruit-or-vegetable consumption.
- **[NHANES Dietary (2021–23 & Archive – CDC/NCHS)](https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx?Component=Dietary&Cycle=2021-2023):** Detailed 24-hour individual dietary recall records, food portion distributions, sodium, and added sugars, particularly for children aged 2–6 years (24–72 months).
- **[FITS (Feeding Infants and Toddlers Study)](https://www.nestlenutrition-institute.org/academies/toddler-hub/fits):** 24-hour dietary-recall methodology, developmental texture progression, and choking hazard exposure in infants and toddlers.

### 2. Vision Recognition Benchmark Datasets for Meal Photos

- **[IndianFoodNet30 (Roboflow Universe)](https://universe.roboflow.com/indianfoodnet/indianfoodnet) & [2026 Frontiers in Computer Science Study](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2026.1753764/full):** Primary benchmark for multi-dish Indian meals (khichdi, dal, rice, roti, sabzi, curd, paneer, thalis).
- **[UECFoodPix / UECFoodPixComplete](https://mm.cs.uec.ac.jp/uecfoodpix/):** Multi-food detection and pixel-level segmentation on plates, divided trays, and bowls.
- **[UEC-Food100 / 256](https://mm.cs.uec.ac.jp/uecfoodpix/):** Multi-category food recognition benchmarking across diverse international food preparations.

### 3. Aggressive Age Boundary Pair Testing Matrix

Bugs at age boundaries in pediatric systems are clinically hazardous. NutriGuide aggressively tests all 7 critical boundaries:
- **5m vs 6m:** Exclusive milk feeding (no solids/water) vs early complementary start (smooth purees, iron-rich foods, 2–3 meals).
- **8m vs 9m:** 2–3 meals (smooth/mashed) vs 3–4 meals + snacks (lumpy textures, finger food pincer grasp).
- **11m vs 12m:** Honey strictly prohibited (infant botulism) & cow's milk beverage warning vs honey safe & whole cow's milk drink allowed.
- **23m vs 24m:** Zero added sugar strict rule (<24m) & whole milk vs family diet & low-fat milk transition option.
- **35m vs 36m:** Late toddler rotary chewing fatigue & acute choking hazards vs 3-year preschool milestone (all 20 deciduous teeth).
- **59m vs 60m:** Active Phase 1 rule upper limit (24–59m) vs School-age Phase 2 deferred scope (60–72m).
- **71m vs 72m:** Near target scope limit (5y 11m) vs 6 completed years exact scope upper boundary.


---

## REST API Documentation

The server exposes a clean JSON REST API on `http://localhost:8080`:

### `GET /api/health`
Checks readiness of the SLM and VLM pipelines along with screening metadata.
```json
{
  "status": "ok",
  "module_type": "nutrition_screening_support",
  "scope": "children_0_to_6_years",
  "target_scope": "0_to_72_months",
  "implemented_rule_scope": "0_to_59_months",
  "screening_engine_status": "under_development",
  "diagnostic": false,
  "vitamin_d_screening_enabled": false,
  "screening_notice": "This module supports nutrition screening and education. It does not diagnose malnutrition, nutrient deficiency, or disease.",
  "lm_ready": true,
  "vlm_ready": true,
  "lm_loading": false,
  "vlm_loading": false
}
```

### `GET /api/bands`
Returns all 5 implemented age bands with full variety targets, meal cadence, food categories, safe textures, foods to avoid, and screening scope metadata.

### `GET /api/meal-meta`
Returns allowable food groups (8 UNICEF groups), textures, preparation safety flags, allergen categories, and screening disclaimers.

### `POST /api/query`
Executes an age-specific question query against either SmolLM2 or the curated evidence context, returning non-diagnostic screening metadata.
**Request Body:**
```json
{
  "age_months": 10,
  "question": "What textures should my 10-month-old eat?",
  "use_model": true
}
```

### `POST /api/analyze-meal`
Processes an uploaded base64 image or a pre-packaged sample meal via `SmolVLM-500M` to produce candidate food and texture observations requiring caregiver confirmation.
**Request Body:**
```json
{
  "sample": "meal_lentils_rice.jpg"
}
```
*or*
```json
{
  "image": "data:image/jpeg;base64,..."
}
```

### `POST /api/review-meal`
Evaluates caregiver-confirmed meal observations against pediatric dietary rules, returning screening guidance and non-diagnostic notices.
**Request Body:**
```json
{
  "age_months": 10,
  "foods": "mashed lentils, soft rice",
  "groups": ["Grains, roots and tubers", "Pulses, nuts and seeds"],
  "textures": ["Mashed", "Smooth puree"],
  "preparation": ["Cooked/softened", "Mashed/pureed"],
  "allergens": [],
  "daily_groups": ["Breast milk", "Grains, roots and tubers", "Pulses, nuts and seeds"],
  "confirmed": true
}
```

### `POST /api/explain-screening`
Implements the core **SLM as Communicator** pattern. Accepts structured output produced by the deterministic screening rule engine and uses the SLM strictly to explain the findings to the caregiver in empathetic, simple language (without calculating or altering screening risk).
**Request Body:**
```json
{
  "age_months": 14,
  "screening_result": "MODERATE_SCREENING_CONCERN",
  "findings": [
    "Limited dietary diversity: only 2 of 5 recommended food groups reported today.",
    "High-sodium processed snack observed."
  ],
  "professional_review_flag": false,
  "use_model": false
}
```
**Response Body:**
```json
{
  "screening_result": "MODERATE_SCREENING_CONCERN",
  "role": "communication_and_explanation",
  "explanation": "Screening Result: MODERATE_SCREENING_CONCERN\n\nKey Screening Observations:\n- Limited dietary diversity: only 2 of 5 recommended food groups reported today.\n- High-sodium processed snack observed.\n\nCaregiver Guidance Summary:\nFor a child aged 14 months, feeding guidelines emphasize age-appropriate variety, responsive feeding, and regular meal cadence.\n- A single meal or photo cannot determine overall nutritional adequacy. Dietary diversity is evaluated across full-day patterns.\n- Note: Vitamin D-specific screening is outside the scope of this module.\n\nScreening Notice: This module supports nutrition screening and education. It does not diagnose malnutrition, nutrient deficiency, or disease.",
  "decision_maker": "deterministic_rule_engine",
  "screening_notice": "This module supports nutrition screening and education. It does not diagnose malnutrition, nutrient deficiency, or disease."
}
```

---

## Authoritative Source Registry

All educational guidance, safety rules, and dietary recommendations in NutriGuide are grounded in official, peer-reviewed clinical guidelines:

| Source ID | Reference Title | Authoring Body | Clinical Topic Covered |
|---|---|---|---|
| **WHO-IYCF** | [Infant and Young Child Feeding](https://www.who.int/news-room/fact-sheets/detail/infant-and-young-child-feeding) | World Health Organization | Exclusive breastfeeding, complementary feeding timing, meal cadence, responsive feeding |
| **WHO-BF** | [Breastfeeding Q&A](https://www.who.int/news-room/questions-and-answers/item/breastfeeding) | World Health Organization | Definition of exclusive breastfeeding; zero water in first 6 months |
| **WHO-CF-2023** | [Guideline for Complementary Feeding (6–23 Months)](https://www.who.int/publications/b/70981) | World Health Organization | Normative global complementary feeding standards |
| **WHO-EARLY-FOODS** | [Recommended Food for the Very Early Years](https://www.who.int/news-room/questions-and-answers/item/child-health-recommended-food-for-the-very-early-years) | World Health Organization | Texture progression, energy density, transition to family table foods |
| **UNICEF-DIET** | [Infant and Young Child Diets](https://data.unicef.org/topic/nutrition/diets/) | UNICEF Data | 5-of-8 food-group Minimum Dietary Diversity (MDD) population indicator |
| **WHO-GROWTH** | [Child Growth Standards](https://www.who.int/news-room/questions-and-answers/item/child-growth-standards) | World Health Organization | 0–5 year growth monitoring principles |
| **CDC-SOLIDS** | [When, What, and How to Introduce Solid Foods](https://www.cdc.gov/infant-toddler-nutrition/foods-and-drinks/when-what-and-how-to-introduce-solid-foods.html) | Centers for Disease Control and Prevention | Developmental readiness cues, texture progression, single-allergen introduction |
| **CDC-CHOKING** | [Choking Hazards Prevention](https://www.cdc.gov/infant-toddler-nutrition/foods-and-drinks/choking-hazards.html) | Centers for Disease Control and Prevention | Food preparation safeguards (quartering grapes lengthwise, steaming hard foods), active supervision |
| **CDC-LIMITS** | [Foods and Drinks to Avoid or Limit](https://www.cdc.gov/infant-toddler-nutrition/foods-and-drinks/foods-and-drinks-to-avoid-or-limit.html) | Centers for Disease Control and Prevention | Strict infant botulism prohibition on honey (<12m); zero added sugars (<24m) |
| **CDC-FOOD-SAFETY**| [Safer Food Choices Under 5](https://www.cdc.gov/food-safety/foods/children-under-5.html) | Centers for Disease Control and Prevention | Foodborne illness risk reduction; pasteurization mandates |

---

## License & Attribution

This educational prototype is developed for research and learning on small language model safety bounding. Model weights are subject to the respective Hugging Face community licenses:
- [SmolLM2-360M-Instruct License (Apache 2.0)](https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct)
- [SmolVLM-500M-Instruct License (Apache 2.0)](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct)
