FEDERAL_SAMPLE_QUESTIONS = [
    {
        "key": "applicant_date_of_birth",
        "prompt": "What is your date of birth?",
        "hint": "For example: 1990-01-20",
        "input_type": "date",
        "sensitivity_level": "medium",
        "options": None,
    },
    {
        "key": "applicant_paid_into_SS",
        "prompt": "Did you ever work and pay U.S. Social Security taxes?",
        "hint": None,
        "input_type": "radio",
        "sensitivity_level": "low",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
    {
        "key": "applicant_income",
        "prompt": "Do you have limited income and resources?",
        "hint": "This is a broad screening question, not a final determination.",
        "input_type": "radio",
        "sensitivity_level": "medium",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
    {
        "key": "applicant_disability",
        "prompt": "Do you have a disability or qualifying illness?",
        "hint": None,
        "input_type": "radio",
        "sensitivity_level": "medium",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
    {
        "key": "applicant_ability_to_work",
        "prompt": "Are you unable to work for a year or more because of your disability?",
        "hint": None,
        "input_type": "radio",
        "sensitivity_level": "medium",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
    {
        "key": "applicant_served_in_active_military",
        "prompt": "Did you serve in the active military, naval, or air service?",
        "hint": None,
        "input_type": "radio",
        "sensitivity_level": "low",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
    {
        "key": "applicant_service_disability",
        "prompt": "Was your disability caused or made worse by your active-duty military service?",
        "hint": None,
        "input_type": "radio",
        "sensitivity_level": "medium",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
    {
        "key": "applicant_dolo",
        "prompt": "Did you recently experience the death of an immediate family member?",
        "hint": None,
        "input_type": "radio",
        "sensitivity_level": "medium",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
    {
        "key": "deceased_date_of_death",
        "prompt": "What was the date of death?",
        "hint": "If you do not know the exact date, enter an approximate one.",
        "input_type": "date",
        "sensitivity_level": "medium",
        "options": None,
    },
    {
        "key": "deceased_died_of_COVID",
        "prompt": "Was the person's death COVID-19 related?",
        "hint": None,
        "input_type": "radio",
        "sensitivity_level": "medium",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
    {
        "key": "deceased_death_location_is_US",
        "prompt": "Did the person die in the U.S.?",
        "hint": "Including Puerto Rico and U.S. territories.",
        "input_type": "radio",
        "sensitivity_level": "low",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
]


FEDERAL_SAMPLE_BENEFITS = [
    {
        "title": "Social Security retirement benefits",
        "summary": "Monthly retirement income for people who worked and paid Social Security taxes.",
        "agency_title": "Social Security Administration",
        "source_link": "https://www.usa.gov/retirement-benefits",
        "category": "retirement",
        "family": "social_security",
        "eligibility": [
            {
                "criteria_key": "applicant_paid_into_SS",
                "label": "You worked and paid Social Security taxes.",
                "acceptable_values": ["Yes"],
            },
            {
                "criteria_key": "applicant_date_of_birth",
                "label": "You are at least retirement age.",
                "acceptable_values": ["<=1961-12-31"],
            },
        ],
        "amount_display": "Monthly amount depends on work history and claiming age.",
        "documents": [
            {"name": "Social Security card or number", "type": "required", "description": "Your 9-digit SSN"},
            {"name": "Proof of age", "type": "required", "description": "Birth certificate or passport"},
            {"name": "W-2 forms or self-employment tax returns", "type": "required", "description": "Most recent year's earnings records"},
            {"name": "Bank account information", "type": "recommended", "description": "For direct deposit of benefits"},
        ],
    },
    {
        "title": "Social Security Disability Insurance (SSDI)",
        "summary": "Monthly disability benefits for people who paid into Social Security and cannot work due to disability.",
        "agency_title": "Social Security Administration",
        "source_link": "https://www.usa.gov/disability-benefits",
        "category": "disability",
        "family": "ssdi",
        "eligibility": [
            {
                "criteria_key": "applicant_paid_into_SS",
                "label": "You worked and paid Social Security taxes.",
                "acceptable_values": ["Yes"],
            },
            {
                "criteria_key": "applicant_disability",
                "label": "You have a disability or qualifying illness.",
                "acceptable_values": ["Yes"],
            },
            {
                "criteria_key": "applicant_ability_to_work",
                "label": "You cannot work for a year or more because of your disability.",
                "acceptable_values": ["Yes"],
            },
        ],
        "amount_display": "Monthly amount depends on work history.",
        "documents": [
            {"name": "Social Security card or number", "type": "required", "description": "Your 9-digit SSN"},
            {"name": "Medical records", "type": "required", "description": "Documentation of your disability from doctors, hospitals, or clinics"},
            {"name": "Proof of age", "type": "required", "description": "Birth certificate or passport"},
            {"name": "W-2 forms or self-employment tax returns", "type": "required", "description": "Earnings records for the current and prior year"},
            {"name": "Bank account information", "type": "recommended", "description": "For direct deposit of benefits"},
        ],
    },
    {
        "title": "Supplemental Security Income (SSI)",
        "summary": "Monthly support for older adults and people with disabilities who have limited income and resources.",
        "agency_title": "Social Security Administration",
        "source_link": "https://www.usa.gov/disability-benefits",
        "category": "cash",
        "family": "ssi",
        "eligibility": [
            {
                "criteria_key": "applicant_income",
                "label": "You have limited income and resources.",
                "acceptable_values": ["Yes"],
            },
            {
                "criteria_key": "applicant_disability",
                "label": "You have a disability or qualifying illness.",
                "acceptable_values": ["Yes"],
            },
        ],
        "amount_display": "Up to $943/month for individuals, $1,415/month for couples (2024 rates).",
        "amount_formula": {
            "type": "fixed",
            "amount": 943,
        },
        "amount_period": "monthly",
        "amount_max": 943,
        "documents": [
            {"name": "Social Security card or number", "type": "required", "description": "Your 9-digit SSN"},
            {"name": "Proof of income and resources", "type": "required", "description": "Pay stubs, bank statements, or benefit award letters"},
            {"name": "Medical records", "type": "required", "description": "Documentation of your disability"},
            {"name": "Proof of living arrangement", "type": "required", "description": "Lease, mortgage statement, or letter from landlord"},
            {"name": "Proof of citizenship or immigration status", "type": "required", "description": "Birth certificate, passport, or immigration documents"},
        ],
    },
    {
        "title": "VA disability compensation",
        "summary": "Tax-free monthly payments for veterans whose disability was caused or worsened by active-duty service.",
        "agency_title": "U.S. Department of Veterans Affairs",
        "source_link": "https://www.va.gov/disability/",
        "category": "veteran",
        "family": "va_disability",
        "eligibility": [
            {
                "criteria_key": "applicant_served_in_active_military",
                "label": "You served in the active military.",
                "acceptable_values": ["Yes"],
            },
            {
                "criteria_key": "applicant_service_disability",
                "label": "Your disability was caused or worsened by active-duty service.",
                "acceptable_values": ["Yes"],
            },
        ],
        "amount_display": "Amount depends on disability rating and dependents.",
        "documents": [
            {"name": "DD-214 (discharge papers)", "type": "required", "description": "Certificate of Release or Discharge from Active Duty"},
            {"name": "Medical records", "type": "required", "description": "Evidence linking your disability to military service"},
            {"name": "VA Form 21-526EZ", "type": "required", "description": "Application for Disability Compensation"},
            {"name": "Bank account information", "type": "recommended", "description": "For direct deposit of benefits"},
        ],
    },
    {
        "title": "Survivor benefits",
        "summary": "Monthly Social Security payments for eligible family members after a worker dies.",
        "agency_title": "Social Security Administration",
        "source_link": "https://www.usa.gov/death-benefits",
        "category": "survivor",
        "family": "survivor",
        "eligibility": [
            {
                "criteria_key": "applicant_dolo",
                "label": "You recently experienced the death of a family member.",
                "acceptable_values": ["Yes"],
            }
        ],
        "amount_display": "Monthly amount depends on the worker's record and your relationship.",
        "documents": [
            {"name": "Deceased's Social Security number", "type": "required", "description": "The worker's SSN"},
            {"name": "Death certificate", "type": "required", "description": "Certified copy of the death certificate"},
            {"name": "Proof of relationship", "type": "required", "description": "Marriage certificate, birth certificate, or adoption papers"},
            {"name": "Bank account information", "type": "recommended", "description": "For direct deposit of benefits"},
        ],
    },
    {
        "title": "COVID-19 funeral assistance",
        "summary": "Financial help for funeral or burial costs for someone who died of COVID-19 in the U.S.",
        "agency_title": "Federal Emergency Management Agency (FEMA)",
        "source_link": "https://www.fema.gov/disaster/coronavirus/economic/funeral-assistance",
        "category": "survivor",
        "family": "funeral_assistance",
        "eligibility": [
            {
                "criteria_key": "deceased_died_of_COVID",
                "label": "The deceased's death was COVID-19 related.",
                "acceptable_values": ["Yes"],
            },
            {
                "criteria_key": "deceased_death_location_is_US",
                "label": "The deceased died in the U.S.",
                "acceptable_values": ["Yes"],
            },
            {
                "criteria_key": "deceased_date_of_death",
                "label": "The deceased died after May 20, 2020.",
                "acceptable_values": [">=2020-05-20"],
            },
        ],
        "amount_display": "Reimbursement amount depends on eligible funeral expenses.",
        "documents": [
            {"name": "Death certificate", "type": "required", "description": "Must attribute the death to COVID-19"},
            {"name": "Funeral expense receipts", "type": "required", "description": "Itemized receipts or contracts from funeral providers"},
            {"name": "Proof of U.S. residency", "type": "required", "description": "For the person who incurred the funeral expenses"},
            {"name": "FEMA application number", "type": "recommended", "description": "If you previously applied for other FEMA assistance"},
        ],
    },
]


STATE_DIRECTORY_SAMPLE = [
    {"code": "CA", "name": "California", "url": "https://www.cdss.ca.gov/"},
    {"code": "NY", "name": "New York", "url": "https://www.ny.gov/"},
    {"code": "TX", "name": "Texas", "url": "https://www.hhs.texas.gov/"},
]


# ---------------------------------------------------------------------------
# Depth-dependent question variants
# ---------------------------------------------------------------------------
# Each entry overrides how a question is presented at a given depth tier.
# Questions without a variant for the active tier fall back to the base
# Question row (backward-compatible).  The "normalizer" field names a
# function in app.normalizers that converts the detailed answer to the
# canonical Yes/No format that eligibility rules already expect.
# ---------------------------------------------------------------------------

QUESTION_VARIANTS = [
    # ── applicant_income ──────────────────────────────────────────────
    {
        "question_key": "applicant_income",
        "depth_tier": "simple",
        "prompt": "Do you have limited income and resources?",
        "hint": "Answer yes if your household struggles to cover basic needs.",
        "input_type": "radio",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
        "normalizer": None,
    },
    {
        "question_key": "applicant_income",
        "depth_tier": "detailed",
        "prompt": "What is your approximate annual household income?",
        "hint": "For reference, the 2024 federal poverty level is $15,060/year for a single-person household. Many programs use 130–200% of this threshold.",
        "input_type": "currency",
        "options": None,
        "normalizer": "yes_if_below_fpl",
    },
    # ── applicant_disability ──────────────────────────────────────────
    {
        "question_key": "applicant_disability",
        "depth_tier": "simple",
        "prompt": "Do you have a disability or qualifying illness?",
        "hint": None,
        "input_type": "radio",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
        "normalizer": None,
    },
    {
        "question_key": "applicant_disability",
        "depth_tier": "detailed",
        "prompt": "What type of disability or condition do you have?",
        "hint": "Select all that apply. Under SSA rules, a qualifying disability must significantly limit your ability to perform basic work activities.",
        "input_type": "select",
        "options": [
            {"label": "Physical disability", "value": "physical"},
            {"label": "Cognitive or intellectual disability", "value": "cognitive"},
            {"label": "Sensory disability (vision/hearing)", "value": "sensory"},
            {"label": "Mental health condition", "value": "mental_health"},
            {"label": "Chronic illness", "value": "chronic_illness"},
            {"label": "None of the above", "value": "none"},
        ],
        "normalizer": "yes_if_any_selected",
    },
    # ── applicant_ability_to_work ─────────────────────────────────────
    {
        "question_key": "applicant_ability_to_work",
        "depth_tier": "simple",
        "prompt": "Are you unable to work for a year or more because of your disability?",
        "hint": None,
        "input_type": "radio",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
        "normalizer": None,
    },
    {
        "question_key": "applicant_ability_to_work",
        "depth_tier": "detailed",
        "prompt": "How many months has your condition prevented you from working?",
        "hint": "SSDI requires inability to engage in substantial gainful activity for at least 12 consecutive months (42 U.S.C. § 423(d)(1)(A)).",
        "input_type": "number",
        "options": None,
        "normalizer": "yes_if_gte_12",
    },
    # ── applicant_date_of_birth ───────────────────────────────────────
    {
        "question_key": "applicant_date_of_birth",
        "depth_tier": "simple",
        "prompt": "What is your approximate age?",
        "hint": "A rough age is enough for a quick check.",
        "input_type": "number",
        "options": None,
        "normalizer": None,
    },
    {
        "question_key": "applicant_date_of_birth",
        "depth_tier": "detailed",
        "prompt": "What is your exact date of birth?",
        "hint": "Full retirement age varies: 66 for those born 1943–1954, increasing to 67 for those born 1960 or later (42 U.S.C. § 416(l)).",
        "input_type": "date",
        "options": None,
        "normalizer": None,
    },
    # ── applicant_served_in_active_military ────────────────────────────
    {
        "question_key": "applicant_served_in_active_military",
        "depth_tier": "simple",
        "prompt": "Are you a military veteran?",
        "hint": None,
        "input_type": "radio",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
        "normalizer": None,
    },
    {
        "question_key": "applicant_served_in_active_military",
        "depth_tier": "detailed",
        "prompt": "Describe your military service (branch, years, and duty status).",
        "hint": "VA benefits require active duty service. Reserve/National Guard service may qualify if activated under federal orders (38 U.S.C. § 101(2)).",
        "input_type": "text",
        "options": None,
        "normalizer": "yes_if_non_empty",
    },
    # ── applicant_service_disability ──────────────────────────────────
    {
        "question_key": "applicant_service_disability",
        "depth_tier": "simple",
        "prompt": "Was your disability related to military service?",
        "hint": None,
        "input_type": "radio",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
        "normalizer": None,
    },
    {
        "question_key": "applicant_service_disability",
        "depth_tier": "detailed",
        "prompt": "Describe how your disability is connected to your military service.",
        "hint": "VA disability compensation requires a service-connected condition with a disability rating of at least 10% (38 U.S.C. § 1110).",
        "input_type": "text",
        "options": None,
        "normalizer": "yes_if_non_empty",
    },
    # ── applicant_dolo (death of loved one) ───────────────────────────
    {
        "question_key": "applicant_dolo",
        "depth_tier": "simple",
        "prompt": "Did you recently lose a family member?",
        "hint": None,
        "input_type": "radio",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
        "normalizer": None,
    },
    {
        "question_key": "applicant_dolo",
        "depth_tier": "detailed",
        "prompt": "Please describe your relationship to the deceased family member.",
        "hint": "Survivor benefits eligibility depends on your relationship to the deceased and their work history (42 U.S.C. § 402).",
        "input_type": "text",
        "options": None,
        "normalizer": "yes_if_non_empty",
    },
    # ── applicant_paid_into_SS ──────────────────────────────────────
    {
        "question_key": "applicant_paid_into_SS",
        "depth_tier": "simple",
        "prompt": "Have you ever worked and paid into Social Security?",
        "hint": None,
        "input_type": "radio",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
        "normalizer": None,
    },
    {
        "question_key": "applicant_paid_into_SS",
        "depth_tier": "detailed",
        "prompt": "Describe your work history and Social Security tax contributions.",
        "hint": "Most jobs in the U.S. withhold Social Security taxes (FICA). You generally need 40 work credits (about 10 years) to qualify for retirement benefits.",
        "input_type": "text",
        "options": None,
        "normalizer": "yes_if_non_empty",
    },
    # ── deceased_died_of_COVID ──────────────────────────────────────
    {
        "question_key": "deceased_died_of_COVID",
        "depth_tier": "simple",
        "prompt": "Was the person's death COVID-19 related?",
        "hint": None,
        "input_type": "radio",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
        "normalizer": None,
    },
    {
        "question_key": "deceased_died_of_COVID",
        "depth_tier": "detailed",
        "prompt": "What was the cause of death as listed on the death certificate?",
        "hint": "FEMA funeral assistance requires that the death certificate attribute the death to COVID-19.",
        "input_type": "text",
        "options": None,
        "normalizer": "yes_if_non_empty",
    },
    # ── deceased_death_location_is_US ───────────────────────────────
    {
        "question_key": "deceased_death_location_is_US",
        "depth_tier": "simple",
        "prompt": "Did the person die in the U.S.?",
        "hint": "Including Puerto Rico and U.S. territories.",
        "input_type": "radio",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
        "normalizer": None,
    },
    {
        "question_key": "deceased_death_location_is_US",
        "depth_tier": "detailed",
        "prompt": "In which U.S. state or territory did the person pass away?",
        "hint": "Include Puerto Rico and other U.S. territories. If the person did not die in the U.S., enter 'N/A'.",
        "input_type": "text",
        "options": None,
        "normalizer": "yes_if_non_empty",
    },
]
