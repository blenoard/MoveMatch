# Younes – business rules (service) and behaviour tests
**Suggested commit message:** `Milestone 2: service logic for offers (rules 4, 5, 6, 9) and API tests`

Files to commit: `movematch/service.py`, `tests/test_api.py`. Do not commit this file.

## What you must be able to explain in the coaching
- `service.py` has no HTTP code (no FastAPI) – only rules. Errors are `MoveMatchError` with code `invalid_input` / `not_found` / `conflict`.
- Order of checks in `create_offer`: request exists (404) → company exists (422) → rule 6 request accepts offers (409) → rule 5 one offer per company (409) → rule 4 price within range, limits included (422).
- First offer: request `open` → `offers_received`. Withdrawing the last pending offer: back to `open` (rule 9). Accepted offer → 409 (binding), declined → 409. IDs of deleted offers are never reused.
- `tests/test_api.py` (34 tests): success, invalid input, conflicts; error responses are compared with `data/error-examples.json`. Run: `python -m pytest tests/test_api.py`.
