"""
District-wise doctor/facility directory, seeded across every specialty in
specialties.SPECIALTIES. This is DEMO DATA (clearly labeled as such
everywhere it's displayed) — approximate district-center coordinates with
representative hospital/clinic names, built so the map + ranking + filter UX
is fully functional out of the box with zero paid APIs (no Google Places key
required — this app only uses Gemini + Tavily). Swap `DOCTORS` for a real
directory (CSV import, hospital API, or Google Places) before production use;
every function below keeps the exact same signature.
"""
import math
import random
import io
import urllib.parse

import db
from specialties import ALL_SPECIALTIES

random.seed(7)

# Approximate lat/lon centers for Tamil Nadu districts (demo region — extend
# this dict with more states/districts as needed; nothing else needs to change).
DISTRICTS = {
    "Chennai": (13.0827, 80.2707),
    "Coimbatore": (11.0168, 76.9558),
    "Madurai": (9.9252, 78.1198),
    "Tiruchirappalli": (10.7905, 78.7047),
    "Salem": (11.6643, 78.1460),
    "Tirunelveli": (8.7139, 77.7567),
    "Erode": (11.3410, 77.7172),
    "Vellore": (12.9165, 79.1325),
    "Thanjavur": (10.7870, 79.1378),
    "Tiruppur": (11.1085, 77.3411),
}

HOSPITAL_SUFFIXES = ["General Hospital", "Multispeciality Clinic", "Medical Centre", "Care Hospital", "Health Institute"]
DOCTOR_FIRST_NAMES = ["Anitha", "Karthik", "Priya", "Suresh", "Meena", "Ramesh", "Divya", "Arun", "Lakshmi", "Vikram"]
DOCTOR_LAST_NAMES = ["Krishnan", "Raman", "Subramaniam", "Iyer", "Pillai", "Nair", "Reddy", "Chandran", "Murthy", "Rao"]


def _jitter(lat, lon, km_radius=6):
    """Small random offset so multiple facilities in a district don't overlap on the map."""
    r = km_radius / 111.0
    angle = random.uniform(0, 2 * math.pi)
    dist = random.uniform(0, r)
    return lat + dist * math.cos(angle), lon + dist * math.sin(angle)


def _generate_directory() -> list[dict]:
    directory = []
    doctor_id = 1
    for district, (lat, lon) in DISTRICTS.items():
        for specialty in ALL_SPECIALTIES:
            # 1-2 doctors per specialty per district
            for _ in range(random.choice([1, 1, 2])):
                dlat, dlon = _jitter(lat, lon)
                name = f"Dr. {random.choice(DOCTOR_FIRST_NAMES)} {random.choice(DOCTOR_LAST_NAMES)}"
                hospital = f"{district} {random.choice(HOSPITAL_SUFFIXES)}"
                directory.append({
                    "id": doctor_id,
                    "name": name,
                    "specialty": specialty,
                    "district": district,
                    "hospital": hospital,
                    "lat": round(dlat, 5),
                    "lon": round(dlon, 5),
                    "rating": round(random.uniform(3.6, 4.9), 1),
                    "years_experience": random.randint(3, 28),
                    "consultation_fee_inr": random.choice([300, 400, 500, 600, 800, 1000]),
                    "phone": f"+91 {random.randint(70000, 99999)}{random.randint(10000, 99999)}",
                    "is_demo_data": True,
                })
                doctor_id += 1
    return directory


DOCTORS = _generate_directory()


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def get_directory() -> list[dict]:
    """Real imported directory if an admin uploaded one, otherwise the demo directory."""
    imported = db.get_imported_doctors()
    return imported if imported else DOCTORS


def directory_source(directory: list[dict] | None = None) -> str:
    directory = directory if directory is not None else get_directory()
    return "demo" if directory and directory[0].get("is_demo_data", True) else "imported"


def directory_districts(directory: list[dict]) -> dict[str, tuple[float, float]]:
    """District -> (lat, lon) centroid computed from the doctors actually in the directory."""
    acc: dict[str, list] = {}
    for d in directory:
        acc.setdefault(d["district"], []).append((d["lat"], d["lon"]))
    return {k: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for k, v in sorted(acc.items())}


def directory_specialties(directory: list[dict]) -> list[str]:
    present = {d["specialty"] for d in directory}
    return [s for s in ALL_SPECIALTIES if s in present] + sorted(present - set(ALL_SPECIALTIES))


def find_doctors(district: str | None = None, specialty: str | None = None,
                 directory: list[dict] | None = None) -> list[dict]:
    results = directory if directory is not None else get_directory()
    if district and district != "All districts":
        results = [d for d in results if d["district"] == district]
    if specialty and specialty != "All specialties":
        results = [d for d in results if d["specialty"] == specialty]
    return results


def navigate_url(lat: float, lon: float) -> str:
    """Google Maps directions link: opens the Maps app/site; needs no API key."""
    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"


