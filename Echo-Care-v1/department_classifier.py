"""
Thin wrapper that loads the model trained by ml/train_department_classifier.py.
Falls back to a transparent keyword lookup (via specialties.KEYWORD_TO_SPECIALTY)
if the model hasn't been trained yet — never a silent guess dressed up as a
trained-model result.
"""
from pathlib import Path
import joblib

from specialties import KEYWORD_TO_SPECIALTY

HERE = Path(__file__).parent
MODEL_PATH = HERE / "ml" / "department_model.joblib"

_model = None


def _load():
    global _model
    if _model is None and MODEL_PATH.exists():
        try:
            _model = joblib.load(MODEL_PATH)
        except Exception:
            # An artifact saved by an incompatible scikit-learn version should
            # not take down the doctor finder; use the explicit heuristic below.
            _model = False
    return _model if _model is not False else None


def predict_department(symptom_text: str) -> dict:
    model = _load()
    if model is not None:
        try:
            proba = model.predict_proba([symptom_text])[0]
            classes = model.classes_
            ranked = sorted(zip(classes, proba), key=lambda x: x[1], reverse=True)[:3]
            return {
                "model_used": "trained_classifier(tfidf+logreg)",
                "top_department": str(ranked[0][0]),
                "confidence": float(ranked[0][1]),
                "ranked": [{"department": str(d), "score": float(s)} for d, s in ranked],
            }
        except Exception:
            # Older/unpickled estimators can lack attributes expected by the
            # installed sklearn. Fall through to a clearly labeled heuristic.
            global _model
            _model = False

    text_l = symptom_text.lower()
    scores: dict[str, int] = {}
    for kw, specialty in KEYWORD_TO_SPECIALTY.items():
        if kw in text_l:
            scores[specialty] = scores.get(specialty, 0) + 1
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = ranked[0][0] if ranked else "General Medicine"
    total = sum(scores.values()) or 1
    return {
        "model_used": "keyword_heuristic_fallback (retrain ml/department_model.joblib for this scikit-learn version)",
        "top_department": top,
        "confidence": (ranked[0][1] / total) if ranked else 0.3,
        "ranked": [{"department": d, "score": s / total} for d, s in ranked[:3]],
    }
