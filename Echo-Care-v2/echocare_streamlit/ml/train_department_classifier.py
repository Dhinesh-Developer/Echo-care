"""
Alg. 5 — Department Recommendation classifier.

Trained DIRECTLY on the project's own SPECIALTIES keyword map: every keyword
phrase becomes a training example, plus generated two-symptom combination
sentences ("I have been experiencing X and Y") for more natural-language
coverage. This keeps the model's vocabulary and label set perfectly aligned
with specialties.py — the same source of truth used by the symptom tagger
and the doctor-finder page.

Run:  python ml/train_department_classifier.py
Outputs: ml/department_model.joblib, ml/label_classes.json, ml/metrics.md
"""
import json
import random
import sys
from pathlib import Path
from itertools import combinations

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from specialties import SPECIALTIES  # noqa: E402

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, classification_report
from sklearn.pipeline import Pipeline
import joblib

random.seed(42)
HERE = Path(__file__).parent


def build_dataset() -> list[tuple[str, str]]:
    dataset = []
    for specialty, keywords in SPECIALTIES.items():
        for kw in keywords:
            dataset.append((kw, specialty))
        # Two-symptom natural-language combinations, capped to avoid class imbalance
        combos = list(combinations(keywords, 2))
        random.shuffle(combos)
        for a, b in combos[:8]:
            dataset.append((f"I have been experiencing {a} and {b}", specialty))
            dataset.append((f"{a} along with {b} for a few days", specialty))
    random.shuffle(dataset)
    return dataset


def main():
    dataset = build_dataset()
    texts = [t for t, _ in dataset]
    labels = [l for _, l in dataset]
    label_set = sorted(set(labels))

    X_train, X_temp, y_train, y_temp = train_test_split(
        texts, labels, test_size=0.3, random_state=42, stratify=labels
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
        ("clf", LogisticRegression(max_iter=2000)),
    ])
    pipeline.fit(X_train, y_train)

    baseline = DummyClassifier(strategy="most_frequent")
    baseline.fit(X_train, y_train)

    def evaluate(model, X, y, name):
        preds = model.predict(X)
        return {
            "name": name,
            "accuracy": accuracy_score(y, preds),
            "macro_f1": f1_score(y, preds, average="macro", zero_division=0),
            "confusion_matrix": confusion_matrix(y, preds, labels=label_set).tolist(),
            "report": classification_report(y, preds, zero_division=0),
        }

    val_result = evaluate(pipeline, X_val, y_val, "LogReg (val)")
    test_result = evaluate(pipeline, X_test, y_test, "LogReg (test)")
    baseline_result = evaluate(baseline, X_test, y_test, "Majority-class baseline (test)")

    joblib.dump(pipeline, HERE / "department_model.joblib")
    with open(HERE / "label_classes.json", "w") as f:
        json.dump(label_set, f)

    lines = ["# Department Classifier — Training Report\n"]
    lines.append(f"Total examples: {len(dataset)} across {len(label_set)} specialties "
                 f"(built directly from `specialties.SPECIALTIES`)\n")
    lines.append(f"Train/Val/Test split: {len(X_train)}/{len(X_val)}/{len(X_test)} "
                 f"(stratified, random_state=42)\n")
    for result in (val_result, test_result, baseline_result):
        lines.append(f"## {result['name']}\n")
        lines.append(f"- Accuracy: {result['accuracy']:.3f}")
        lines.append(f"- Macro-F1: {result['macro_f1']:.3f}\n")
        lines.append("```")
        lines.append(result["report"])
        lines.append("```\n")
    lines.append("## Confusion matrix (test set, LogReg)\n")
    lines.append(f"Label order: {label_set}\n")
    lines.append("```")
    for row in test_result["confusion_matrix"]:
        lines.append(str(row))
    lines.append("```\n")
    lines.append(
        "## Notes\nThis dataset is generated programmatically from the project's own "
        "symptom-keyword map rather than hand-labeled patient data, so treat these "
        "metrics as a pipeline validation, not a clinical-grade evaluation. For a "
        "submission-grade evaluation, augment with a curated public symptom-checker "
        "dataset and re-run this script."
    )
    with open(HERE / "metrics.md", "w") as f:
        f.write("\n".join(lines))

    print(f"Saved model + metrics.md. Val acc={val_result['accuracy']:.3f} "
          f"Test acc={test_result['accuracy']:.3f} (n={len(dataset)})")


if __name__ == "__main__":
    main()