def maps_search_url(query: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(query)


# ---------------- Real-data import (CSV / Excel) ----------------
REQUIRED_COLUMNS = ["name", "specialty", "district", "hospital"]
OPTIONAL_COLUMNS = ["lat", "lon", "rating", "years_experience", "consultation_fee_inr", "phone"]
SPECIALTY_ALIASES = {
    "psychiatry": "Psychiatry / Mental Health", "mental health": "Psychiatry / Mental Health",
    "psychiatrist": "Psychiatry / Mental Health", "gynaecology": "Gynecology", "gynecologist": "Gynecology",
    "orthopaedics": "Orthopedics", "orthopedic": "Orthopedics", "orthopaedic": "Orthopedics",
    "general physician": "General Medicine", "physician": "General Medicine", "general": "General Medicine",
    "gastro": "Gastroenterology", "ent specialist": "ENT", "cardiologist": "Cardiology",
    "neurologist": "Neurology", "dermatologist": "Dermatology", "pulmonologist": "Pulmonology",
}


def normalize_specialty(raw: str) -> tuple[str, bool]:
    """Returns (canonical specialty, recognised?)."""
    s = str(raw).strip()
    for canonical in ALL_SPECIALTIES:
        if s.lower() == canonical.lower():
            return canonical, True
    if s.lower() in SPECIALTY_ALIASES:
        return SPECIALTY_ALIASES[s.lower()], True
    return s.title(), False


def template_csv() -> str:
    return (",".join(REQUIRED_COLUMNS + OPTIONAL_COLUMNS) + "\n"
            "Dr. A. Kumar,Cardiology,Chennai,Example Heart Hospital,13.0827,80.2707,4.6,18,700,+91 9000000001\n"
            "Dr. S. Devi,Dermatology,Coimbatore,Example Skin Clinic,,,4.3,9,500,+91 9000000002\n")


def parse_directory_upload(df) -> tuple[list[dict], list[str], list[str]]:
    """Validates a pandas DataFrame. Returns (clean rows, errors that skipped rows, warnings)."""
    df = df.rename(columns={c: str(c).strip().lower() for c in df.columns})
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return [], [f"Missing required column(s): {', '.join(missing)}"], []
    known_centers = {k.lower(): v for k, v in DISTRICTS.items()}
    rows, errors, warnings = [], [], []

    def num(v, cast, default):
        try:
            return cast(float(v)) if str(v).strip() not in ("", "nan", "None") else default
        except (ValueError, TypeError):
            return default

    for i, r in df.iterrows():
        line = i + 2
        name, district, hospital = (str(r.get(c, "")).strip() for c in ("name", "district", "hospital"))
        if not name or name == "nan" or not district or district == "nan":
            errors.append(f"Row {line}: name and district are required, row skipped.")
            continue
        specialty, known = normalize_specialty(r.get("specialty", ""))
        if not known:
            warnings.append(f"Row {line}: unrecognised specialty '{specialty}' imported as-is.")
        lat, lon = num(r.get("lat"), float, None), num(r.get("lon"), float, None)
        if lat is None or lon is None:
            center = known_centers.get(district.lower())
            if not center:
                errors.append(f"Row {line}: no lat/lon and district '{district}' is not a known district, row skipped.")
                continue
            lat, lon = _jitter(*center)
            warnings.append(f"Row {line}: no coordinates, placed near the {district} centre.")
        rows.append({"name": name, "specialty": specialty, "district": district.title(),
                     "hospital": hospital if hospital != "nan" else "", "lat": round(lat, 5), "lon": round(lon, 5),
                     "rating": min(max(num(r.get("rating"), float, 4.0), 0.0), 5.0),
                     "years_experience": num(r.get("years_experience"), int, 0),
                     "consultation_fee_inr": num(r.get("consultation_fee_inr"), int, 0),
                     "phone": ("" if str(r.get("phone", "")) in ("nan", "None") else str(r.get("phone", "")).strip())})
    return rows, errors, warnings


def rank_doctors(doctors: list[dict], user_lat: float | None = None, user_lon: float | None = None) -> list[dict]:
    """Alg. 6 — composite ranking: rating + experience + (optional) proximity."""
    ranked = []
    for d in doctors:
        rating_score = d["rating"] / 5
        exp_score = min(d["years_experience"] / 25, 1.0)
        if user_lat is not None and user_lon is not None:
            dist_km = haversine_km(user_lat, user_lon, d["lat"], d["lon"])
            distance_score = max(0, 1 - dist_km / 50)
            composite = 0.35 * rating_score + 0.25 * exp_score + 0.4 * distance_score
        else:
            dist_km = None
            composite = 0.55 * rating_score + 0.45 * exp_score
        d = dict(d)
        d["distance_km"] = round(dist_km, 1) if dist_km is not None else None
        d["_score"] = round(composite, 3)
        ranked.append(d)
    ranked.sort(key=lambda x: x["_score"], reverse=True)
    return ranked
