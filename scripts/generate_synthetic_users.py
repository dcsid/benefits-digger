from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from random import Random
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
REFERENCE_DATE = date(2026, 3, 21)
SEED = 20260321
USER_COUNT = 50


BENCHMARKS = {
    "female_pct": 50.5,
    "age_65_plus_pct": 18.0,
    "foreign_born_pct": 14.1,
    "bachelors_or_higher_pct": 35.7,
    "disability_under_65_pct": 9.3,
    "poverty_pct": 10.6,
    "broadband_pct": 91.0,
    "labor_force_pct": 63.0,
    "families_with_children_pct": 39.0,
    "college_enrollment_18_24_pct": 39.0,
}

SOURCE_URLS = [
    "https://www.census.gov/quickfacts/fact/table/US/PST045225",
    "https://www.census.gov/newsroom/press-releases/2025/families-and-living-arrangements.html",
    "https://nces.ed.gov/programs/coe/indicator/cpb/college-enrollment-rate",
]

AGE_BANDS = {
    "18-24": (18, 24),
    "25-34": (25, 34),
    "35-44": (35, 44),
    "45-54": (45, 54),
    "55-64": (55, 64),
    "65-74": (65, 74),
    "75+": (75, 85),
}

AGE_BAND_QUOTAS = Counter(
    {
        "18-24": 6,
        "25-34": 10,
        "35-44": 9,
        "45-54": 8,
        "55-64": 8,
        "65-74": 6,
        "75+": 3,
    }
)

SEX_QUOTAS = Counter({"female": 25, "male": 25})
RACE_QUOTAS = Counter(
    {
        "White, non-Hispanic": 28,
        "Black, non-Hispanic": 7,
        "Hispanic or Latino": 10,
        "Asian, non-Hispanic": 3,
        "American Indian or Alaska Native": 1,
        "Multiracial, non-Hispanic": 1,
    }
)
REGION_QUOTAS = Counter({"South": 19, "West": 12, "Midwest": 10, "Northeast": 9})
REGION_STATES = {
    "South": ["TX", "FL", "GA", "NC", "VA", "TN", "SC", "AL", "LA", "KY", "OK", "AR", "MD"],
    "West": ["CA", "WA", "OR", "AZ", "CO", "NM", "NV", "UT", "HI", "AK", "ID", "MT"],
    "Midwest": ["IL", "OH", "MI", "WI", "MN", "IN", "MO", "IA", "KS", "NE"],
    "Northeast": ["NY", "PA", "NJ", "MA", "CT", "RI", "NH", "VT", "ME"],
}

GENDER_OVERRIDES = {
    11: "nonbinary",
    37: "transgender woman",
}

LANGUAGE_OVERRIDES = {
    3: "Spanish",
    7: "Spanish",
    9: "Spanish",
    14: "Spanish",
    18: "Spanish",
    23: "Spanish",
    29: "Spanish",
    32: "Chinese",
    35: "Vietnamese",
    41: "Arabic",
    47: "Spanish",
}


@dataclass(frozen=True)
class ScenarioTemplate:
    key: str
    count: int
    allowed_age_bands: tuple[str, ...]
    base_categories: tuple[str, ...]
    employment_mode: str
    require_children: bool = False
    require_student: bool = False
    require_veteran: bool = False
    require_disability: bool = False
    severe_disability: bool = False
    require_recent_job_loss: bool = False
    require_death_event: bool = False
    require_disaster: bool = False
    require_housing_pressure: bool = False
    require_low_income: bool = False
    require_senior: bool = False
    likely_scope: str = "both"


