"""Unified Test & Evaluation Runner for NutriGuide

Executes all test suites in the repository:
1. evaluate_dataset.py (Aggressive Age Boundary Matrix + 70 Deterministic Cases + 110 Meal Photos)
2. evaluate_screening_boundaries.py (Phase 1 Screening Boundaries & Scope Verification)
3. evaluate.py (Curated Knowledge Safety Checks)
4. evaluate_framework.py (Educational Framework Checks)
5. evaluate_meal.py (Meal Photo Workflow Checks)
6. benchmark_models.py (SLM & VLM Model Benchmark Suite)
"""
from __future__ import annotations

import subprocess
import sys
import time

TEST_SCRIPTS = [
    ("Intake Indicators & Model Contracts", "test_intake_screening.py"),
    ("Server Concurrency & Request Validation", "test_server_runtime.py"),
    ("Age Boundary Matrix & Evaluation Datasets", "evaluate_dataset.py"),
    ("Phase 1 Screening Safety Boundaries", "evaluate_screening_boundaries.py"),
    ("Curated Context Safety", "evaluate.py"),
    ("Educational Framework & Scope", "evaluate_framework.py"),
    ("Meal Photo Workflow & Confirmation", "evaluate_meal.py"),
    ("SLM/VLM Model Benchmark Suite", "benchmark_models.py"),
]

def run_all() -> int:
    print("=================================================================")
    print("      RUNNING ALL NUTRIGUIDE TEST & EVALUATION SUITES")
    print("=================================================================\n")

    results = []
    total_start = time.time()

    for title, script in TEST_SCRIPTS:
        print(f"[*] Running: {title} ({script})...")
        t0 = time.time()
        res = subprocess.run([sys.executable, script], capture_output=True, text=True)
        dur = round(time.time() - t0, 2)
        passed = (res.returncode == 0)
        results.append((title, script, passed, dur, res.stdout, res.stderr))
        status = "PASSED" if passed else "FAILED"
        print(f"    --> [{status}] in {dur}s\n")

    total_dur = round(time.time() - total_start, 2)

    print("=================================================================")
    print("                      TEST SUMMARY REPORT")
    print("=================================================================")
    all_passed = True
    for title, script, passed, dur, stdout, stderr in results:
        status_sym = "[PASS]" if passed else "[FAIL]"
        print(f"  {status_sym} {title:<40} ({script}) - {dur}s")
        if not passed:
            all_passed = False
            print(f"        Error details:\n{stderr or stdout}\n")

    print(f"\nTotal Test Duration: {total_dur}s")
    if all_passed:
        print("OVERALL STATUS: ALL TEST SUITES PASSED (100% SUCCESS)")
        return 0
    else:
        print("OVERALL STATUS: SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(run_all())
