"""Lab-report helpers: reference-range parsing, out-of-range detection, text field extraction,
loose JSON parsing of Gemini Vision output, and per-test trend series across reports."""
import json
import re

FIELD_PATTERN = re.compile(
    r"([A-Za-z][A-Za-z0-9 /()%-]{2,40}?)\s+([\d.]+)\s*([a-zA-Z/%µ]{0,10})\s*"
    r"\(?\s*([\d.]+\s*-\s*[\d.]+)?\s*\)?")

_NUM = r"(\d+(?:\.\d+)?)"


def to_float(value):
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        m = re.search(_NUM, str(value or ""))
        return float(m.group(1)) if m else None


def parse_ref_range(ref):
    """'12.0-15.5' -> (12.0, 15.5); '<200' -> (None, 200); '>40' -> (40, None); unknown -> (None, None)."""
    if not ref:
        return None, None
    s = str(ref).replace("–", "-").replace("—", "-").replace("to", "-").replace("≤", "<").replace("≥", ">")
    m = re.search(_NUM + r"\s*-\s*" + _NUM, s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"<\s*=?\s*" + _NUM, s)
    if m:
        return None, float(m.group(1))
    m = re.search(r">\s*=?\s*" + _NUM, s)
    if m:
        return float(m.group(1)), None
    return None, None


def direction(value, ref):
    """'high' / 'low' / 'normal' / None (unknown) for a value against its reference range."""
    v = to_float(value)
    low, high = parse_ref_range(ref)
    if v is None or (low is None and high is None):
        return None
    if high is not None and v > high:
        return "high"
    if low is not None and v < low:
        return "low"
    return "normal"


def is_out_of_range(value, ref) -> bool:
    return direction(value, ref) in ("high", "low")


def extract_fields(text: str) -> list[dict]:
    """Regex extraction for digital-text / OCR output."""
    fields = []
    for m in FIELD_PATTERN.finditer(text or ""):
        name, value, unit, ref = m.groups()
        fields.append({"test": name.strip(), "value": value.strip(), "unit": (unit or "").strip() or None,
                       "reference_range": ref.strip() if ref else None,
                       "out_of_range": is_out_of_range(value, ref)})
    return fields


def parse_json_loose(text):
    """Parses JSON from a model answer even if wrapped in ``` fences or surrounded by prose."""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    candidates = [cleaned]
    braces = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if braces:
        candidates.append(braces.group(0))
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def normalize_vision_fields(raw_fields) -> list[dict]:
    """Cleans fields returned by Gemini Vision; out_of_range is recomputed here, never trusted from the model."""
    out = []
    for f in raw_fields or []:
        if not isinstance(f, dict) or not f.get("test"):
            continue
        value = str(f.get("value", "")).strip()
        ref = (str(f.get("reference_range")).strip() if f.get("reference_range") else None)
        out.append({"test": str(f["test"]).strip(), "value": value,
                    "unit": (str(f.get("unit")).strip() if f.get("unit") else None),
                    "reference_range": ref, "out_of_range": is_out_of_range(value, ref)})
    return out


def normalize_test_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ()%/-]", "", (name or "").lower())).strip()


def build_lab_series(reports: list[dict]) -> dict[str, list[dict]]:
    """{normalized test name: [{date, value, unit, low, high, out_of_range, label}] sorted by date}"""
    series: dict[str, list[dict]] = {}
    for r in reports:
        for f in r.get("fields", []):
            v = to_float(f.get("value"))
            if v is None:
                continue
            low, high = parse_ref_range(f.get("reference_range"))
            key = normalize_test_name(f.get("test"))
            if not key:
                continue
            series.setdefault(key, []).append({
                "date": r.get("report_date") or (r.get("created_at") or "")[:10], "value": v,
                "unit": f.get("unit"), "low": low, "high": high, "label": f.get("test"),
                "out_of_range": is_out_of_range(f.get("value"), f.get("reference_range")),
                "direction": direction(f.get("value"), f.get("reference_range"))})
    for pts in series.values():
        pts.sort(key=lambda p: p["date"])
    return series


def latest_abnormal(series: dict) -> list[dict]:
    """Latest reading of each test that is out of range, with trend vs the previous reading."""
    alerts = []
    for pts in series.values():
        last = pts[-1]
        if last["out_of_range"]:
            trend = None
            if len(pts) > 1:
                trend = "rising" if last["value"] > pts[-2]["value"] else "falling" if last["value"] < pts[-2]["value"] else "steady"
            alerts.append({**last, "trend": trend})
    return alerts
