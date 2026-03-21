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
        "amount_display": "Amount depends on income, living arrangement, and state supplements.",
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
    },
]


STATE_DIRECTORY_SAMPLE = [
    {"code": "CA", "name": "California", "url": "https://www.cdss.ca.gov/"},
    {"code": "NY", "name": "New York", "url": "https://www.ny.gov/"},
    {"code": "TX", "name": "Texas", "url": "https://www.hhs.texas.gov/"},
]