SCENARIO_TEMPLATES = [
    ScenarioTemplate(
        key="working_parent_housing_cost",
        count=6,
        allowed_age_bands=("25-34", "35-44", "45-54"),
        base_categories=("children_families", "housing_utilities", "health"),
        employment_mode="employed",
        require_children=True,
        require_housing_pressure=True,
        require_low_income=True,
        likely_scope="both",
    ),
    ScenarioTemplate(
        key="student_low_income",
        count=5,
        allowed_age_bands=("18-24", "25-34"),
        base_categories=("education", "food", "health"),
        employment_mode="student",
        require_student=True,
        require_low_income=True,
        require_housing_pressure=True,
        likely_scope="both",
    ),
    ScenarioTemplate(
        key="senior_fixed_income",
        count=8,
        allowed_age_bands=("55-64", "65-74", "75+"),
        base_categories=("retirement_seniors", "health"),
        employment_mode="retired",
        require_senior=True,
        require_housing_pressure=True,
        likely_scope="federal",
    ),
    ScenarioTemplate(
        key="disabled_worker",
        count=5,
        allowed_age_bands=("25-34", "35-44", "45-54", "55-64"),
        base_categories=("disabilities", "health", "welfare_cash_assistance"),
        employment_mode="limited_work",
        require_disability=True,
        severe_disability=True,
        require_low_income=True,
        likely_scope="both",
    ),
    ScenarioTemplate(
        key="unemployed_renter",
        count=4,
        allowed_age_bands=("25-34", "35-44", "45-54", "55-64"),
        base_categories=("jobs_unemployment", "housing_utilities", "food"),
        employment_mode="unemployed",
        require_recent_job_loss=True,
        require_housing_pressure=True,
        require_low_income=True,
        likely_scope="both",
    ),
    ScenarioTemplate(
        key="veteran_household",
        count=3,
        allowed_age_bands=("35-44", "45-54", "55-64", "65-74"),
        base_categories=("military_veterans", "health"),
        employment_mode="mixed",
        require_veteran=True,
        likely_scope="both",
    ),
    ScenarioTemplate(
        key="disaster_recovery",
        count=3,
        allowed_age_bands=("25-34", "35-44", "45-54", "55-64", "65-74"),
        base_categories=("disasters", "housing_utilities", "food"),
        employment_mode="mixed",
        require_disaster=True,
        require_housing_pressure=True,
        likely_scope="state",
    ),
    ScenarioTemplate(
        key="survivor_funeral",
        count=3,
        allowed_age_bands=("25-34", "35-44", "45-54", "55-64", "65-74"),
        base_categories=("death",),
        employment_mode="mixed",
        require_death_event=True,
        likely_scope="federal",
    ),
    ScenarioTemplate(
        key="general_low_income",
        count=5,
        allowed_age_bands=("25-34", "35-44", "45-54", "55-64"),
        base_categories=("food", "welfare_cash_assistance"),
        employment_mode="mixed",
        require_low_income=True,
        likely_scope="both",
    ),
    ScenarioTemplate(
        key="caregiver_health",
        count=4,
        allowed_age_bands=("25-34", "35-44", "45-54", "55-64"),
        base_categories=("children_families", "health"),
        employment_mode="caregiver",
        require_children=True,
        likely_scope="both",
    ),
    ScenarioTemplate(
        key="reskilling_worker",
        count=4,
        allowed_age_bands=("18-24", "25-34", "35-44", "45-54"),
        base_categories=("education", "jobs_unemployment"),
        employment_mode="training",
        require_recent_job_loss=True,
        likely_scope="both",
    ),
]


def weighted_pick(rng: Random, quota: Counter[str], allowed: list[str] | tuple[str, ...] | None = None) -> str:
    candidates = [(key, count) for key, count in quota.items() if count > 0 and (allowed is None or key in allowed)]
    if not candidates:
        candidates = [(key, count) for key, count in quota.items() if count > 0]
    total = sum(count for _, count in candidates)
    cursor = rng.uniform(0, total)
    running = 0.0
    for key, count in candidates:
        running += count
        if cursor <= running:
            quota[key] -= 1
            return key
    key = candidates[-1][0]
    quota[key] -= 1
    return key


def random_age_in_band(rng: Random, band: str) -> int:
    low, high = AGE_BANDS[band]
    return rng.randint(low, high)


def make_birth_date(rng: Random, age: int) -> str:
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    year = REFERENCE_DATE.year - age
    if (month, day) > (REFERENCE_DATE.month, REFERENCE_DATE.day):
        year -= 1
    return date(year, month, day).isoformat()


def state_name_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for region, states in REGION_STATES.items():
        for code in states:
            mapping[code] = region
    return mapping


STATE_TO_REGION = state_name_map()


def rotate_state(region: str, counters: dict[str, int]) -> str:
    states = REGION_STATES[region]
    index = counters.get(region, 0)
    counters[region] = index + 1
    return states[index % len(states)]


def scenario_plan() -> list[ScenarioTemplate]:
    plan: list[ScenarioTemplate] = []
    for template in SCENARIO_TEMPLATES:
        plan.extend([template] * template.count)
    assert len(plan) == USER_COUNT
    return plan


def poverty_like_threshold(household_size: int) -> int:
    return 18000 + max(0, household_size - 1) * 7000


def limited_income_threshold(household_size: int) -> int:
    return 26000 + max(0, household_size - 1) * 9000


