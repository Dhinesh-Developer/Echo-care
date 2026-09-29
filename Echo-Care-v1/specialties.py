"""
Canonical specialty -> symptom-keyword map, as provided by the project owner.
This single source of truth drives THREE things across the app:
  1. Symptom tagging in the LE-RAG evidence pipeline (rag.py)
  2. The trained department-recommendation classifier (ml/train_department_classifier.py)
  3. The specialty filter on the district doctor-finder map (pages/8_Find_Doctors.py)
"""

SPECIALTIES = {
    "General Medicine": [
        "fever", "fatigue", "body ache", "chills", "weakness", "loss of appetite",
        "mild cough", "general malaise", "feeling unwell", "low grade temperature",
    ],
    "Neurology": [
        "headache", "migraine", "dizziness", "numbness in hand", "tingling in leg",
        "memory problems", "seizure", "blurred vision with headache", "vertigo",
        "difficulty concentrating", "light sensitivity",
    ],
    "Cardiology": [
        "chest pain", "palpitations", "shortness of breath on exertion", "racing heartbeat",
        "chest tightness", "swelling in ankles", "fainting spells", "high blood pressure readings",
    ],
    "Gastroenterology": [
        "stomach pain", "bloating", "acid reflux", "nausea after eating", "diarrhea",
        "constipation", "blood in stool", "loss of appetite with stomach cramps",
        "indigestion", "abdominal cramps",
    ],
    "Dermatology": [
        "skin rash", "itching", "red patches on skin", "acne breakout", "hives",
        "dry flaky skin", "hair loss", "skin discoloration", "eczema flare up",
    ],
    "Orthopedics": [
        "joint pain", "back pain", "knee pain when walking", "stiffness in the morning",
        "swelling in the joint", "muscle strain", "shoulder pain", "difficulty moving the wrist",
    ],
    "ENT": [
        "sore throat", "ear pain", "blocked nose", "ringing in the ears", "hearing loss",
        "sinus pressure", "hoarse voice", "difficulty swallowing", "recurring throat infection",
    ],
    "Pulmonology": [
        "persistent cough", "wheezing", "shortness of breath at rest", "chest congestion",
        "coughing up mucus", "breathlessness climbing stairs", "recurring bronchitis",
    ],
    "Psychiatry / Mental Health": [
        "constant worry", "trouble sleeping due to racing thoughts", "low mood for weeks",
        "loss of interest in activities", "panic attacks", "feeling anxious most days",
        "difficulty concentrating and low motivation", "irritability and stress",
    ],
    "Gynecology": [
        "irregular periods", "pelvic pain", "heavy menstrual bleeding", "painful periods",
        "spotting between periods", "menstrual cramps with fatigue",
    ],
}

ALL_SPECIALTIES = list(SPECIALTIES.keys())

# Flattened keyword -> specialty lookup, used by the rule-based fallback tagger
KEYWORD_TO_SPECIALTY = {
    kw: specialty for specialty, kws in SPECIALTIES.items() for kw in kws
}
