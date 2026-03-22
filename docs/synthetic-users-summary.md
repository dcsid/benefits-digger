# Synthetic User Cohort

Generated 50 synthetic user profiles with seed `20260321`.

This cohort is demographically benchmarked at a high level against official national statistics, but benefit-need conditions are intentionally enriched so all benefit categories are exercised during product testing.

## Files

- `data/synthetic_users_v1.json`: nested JSON payload
- `data/synthetic_users_v1.csv`: flattened CSV export
- `docs/synthetic-users-summary.md`: this summary

## Benchmark Alignment

| Measure | Cohort | Official benchmark |
| --- | ---: | ---: |
| Female | 50.0% | 50.5% |
| Age 65+ | 18.0% | 18.0% |
| Foreign-born | 14.0% | 14.1% |
| Bachelor's or higher | 34.0% | 35.7% |
| Broadband access | 90.0% | 91.0% |
| In labor force | 66.0% | 63.0% |

## Scope Mix

| Scope | Count | Share |
| --- | ---: | ---: |
| both | 37 | 74.0% |
| federal | 10 | 20.0% |
| state | 3 | 6.0% |

## Age Bands

| Age band | Count | Share |
| --- | ---: | ---: |
| 25-34 | 10 | 20.0% |
| 35-44 | 9 | 18.0% |
| 45-54 | 8 | 16.0% |
| 55-64 | 8 | 16.0% |
| 65-74 | 6 | 12.0% |
| 18-24 | 6 | 12.0% |
| 75+ | 3 | 6.0% |

## Race and Ethnicity

| Group | Count | Share |
| --- | ---: | ---: |
| White, non-Hispanic | 28 | 56.0% |
| Hispanic or Latino | 10 | 20.0% |
| Black, non-Hispanic | 7 | 14.0% |
| Asian, non-Hispanic | 3 | 6.0% |
| American Indian or Alaska Native | 1 | 2.0% |
| Multiracial, non-Hispanic | 1 | 2.0% |

## Selected Benefit Categories

| Category | Count | Share of users selecting |
| --- | ---: | ---: |
| health | 42 | 84.0% |
| food | 38 | 76.0% |
| welfare_cash_assistance | 36 | 72.0% |
| housing_utilities | 32 | 64.0% |
| retirement_seniors | 14 | 28.0% |
| children_families | 10 | 20.0% |
| jobs_unemployment | 9 | 18.0% |
| education | 9 | 18.0% |
| disabilities | 8 | 16.0% |
| military_veterans | 5 | 10.0% |
| death | 3 | 6.0% |
| disasters | 3 | 6.0% |

## Household and Need Flags

- Households with dependent children: 10 of 50 (20.0%)
- Limited-income screen positive: 36 of 50 (72.0%)
- Poverty-like status positive: 23 of 50 (46.0%)
- Veteran profiles: 5 of 50 (10.0%)
- Disability profiles: 8 of 50 (16.0%)
- Foreign-born profiles: 7 of 50 (14.0%)
- Broadband access: 45 of 50 (90.0%)

## Official Sources Used For Benchmarking

- https://www.census.gov/quickfacts/fact/table/US/PST045225
- https://www.census.gov/newsroom/press-releases/2025/families-and-living-arrangements.html
- https://nces.ed.gov/programs/coe/indicator/cpb/college-enrollment-rate

## Important Caveat

These are synthetic test users. They are not a formally weighted microdata sample of the U.S. population, and they intentionally over-represent benefit-relevant circumstances so the product can be tested across all benefit categories.