def infer_education_level(rng: Random, age: int, scenario: ScenarioTemplate, bachelors_slots_remaining: Counter[str]) -> str:
    if scenario.require_student:
        return rng.choice(["high_school_or_ged", "some_college", "associate_in_progress", "bachelors_in_progress"])
    if age >= 65:
        return rng.choice(["high_school_or_ged", "some_college", "associate", "bachelors"])
    if age < 25:
        return rng.choice(["high_school_or_ged", "some_college", "associate_in_progress", "bachelors_in_progress"])

    if bachelors_slots_remaining["remaining"] > 0 and rng.random() < 0.5:
        bachelors_slots_remaining["remaining"] -= 1
        return rng.choice(["bachelors", "graduate_degree"])
    return rng.choice(["high_school_or_ged", "some_college", "associate"])


def determine_household(rng: Random, scenario: ScenarioTemplate, age: int) -> tuple[int, int, str]:
    if scenario.require_children:
        dependents = rng.randint(1, 3)
        adults = 1 if rng.random() < 0.4 else 2
        return adults + dependents, dependents, rng.choice(["single", "married", "partnered"])
    if scenario.require_senior:
        if age >= 75 and rng.random() < 0.4:
            return 1, 0, "widowed"
        return rng.choice([(1, 0, "single"), (2, 0, "married"), (1, 0, "widowed")])
    if scenario.require_student:
        if rng.random() < 0.4:
            return 1, 0, "single"
        return rng.choice([(2, 0, "single"), (3, 0, "single"), (1, 0, "single")])
    if scenario.key in {"unemployed_renter", "general_low_income"} and rng.random() < 0.3:
        return 1, 0, "single"
    adults = rng.choice([1, 2, 2, 2, 3])
    return adults, 0, rng.choice(["single", "married", "partnered", "divorced"])


def determine_employment_status(rng: Random, scenario: ScenarioTemplate, age: int) -> str:
    if scenario.employment_mode == "retired":
        return "retired"
    if scenario.employment_mode == "student":
        return rng.choice(["student_full_time", "student_part_time_worker"])
    if scenario.employment_mode == "limited_work":
        return rng.choice(["disabled_not_working", "part_time_due_to_disability"])
    if scenario.employment_mode == "unemployed":
        return rng.choice(["unemployed_looking", "recently_laid_off"])
    if scenario.employment_mode == "caregiver":
        return rng.choice(["not_in_labor_force_caregiver", "part_time_worker"])
    if scenario.employment_mode == "training":
        return rng.choice(["job_training", "unemployed_looking", "part_time_worker"])
    if scenario.employment_mode == "mixed":
        if scenario.require_veteran:
            return rng.choice(["employed_full_time", "retired", "part_time_worker"])
        if scenario.require_death_event:
            return rng.choice(["employed_full_time", "part_time_worker", "not_in_labor_force_caregiver"])
        if scenario.require_disaster:
            return rng.choice(["employed_full_time", "part_time_worker", "recently_laid_off"])
    if age >= 65:
        return rng.choice(["retired", "part_time_worker"])
    return rng.choice(["employed_full_time", "employed_full_time", "part_time_worker"])


def determine_housing(rng: Random, scenario: ScenarioTemplate, age: int) -> tuple[str, int, bool, bool]:
    if scenario.require_housing_pressure or scenario.require_low_income:
        housing_status = rng.choice(["renter", "renter", "staying_with_family", "shelter_or_temporary"])
    elif age >= 65:
        housing_status = rng.choice(["owner_no_mortgage", "owner_with_mortgage", "renter"])
    else:
        housing_status = rng.choice(["renter", "owner_with_mortgage", "renter", "owner_with_mortgage"])

    if housing_status == "owner_no_mortgage":
        housing_cost = rng.randint(450, 1300)
    elif housing_status == "owner_with_mortgage":
        housing_cost = rng.randint(1200, 2900)
    elif housing_status == "shelter_or_temporary":
        housing_cost = rng.randint(0, 500)
    elif housing_status == "staying_with_family":
        housing_cost = rng.randint(200, 900)
    else:
        housing_cost = rng.randint(700, 2400)

    utility_arrears = bool(scenario.require_housing_pressure and rng.random() < 0.75 or rng.random() < 0.12)
    housing_burden = bool(scenario.require_housing_pressure or utility_arrears or rng.random() < 0.25)
    return housing_status, housing_cost, housing_burden, utility_arrears


def determine_income(rng: Random, scenario: ScenarioTemplate, household_size: int, employment_status: str) -> int:
    ranges = {
        "working_parent_housing_cost": (26000, 72000),
        "student_low_income": (0, 28000),
        "senior_fixed_income": (16000, 62000),
        "disabled_worker": (0, 38000),
        "unemployed_renter": (0, 22000),
        "veteran_household": (24000, 82000),
        "disaster_recovery": (18000, 68000),
        "survivor_funeral": (15000, 70000),
        "general_low_income": (0, 30000),
        "caregiver_health": (22000, 62000),
        "reskilling_worker": (12000, 54000),
    }
    low, high = ranges[scenario.key]
    income = rng.randint(low, high)
    if employment_status == "employed_full_time":
        income += rng.randint(3000, 12000)
    if employment_status == "retired":
        income += rng.randint(0, 8000)
    if household_size >= 4:
        income += rng.randint(0, 7000)
    return max(0, round(income / 1000) * 1000)


