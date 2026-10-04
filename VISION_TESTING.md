# Meal-photo testing

The browser uses a local copy of `HuggingFaceTB/SmolVLM-500M-Instruct`, pinned to revision `a7da5b986cb59b408707209984f360a5f4ad7e47`. The weight download was verified against the official SHA-256 metadata. Inference runs offline; photos are not sent to Hugging Face.

The 500M model did not follow the previous multi-field JSON instruction on either sample image. That prompt produced repeated food names or incomplete text. The new workflow asks two short visual questions: whether a person/face is visible, then a list of visible foods. Code validates the list and builds the editable observation fields. Unknown person-check output and malformed food lists abstain. Person detection has not been validated as a privacy filter.

CPU preprocessing now uses a 1024px longest edge instead of the processor's default 2048px, retaining a global image and detail crops. Generation settings now reach the model through the pipeline's `generate_kwargs`; deterministic generation and a repetition penalty prevent the previous repeated-list behavior in the measured samples.

Measured food-list calls took 17.22 seconds for the divided plate and 15.42 seconds for the yellow bowl after loading. Results were `Carrots, Avocado, Rice` and `Yellow soup`. The plate's grain portion is labeled oatmeal in the sample; the model's rice suggestion illustrates a remaining identification error. The bowl's precise ingredients cannot be established visually. These two images are smoke checks, not an accuracy benchmark.

All food names remain suggestions. Food identity, preparation, allergens, texture, and previous-day intake need caregiver review. Photo output does not establish softness, portion size, nutrients, or a diagnosis. No new vision-model weight training was performed; this update improves inference and the review workflow. Representative labeled meal photos are still needed for task-specific fine-tuning and accuracy validation.

Run `start_testing.ps1` to start both local models on port 8088. Use **Intake Screening & Meal Review**, upload a meal-only photo or select a sample, then press **Analyze Meal Photo**.

Measured artifacts: `data/eval/vision_live_smoke_results.json`, `data/eval/vision_caption_probe.json`, and `data/eval/vision_api_sample_result.json`.
