"""Reproducible evidence-selection pairs; no evaluation-case or survey-row reuse.

Labels are synthetic selections from the reviewed local KB. Held-out prompts test
engineering behaviour only, not clinical screening accuracy.
"""
import hashlib
import json
import random
from pathlib import Path

from app import find_band
from model_runtime import selection_messages

ROOT = Path(__file__).parent
TOPICS = {
    "meals": (["What feeding frequency is recommended?", "How often should I feed my child?", "Tell me about the daily meal pattern."], "How many daily feedings are suggested?"),
    "textures": (["Which textures are suitable?", "What food consistency should I offer?", "How should I progress food textures?"], "Which food textures fit this age?"),
    "variety": (["What variety should I aim for?", "Explain the dietary variety guidance.", "What does dietary diversity mean at this age?"], "What is the age-specific food variety guidance?"),
    "skills": (["How do I support feeding skills?", "Explain responsive feeding skills.", "How can I help my child learn to eat?"], "What feeding skills should I encourage?"),
}


def build_records():
    rng = random.Random(42)
    train, held = [], []
    for age in (3, 7, 10, 18, 36):
        band = find_band(age)
        facts = {"meals": band["meal_cadence"], "textures": band["safe_textures"],
                 "variety": band["variety_target"], "skills": band["feeding_skills"]}
        for topic, (queries, held_query) in TOPICS.items():
            for split, questions in ((train, queries), (held, [held_query])):
                for query in questions:
                    evidence = list(facts.values())
                    rng.shuffle(evidence)
                    question = f"For a child aged {age} months: {query}"
                    label = [evidence.index(facts[topic])]
                    record = {"age_months": age, "topic": topic, "question": question,
                              "evidence": evidence, "target": label,
                              "messages": selection_messages(question, evidence),
                              "source_ids": band["sources"], "label_origin": "synthetic_reviewed_kb_selection"}
                    record["id"] = hashlib.sha256(question.encode()).hexdigest()[:16]
                    split.append(record)
    return train, held


def main():
    directory = ROOT / "data" / "training"
    directory.mkdir(parents=True, exist_ok=True)
    train, held = build_records()
    assert not {r["id"] for r in train} & {r["id"] for r in held}
    for name, rows in (("evidence_train.jsonl", train), ("evidence_holdout.jsonl", held)):
        (directory / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"Prepared {len(train)} train and {len(held)} held-out prompt records. No clinical accuracy claim.")
    # A separate confirmation set is reserved from prompt tuning and training.
    rng = random.Random(97)
    confirmation = []
    queries = {"meals": "What pattern of meals and snacks is recommended through the day?",
               "textures": "How should the consistency of foods progress for eating?",
               "variety": "Which guidance describes dietary diversity for this age?",
               "skills": "What age-appropriate feeding abilities should I support?"}
    for age in (8, 11, 22):
        band = find_band(age)
        facts = {"meals": band["meal_cadence"], "textures": band["safe_textures"],
                 "variety": band["variety_target"], "skills": band["feeding_skills"]}
        for topic, query in list(queries.items()) + [("abstain", "What is my child's blood sodium concentration?")]:
            evidence = list(facts.values())
            rng.shuffle(evidence)
            question = f"For a child aged {age} months: {query}"
            confirmation.append({"id": hashlib.sha256(question.encode()).hexdigest()[:16],
                                 "age_months": age, "topic": topic, "question": question,
                                 "evidence": evidence, "target": [] if topic == "abstain" else [evidence.index(facts[topic])],
                                 "messages": selection_messages(question, evidence),
                                 "source_ids": band["sources"],
                                 "label_origin": "synthetic_reviewed_kb_selection"})
    (directory / "evidence_confirmation.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in confirmation), encoding="utf-8")


if __name__ == "__main__":
    main()