def determine_insurance(rng: Random, scenario: ScenarioTemplate, age: int, veteran: bool, disability: bool, limited_income: bool) -> str:
    if veteran and rng.random() < 0.6:
        return "va_or_tricare"
    if age >= 65:
        return "medicare"
    if disability and limited_income:
        return rng.choice(["medicaid_or_public", "medicaid_or_public", "dual_eligible"])
    if limited_income and rng.random() < 0.55:
        return "medicaid_or_public"
    if scenario.require_student and rng.random() < 0.15:
        return "uninsured"
    if rng.random() < 0.1:
        return "uninsured"
    return rng.choice(["employer_or_union", "marketplace", "employer_or_union"])


def assign_foreign_born(rng: Random, race_ethnicity: str, remaining: Counter[str]) -> bool:
    if remaining["remaining"] <= 0:
        return False
    probability = 0.12
    if race_ethnicity == "Hispanic or Latino":
        probability = 0.35
    elif race_ethnicity == "Asian, non-Hispanic":
        probability = 0.55
    elif race_ethnicity == "Black, non-Hispanic":
        probability = 0.15
    if rng.random() < probability:
        remaining["remaining"] -= 1
        return True
    return False


def assign_veteran(rng: Random, scenario: ScenarioTemplate, age: int, remaining: Counter[str]) -> bool:
    if scenario.require_veteran:
        if remaining["remaining"] > 0:
            remaining["remaining"] -= 1
        return True
    if remaining["remaining"] <= 0 or age < 30:
        return False
    if rng.random() < 0.03:
        remaining["remaining"] -= 1
        return True
    return False


def assign_disability(rng: Random, scenario: ScenarioTemplate, age: int, remaining: Counter[str]) -> tuple[bool, bool]:
    if scenario.require_disability:
        if remaining["remaining"] > 0:
            remaining["remaining"] -= 1
        return True, scenario.severe_disability
    if remaining["remaining"] <= 0:
        return False, False
    probability = 0.05 if age < 65 else 0.14
    if rng.random() < probability:
        remaining["remaining"] -= 1
        return True, rng.random() < 0.5
    return False, False


def assign_broadband(rng: Random, remaining_without: Counter[str]) -> bool:
    if remaining_without["remaining"] <= 0:
        return True
    if rng.random() < 0.15:
        remaining_without["remaining"] -= 1
        return False
    return True


def assign_language(user_index: int, foreign_born: bool, race_ethnicity: str) -> str:
    if user_index in LANGUAGE_OVERRIDES:
        return LANGUAGE_OVERRIDES[user_index]
    if foreign_born and race_ethnicity == "Hispanic or Latino":
        return "Spanish"
    return "English"


def category_priority(categories: list[str]) -> list[str]:
    order = [
        "children_families",
        "death",
        "disabilities",
        "disasters",
        "education",
        "food",
        "health",
        "housing_utilities",
        "jobs_unemployment",
        "military_veterans",
        "retirement_seniors",
        "welfare_cash_assistance",
    ]
    seen = []
    for key in order:
        if key in categories:
            seen.append(key)
    return seen


def build_selected_categories(
    scenario: ScenarioTemplate,
    *,
    age: int,
    dependents_under_18: int,
    veteran: bool,
    disability: bool,
    limited_income: bool,
    housing_burden: bool,
    death_event: bool,
    disaster_event: bool,
    student_status: str,
    employment_status: str,
    insurance_status: str,
) -> list[str]:
    categories = list(scenario.base_categories)
    if dependents_under_18 > 0:
        categories.append("children_families")
    if age >= 62:
        categories.append("retirement_seniors")
    if veteran:
        categories.append("military_veterans")
    if disability:
        categories.extend(["disabilities", "health"])
    if limited_income:
        categories.extend(["food", "welfare_cash_assistance"])
    if housing_burden:
        categories.append("housing_utilities")
    if death_event:
        categories.append("death")
    if disaster_event:
        categories.append("disasters")
    if student_status != "not_a_student":
        categories.append("education")
    if employment_status in {"recently_laid_off", "unemployed_looking", "job_training"}:
        categories.append("jobs_unemployment")
    if insurance_status in {"uninsured", "medicaid_or_public", "dual_eligible", "medicare", "va_or_tricare"}:
        categories.append("health")
    return category_priority(sorted(set(categories)))


