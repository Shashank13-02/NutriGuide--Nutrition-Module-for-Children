# NutriGuide measured model evaluation

Only real generated outputs are scored. No clinical accuracy or vision accuracy is established.

JSON syntax is enforced by constrained decoding; exact evidence selection measures the model's choice separately.

| Model | Development prompts | Valid JSON | Exact evidence selection | Mean latency |
|---|---:|---:|---:|---:|
| qwen3_base | 20 | 100.0% | 50.0% | 12.17s |
| qwen_nutrition_evidence_candidate | 20 | 100.0% | 75.0% | 11.69s |

Baseline measurements reused from `data\eval\qwen_fewshot_evaluation.json` after checking identical prompt hash, checkpoint, decoding and CPU precision.


Candidate passed promotion gate: False. Activated: False.

The 20 wording prompts were used as a synthetic development benchmark during task optimization. They are not clinical validation.

Separate 15-prompt confirmation set: failed. Exact selection 60.0%; JSON validity 100.0%; correct unsupported-question abstention 0/3. The set was excluded from training and prompt tuning.

Vision evaluation requires real meal-only image files with independently reviewed food and person-presence labels. Existing JSON fixtures are workflow tests.

Legacy adapted weights were previously trained on synthetic evaluation cases; earlier evaluation-case accuracy is invalid for measuring generalization.
