"""Measure actual held-out evidence selection; never simulate model accuracy.

The existing meal-photo JSON contains descriptions and drafted outputs, not
labelled image files. It can test workflow contracts, not vision accuracy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import time
import subprocess
import sys
import tempfile
from pathlib import Path
from model_runtime import parse_selection, selection_constraint

ROOT = Path(__file__).parent.resolve()


def evaluate_model(model_path, records, cpu_int8=False):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(min(4, torch.get_num_threads()))
    if cpu_int8:
        from cpu_model import cpu_text_components
        print(f"Loading {model_path} with experimental per-channel int8 CPU MLP modules...", flush=True)
        components = cpu_text_components(model_path, quantize_mlp=True)
        model, tokenizer = components["model"], components["tokenizer"]
    else:
        from cpu_model import cpu_text_components
        components = cpu_text_components(model_path)
        model, tokenizer = components["model"], components["tokenizer"]
    model.eval()
    outputs = []
    for record in records:
        prompt = tokenizer.apply_chat_template(record["messages"], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        inputs = tokenizer(prompt, return_tensors="pt")
        start = time.perf_counter()
        with torch.inference_mode():
            tokens = model.generate(**inputs, max_new_tokens=48, do_sample=False, repetition_penalty=1.05,
                                    prefix_allowed_tokens_fn=selection_constraint(tokenizer, inputs["input_ids"].shape[1], len(record["evidence"])),
                                    pad_token_id=tokenizer.eos_token_id)
        raw = tokenizer.decode(tokens[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        try:
            prediction = parse_selection(raw, len(record["evidence"]))
            valid = True
        except (ValueError, TypeError):
            prediction, valid = [], False
        outputs.append({"id": record["id"], "target": record["target"], "prediction": prediction,
                        "raw": raw, "schema_valid": valid, "exact_match": prediction == record["target"],
                        "latency_seconds": time.perf_counter()-start})
        print(f"{Path(model_path).name} {record['id']} valid={valid} correct={prediction == record['target']}", flush=True)
    n = len(outputs)
    return {"model": str(model_path), "precision": "mlp_per_channel_int8_cpu" if cpu_int8 else "float32_cpu", "count": n,
            "schema_valid_rate": sum(r["schema_valid"] for r in outputs)/n,
            "exact_selection_rate": sum(r["exact_match"] for r in outputs)/n,
            "mean_latency_seconds": sum(r["latency_seconds"] for r in outputs)/n,
            "outputs": outputs}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--baseline", default=str(ROOT / "models" / "nutriguide_adapted_slm"))
    parser.add_argument("--baseline-report", type=Path, help="Reuse measured baseline outputs only when prompts, model, decoding and precision match")
    parser.add_argument("--candidate", default=str(ROOT / "models" / "nutrition_evidence_candidate"))
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--cpu-int8", action="store_true", help="Evaluate experimental MLP int8; original-weight float32 is the default")
    parser.add_argument("--text-only", action="store_true")
    parser.add_argument("--vision-only", action="store_true")
    parser.add_argument("--evaluate-one", help=argparse.SUPPRESS)
    parser.add_argument("--records-file", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--result-file", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.evaluate_one:
        rows = [json.loads(line) for line in args.records_file.read_text(encoding="utf-8").splitlines()]
        result = evaluate_model(args.evaluate_one, rows, cpu_int8=args.cpu_int8)
        args.result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return
    if args.promote and not args.live:
        parser.error("Promotion requires measured live evaluation")
    if not args.live:
        print("Model inference skipped. No model accuracy claims and no measured report overwritten. Use --live for evaluation.")
        return
    report = {"evaluation_kind": "held_out_evidence_selection", "decoding": "single_id_json_token_trie",
              "clinical_validation": False,
              "vision_status": "not_evaluated_no_labelled_image_dataset", "models": []}
    if args.live and not args.vision_only:
        from build_task_training_data import main as build
        build()
        path = ROOT / "data" / "training" / "evidence_holdout.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        report["holdout_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        # Release every model's memory before loading the next checkpoint. This
        # also prevents allocator residency from distorting latency on this PC.
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            output = Path(directory) / "result.json"
            for index, model in enumerate((args.baseline, args.candidate)):
                if index == 0 and args.baseline_report:
                    previous = json.loads(args.baseline_report.read_text(encoding="utf-8"))
                    expected_precision = "mlp_per_channel_int8_cpu" if args.cpu_int8 else "float32_cpu"
                    matched = next((r for r in previous.get("models", []) if Path(r["model"]).resolve() == Path(model).resolve() and r["precision"] == expected_precision), None)
                    if (previous.get("holdout_sha256") != report["holdout_sha256"] or previous.get("decoding") != report["decoding"]
                            or not matched or [(r["id"], r["target"]) for r in matched["outputs"]] != [(r["id"], r["target"]) for r in rows]):
                        raise ValueError("Cached baseline does not match this model, precision and exact prompt dataset.")
                    matched["reused_from"] = str(args.baseline_report)
                    report["models"].append(matched)
                    print(f"Reused measured baseline from {args.baseline_report}; identical prompt hash and CPU precision.", flush=True)
                    continue
                command = [sys.executable, str(Path(__file__).resolve()), "--evaluate-one", model,
                           "--records-file", str(path), "--result-file", str(output)]
                if args.cpu_int8:
                    command.append("--cpu-int8")
                subprocess.run(command, check=True)
                report["models"].append(json.loads(output.read_text(encoding="utf-8")))
        baseline, candidate = report["models"]
        report["development_passed"] = candidate["schema_valid_rate"] == 1.0 and candidate["exact_selection_rate"] >= 0.9 and candidate["exact_selection_rate"] > baseline["exact_selection_rate"]
        confirmation = ROOT / "data" / "training" / "evidence_confirmation.jsonl"
        report["confirmation_sha256"] = hashlib.sha256(confirmation.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            output = Path(directory) / "confirmation.json"
            command = [sys.executable, str(Path(__file__).resolve()), "--evaluate-one", args.candidate,
                       "--records-file", str(confirmation), "--result-file", str(output)]
            if args.cpu_int8:
                command.append("--cpu-int8")
            subprocess.run(command, check=True)
            report["confirmation"] = json.loads(output.read_text(encoding="utf-8"))
        check = report["confirmation"]
        abstentions = [r for r in check["outputs"] if r["target"] == []]
        confirmation_passed = check["schema_valid_rate"] == 1.0 and check["exact_selection_rate"] >= 0.9 and all(r["exact_match"] for r in abstentions)
        report["passed"] = report["development_passed"] and confirmation_passed
        report["confirmation_status"] = "passed" if confirmation_passed else "failed"
        if args.promote and report["passed"]:
            checkpoint = Path(args.candidate).resolve()
            checkpoint.relative_to(ROOT / "models")
            manifest = {"checkpoint": str(checkpoint.relative_to(ROOT)), "passed": True,
                        "evaluation_kind": report["evaluation_kind"], "holdout_sha256": report["holdout_sha256"],
                        "precision": candidate["precision"],
                        "confirmation_sha256": report["confirmation_sha256"],
                        "decoding": report["decoding"],
                        "clinical_validation": False}
            (ROOT / "models" / "deployment.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        report["promoted"] = args.promote and report["passed"]
    else:
        report["status"] = "not_run_no_model_accuracy_claims"
    result_path = ROOT / "data" / "eval" / "model_evaluation_results.json"
    result_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# NutriGuide measured model evaluation", "", "Only real generated outputs are scored. No clinical accuracy or vision accuracy is established.", "", "JSON syntax is enforced by constrained decoding; exact evidence selection measures the model's choice separately.", ""]
    if report["models"]:
        lines += ["| Model | Development prompts | Valid JSON | Exact evidence selection | Mean latency |", "|---|---:|---:|---:|---:|"]
        for r in report["models"]:
            lines.append(f"| {Path(r['model']).name} | {r['count']} | {r['schema_valid_rate']:.1%} | {r['exact_selection_rate']:.1%} | {r['mean_latency_seconds']:.2f}s |")
        if "reused_from" in report["models"][0]:
            lines.append(f"\nBaseline measurements reused from `{report['models'][0]['reused_from']}` after checking identical prompt hash, checkpoint, decoding and CPU precision.\n")
        lines += ["", f"Candidate passed promotion gate: {report['passed']}. Activated: {report['promoted']}.", "", "The 20 wording prompts were used as a synthetic development benchmark during task optimization. They are not clinical validation.", "", f"Separate 15-prompt confirmation set: {report['confirmation_status']}."]
        if "confirmation" in report:
            check = report["confirmation"]
            lines.append(f"Confirmation exact evidence selection: {check['exact_selection_rate']:.1%}; valid JSON: {check['schema_valid_rate']:.1%}. This set was excluded from training and prompt tuning, and includes unsupported-question abstentions.")
    else:
        lines += ["Model inference was not run. No accuracy, F1 or latency metrics are available."]
    lines += ["", "Vision evaluation requires real meal-only image files with independently reviewed food and person-presence labels. Existing JSON fixtures are workflow tests.", "", "Legacy adapted weights were previously trained on synthetic evaluation cases; earlier evaluation-case accuracy is invalid for measuring generalization."]
    (ROOT / "BENCHMARK_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "models"}, indent=2))


if __name__ == "__main__":
    main()