def build_current_app_answers(
    *,
    birth_date: str,
    age: int,
    income_limited: bool,
    disability: bool,
    severe_disability: bool,
    veteran: bool,
    service_connected_disability: bool,
    death_event: bool,
    rng: Random,
) -> dict[str, Any]:
    paid_into_ss = "Yes" if age >= 24 and rng.random() < 0.85 else "No"
    if age >= 62:
        paid_into_ss = "Yes"
    answers = {
        "applicant_date_of_birth": birth_date,
        "applicant_paid_into_SS": paid_into_ss,
        "applicant_income": "Yes" if income_limited else "No",
        "applicant_disability": "Yes" if disability else "No",
        "applicant_ability_to_work": "Yes" if severe_disability else "No",
        "applicant_served_in_active_military": "Yes" if veteran else "No",
        "applicant_service_disability": "Yes" if service_connected_disability else "No",
        "applicant_dolo": "Yes" if death_event else "No",
        "deceased_date_of_death": None,
        "deceased_died_of_COVID": None,
        "deceased_death_location_is_US": None,
    }
    if death_event:
        death_year = rng.choice([2020, 2021, 2022, 2023, 2024, 2025, 2026])
        death_month = rng.randint(1, 12)
        death_day = rng.randint(1, 28)
        answers["deceased_date_of_death"] = date(death_year, death_month, death_day).isoformat()
        covid = death_year <= 2022 and rng.random() < 0.5
        answers["deceased_died_of_COVID"] = "Yes" if covid else "No"
        answers["deceased_death_location_is_US"] = "Yes"
    return answers


def persona_title(scenario: ScenarioTemplate, age: int, dependents_under_18: int) -> str:
    titles = {
        "working_parent_housing_cost": "Working parent with high housing costs",
        "student_low_income": "Low-income student or trainee",
        "senior_fixed_income": "Older adult on a fixed income",
        "disabled_worker": "Adult with a work-limiting disability",
        "unemployed_renter": "Recently unemployed renter",
        "veteran_household": "Veteran household navigating benefits",
        "disaster_recovery": "Household recovering from a disaster",
        "survivor_funeral": "Survivor handling funeral costs",
        "general_low_income": "Low-income adult seeking support",
        "caregiver_health": "Caregiver balancing family and health needs",
        "reskilling_worker": "Worker pursuing reskilling support",
    }
    title = titles[scenario.key]
    if scenario.key == "working_parent_housing_cost" and dependents_under_18 >= 2:
        return f"{title} with {dependents_under_18} children"
    if scenario.key == "senior_fixed_income" and age >= 75:
        return "Older senior on a fixed income"
    return title


def background_summary(
    *,
    age: int,
    race_ethnicity: str,
    state_code: str,
    employment_status: str,
    categories: list[str],
    household_size: int,
    dependents_under_18: int,
) -> str:
    parts = [
        f"{age}-year-old applicant in {state_code}",
        race_ethnicity.lower(),
        employment_status.replace("_", " "),
        f"household of {household_size}",
    ]
    if dependents_under_18:
        parts.append(f"{dependents_under_18} dependent child{'ren' if dependents_under_18 != 1 else ''}")
    parts.append("focused on " + ", ".join(categories[:3]).replace("_", " "))
    return "; ".join(parts) + "."


