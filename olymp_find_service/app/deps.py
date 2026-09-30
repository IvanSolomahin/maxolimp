BENEFIT_ALIASES = {
    "bvi": "no entrance exams",
    "no entrance exams": "no entrance exams",
    "no_entrance_exams": "no entrance exams",
    "100 points": "100 points",
    "100_points": "100 points",
    "additional_points": "additional_points",
    "additional points": "additional_points",
}

RESPONSE_BENEFIT_ALIASES = {
    "no entrance exams": "bvi",
}


def normalize_benefit_type(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip().lower()
    return BENEFIT_ALIASES.get(key, value.strip())


def public_benefit_type(stored: str) -> str:
    return RESPONSE_BENEFIT_ALIASES.get(stored, stored)