def generate_users() -> dict[str, Any]:
    rng = Random(SEED)
    age_quota = AGE_BAND_QUOTAS.copy()
    sex_quota = SEX_QUOTAS.copy()
    race_quota = RACE_QUOTAS.copy()
    region_quota = REGION_QUOTAS.copy()
    region_rotation: dict[str, int] = {}
    foreign_born_remaining = Counter({"remaining": 7})
    veteran_remaining = Counter({"remaining": 3})
    disability_remaining = Counter({"remaining": 7})
    no_broadband_remaining = Counter({"remaining": 5})
    bachelors_remaining = Counter({"remaining": 16})

    users: list[dict[str, Any]] = []
    templates = scenario_plan()
    rng.shuffle(templates)

    for index, template in enumerate(templates, start=1):
        age_band = weighted_pick(rng, age_quota, template.allowed_age_bands)
        age = random_age_in_band(rng, age_band)
        if template.require_senior and age < 62:
            age = max(age, 62)
        birth_date = make_birth_date(rng, age)

        sex_at_birth = weighted_pick(rng, sex_quota)
        gender_identity = GENDER_OVERRIDES.get(index, sex_at_birth)
        race_ethnicity = weighted_pick(rng, race_quota)
        region = weighted_pick(rng, region_quota)
        state_code = rotate_state(region, region_rotation)

        household_size, dependents_under_18, marital_status = determine_household(rng, template, age)
        employment_status = determine_employment_status(rng, template, age)
        veteran = assign_veteran(rng, template, age, veteran_remaining)
        disability, severe_disability = assign_disability(rng, template, age, disability_remaining)
        service_connected_disability = bool(veteran and disability and rng.random() < 0.6)
        foreign_born = assign_foreign_born(rng, race_ethnicity, foreign_born_remaining)
        preferred_language = assign_language(index, foreign_born, race_ethnicity)
        broadband_access = assign_broadband(rng, no_broadband_remaining)

        housing_status, monthly_housing_cost, housing_burden, utility_arrears = determine_housing(rng, template, age)
        annual_income = determine_income(rng, template, household_size, employment_status)
        poverty_like = annual_income <= poverty_like_threshold(household_size)
        limited_income = annual_income <= limited_income_threshold(household_size) or template.require_low_income
        education_level = infer_education_level(rng, age, template, bachelors_remaining)

        student_status = "not_a_student"
        if template.require_student:
            student_status = rng.choice(["community_college", "four_year_college", "certificate_program"])
        elif template.key == "reskilling_worker":
            student_status = rng.choice(["job_training_program", "certificate_program", "not_a_student"])

        death_event = template.require_death_event
        disaster_event = template.require_disaster
        insurance_status = determine_insurance(rng, template, age, veteran, disability, limited_income)

        selected_categories = build_selected_categories(
            template,
            age=age,
            dependents_under_18=dependents_under_18,
            veteran=veteran,
            disability=disability,
            limited_income=limited_income,
            housing_burden=housing_burden,
            death_event=death_event,
            disaster_event=disaster_event,
            student_status=student_status,
            employment_status=employment_status,
            insurance_status=insurance_status,
        )

        scope = template.likely_scope
        if template.require_senior and veteran:
            scope = "both"

        current_app_answers = build_current_app_answers(
            birth_date=birth_date,
            age=age,
            income_limited=limited_income,
            disability=disability,
            severe_disability=severe_disability,
            veteran=veteran,
            service_connected_disability=service_connected_disability,
            death_event=death_event,
            rng=rng,
        )

        user = {
            "synthetic_user_id": f"syn-{index:03d}",
            "full_name": f"Synthetic User {index:03d}",
            "persona_title": persona_title(template, age, dependents_under_18),
            "scenario_key": template.key,
            "selected_scope": scope,
            "selected_state_code": state_code,
            "region": STATE_TO_REGION[state_code],
            "preferred_language": preferred_language,
            "breadth_value": round(rng.choice([0.15, 0.35, 0.5, 0.7, 0.9]), 2),
            "depth_value": round(rng.choice([0.15, 0.35, 0.5, 0.7, 0.9]), 2),
            "selected_categories": selected_categories,
            "demographics": {
                "age": age,
                "age_band": age_band,
                "date_of_birth": birth_date,
                "sex_at_birth": sex_at_birth,
                "gender_identity": gender_identity,
                "race_ethnicity": race_ethnicity,
                "foreign_born": foreign_born,
                "education_level": education_level,
                "marital_status": marital_status,
            },
            "household": {
                "household_size": household_size,
                "dependents_under_18": dependents_under_18,
                "housing_status": housing_status,
                "monthly_housing_cost_usd": monthly_housing_cost,
                "housing_cost_burdened": housing_burden,
                "utility_arrears": utility_arrears,
                "broadband_access": broadband_access,
            },
            "economic_profile": {
                "employment_status": employment_status,
                "annual_income_usd": annual_income,
                "poverty_like_status": poverty_like,
                "limited_income_screen": limited_income,
                "student_status": student_status,
                "insurance_status": insurance_status,
            },
            "benefit_relevant_flags": {
                "veteran": veteran,
                "service_connected_disability": service_connected_disability,
                "disability": disability,
                "severe_work_limitation": severe_disability,
                "recent_job_loss": template.require_recent_job_loss,
                "recent_family_death": death_event,
                "recent_disaster_impact": disaster_event,
            },
            "current_app_answers": current_app_answers,
            "expanded_answers": {
                "household_size": household_size,
                "dependents_under_18": dependents_under_18,
                "current_student_status": student_status,
                "employment_status": employment_status,
                "annual_income_usd": annual_income,
                "limited_income_screen": "Yes" if limited_income else "No",
                "housing_status": housing_status,
                "monthly_housing_cost_usd": monthly_housing_cost,
                "housing_cost_burdened": "Yes" if housing_burden else "No",
                "utility_arrears": "Yes" if utility_arrears else "No",
                "broadband_access": "Yes" if broadband_access else "No",
                "insurance_status": insurance_status,
                "foreign_born": "Yes" if foreign_born else "No",
                "preferred_language": preferred_language,
                "recent_job_loss": "Yes" if template.require_recent_job_loss else "No",
                "recent_disaster_impact": "Yes" if disaster_event else "No",
                "recent_family_death": "Yes" if death_event else "No",
                "funeral_expenses_incurred": "Yes" if death_event else "No",
            },
            "background_summary": background_summary(
                age=age,
                race_ethnicity=race_ethnicity,
                state_code=state_code,
                employment_status=employment_status,
                categories=selected_categories,
                household_size=household_size,
                dependents_under_18=dependents_under_18,
            ),
        }
        users.append(user)

    return {
        "meta": {
            "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "reference_date": REFERENCE_DATE.isoformat(),
            "seed": SEED,
            "user_count": USER_COUNT,
            "note": (
                "This cohort is statistically informed on core national demographic patterns, "
                "but benefit-relevant conditions are intentionally enriched so every product category is exercised."
            ),
            "sources": SOURCE_URLS,
        },
        "users": users,
    }


def flatten_for_csv(user: dict[str, Any]) -> dict[str, Any]:
    row = {
        "synthetic_user_id": user["synthetic_user_id"],
        "full_name": user["full_name"],
        "persona_title": user["persona_title"],
        "scenario_key": user["scenario_key"],
        "selected_scope": user["selected_scope"],
        "selected_state_code": user["selected_state_code"],
        "region": user["region"],
        "preferred_language": user["preferred_language"],
        "breadth_value": user["breadth_value"],
        "depth_value": user["depth_value"],
        "selected_categories": "|".join(user["selected_categories"]),
        "background_summary": user["background_summary"],
    }
    for section_key in ("demographics", "household", "economic_profile", "benefit_relevant_flags"):
        for key, value in user[section_key].items():
            row[f"{section_key}.{key}"] = value
    for key, value in user["current_app_answers"].items():
        row[f"current_app_answers.{key}"] = value
    for key, value in user["expanded_answers"].items():
        row[f"expanded_answers.{key}"] = value
    return row


def summarize(users: list[dict[str, Any]]) -> dict[str, Any]:
    age_band_counts = Counter(user["demographics"]["age_band"] for user in users)
    sex_counts = Counter(user["demographics"]["sex_at_birth"] for user in users)
    race_counts = Counter(user["demographics"]["race_ethnicity"] for user in users)
    scope_counts = Counter(user["selected_scope"] for user in users)
    region_counts = Counter(user["region"] for user in users)
    category_counts = Counter(category for user in users for category in user["selected_categories"])

    limited_income_count = sum(1 for user in users if user["economic_profile"]["limited_income_screen"])
    poverty_like_count = sum(1 for user in users if user["economic_profile"]["poverty_like_status"])
    veteran_count = sum(1 for user in users if user["benefit_relevant_flags"]["veteran"])
    disability_count = sum(1 for user in users if user["benefit_relevant_flags"]["disability"])
    children_count = sum(1 for user in users if user["household"]["dependents_under_18"] > 0)
    foreign_born_count = sum(1 for user in users if user["demographics"]["foreign_born"])
    broadband_count = sum(1 for user in users if user["household"]["broadband_access"])
    bachelors_count = sum(
        1
        for user in users
        if user["demographics"]["education_level"] in {"bachelors", "graduate_degree"}
    )
    labor_force_count = sum(
        1
        for user in users
        if user["economic_profile"]["employment_status"]
        in {
            "employed_full_time",
            "part_time_worker",
            "student_part_time_worker",
            "unemployed_looking",
            "recently_laid_off",
            "job_training",
            "part_time_due_to_disability",
        }
    )

    return {
        "age_band_counts": age_band_counts,
        "sex_counts": sex_counts,
        "race_counts": race_counts,
        "scope_counts": scope_counts,
        "region_counts": region_counts,
        "category_counts": category_counts,
        "limited_income_count": limited_income_count,
        "poverty_like_count": poverty_like_count,
        "veteran_count": veteran_count,
        "disability_count": disability_count,
        "children_count": children_count,
        "foreign_born_count": foreign_born_count,
        "broadband_count": broadband_count,
        "bachelors_count": bachelors_count,
        "labor_force_count": labor_force_count,
    }


def format_counter(counter: Counter[str], total: int) -> str:
    lines = []
    for key, value in counter.most_common():
        pct = round(value / total * 100, 1)
        lines.append(f"| {key} | {value} | {pct}% |")
    return "\n".join(lines)


def build_summary_markdown(payload: dict[str, Any]) -> str:
    users = payload["users"]
    total = len(users)
    summary = summarize(users)

    benchmark_rows = [
        ("Female", f"{summary['sex_counts']['female'] / total * 100:.1f}%", f"{BENCHMARKS['female_pct']}%"),
        ("Age 65+", f"{sum(1 for user in users if user['demographics']['age'] >= 65) / total * 100:.1f}%", f"{BENCHMARKS['age_65_plus_pct']}%"),
        ("Foreign-born", f"{summary['foreign_born_count'] / total * 100:.1f}%", f"{BENCHMARKS['foreign_born_pct']}%"),
        ("Bachelor's or higher", f"{summary['bachelors_count'] / total * 100:.1f}%", f"{BENCHMARKS['bachelors_or_higher_pct']}%"),
        ("Broadband access", f"{summary['broadband_count'] / total * 100:.1f}%", f"{BENCHMARKS['broadband_pct']}%"),
        ("In labor force", f"{summary['labor_force_count'] / total * 100:.1f}%", f"{BENCHMARKS['labor_force_pct']}%"),
    ]

    lines = [
        "# Synthetic User Cohort",
        "",
        f"Generated {total} synthetic user profiles with seed `{payload['meta']['seed']}`.",
        "",
        "This cohort is demographically benchmarked at a high level against official national statistics, but benefit-need conditions are intentionally enriched so all benefit categories are exercised during product testing.",
        "",
        "## Files",
        "",
        "- `data/synthetic_users_v1.json`: nested JSON payload",
        "- `data/synthetic_users_v1.csv`: flattened CSV export",
        "- `docs/synthetic-users-summary.md`: this summary",
        "",
        "## Benchmark Alignment",
        "",
        "| Measure | Cohort | Official benchmark |",
        "| --- | ---: | ---: |",
    ]
    for label, cohort, benchmark in benchmark_rows:
        lines.append(f"| {label} | {cohort} | {benchmark} |")

    lines.extend(
        [
            "",
            "## Scope Mix",
            "",
            "| Scope | Count | Share |",
            "| --- | ---: | ---: |",
            format_counter(summary["scope_counts"], total),
            "",
            "## Age Bands",
            "",
            "| Age band | Count | Share |",
            "| --- | ---: | ---: |",
            format_counter(summary["age_band_counts"], total),
            "",
            "## Race and Ethnicity",
            "",
            "| Group | Count | Share |",
            "| --- | ---: | ---: |",
            format_counter(summary["race_counts"], total),
            "",
            "## Selected Benefit Categories",
            "",
            "| Category | Count | Share of users selecting |",
            "| --- | ---: | ---: |",
            format_counter(summary["category_counts"], total),
            "",
            "## Household and Need Flags",
            "",
            f"- Households with dependent children: {summary['children_count']} of {total} ({summary['children_count'] / total * 100:.1f}%)",
            f"- Limited-income screen positive: {summary['limited_income_count']} of {total} ({summary['limited_income_count'] / total * 100:.1f}%)",
            f"- Poverty-like status positive: {summary['poverty_like_count']} of {total} ({summary['poverty_like_count'] / total * 100:.1f}%)",
            f"- Veteran profiles: {summary['veteran_count']} of {total} ({summary['veteran_count'] / total * 100:.1f}%)",
            f"- Disability profiles: {summary['disability_count']} of {total} ({summary['disability_count'] / total * 100:.1f}%)",
            f"- Foreign-born profiles: {summary['foreign_born_count']} of {total} ({summary['foreign_born_count'] / total * 100:.1f}%)",
            f"- Broadband access: {summary['broadband_count']} of {total} ({summary['broadband_count'] / total * 100:.1f}%)",
            "",
            "## Official Sources Used For Benchmarking",
            "",
        ]
    )
    for url in SOURCE_URLS:
        lines.append(f"- {url}")
    lines.extend(
        [
            "",
            "## Important Caveat",
            "",
            "These are synthetic test users. They are not a formally weighted microdata sample of the U.S. population, and they intentionally over-represent benefit-relevant circumstances so the product can be tested across all benefit categories.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    json_path = DATA_DIR / "synthetic_users_v1.json"
    csv_path = DATA_DIR / "synthetic_users_v1.csv"
    summary_path = DOCS_DIR / "synthetic-users-summary.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    rows = [flatten_for_csv(user) for user in payload["users"]]
    fieldnames = list(rows[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with summary_path.open("w", encoding="utf-8") as handle:
        handle.write(build_summary_markdown(payload))


def main() -> None:
    payload = generate_users()
    write_outputs(payload)
    print(json.dumps({"users": len(payload["users"]), "seed": payload["meta"]["seed"]}, indent=2))


if __name__ == "__main__":
    main()
