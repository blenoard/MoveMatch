"""Behaviour checks for the implemented operations: success, invalid input and conflicts.

Run from the repository root:  python -m pytest
The tests use the sample data in data/ and a temporary copy of movematch/seed.json (never your saved data).
Seed (movematch/seed.json): request 1038 `assigned` (offer 305 accepted, 306 declined),
request 1042 `offers_received` (offers 309 and 310 pending), request 1047 `open` (no offers).
Companies: 7 Keller, 8 Rhein Transport, 9 Zügelprofi. The next new offer gets ID 311.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from movematch.api import create_app

DATA = Path(__file__).resolve().parents[1] / "data"
CREATE_OFFER = json.loads((DATA / "create-offer.json").read_text(encoding="utf-8"))
SAVED_OFFER = json.loads((DATA / "offer.json").read_text(encoding="utf-8"))
ERROR_EXAMPLES = json.loads((DATA / "error-examples.json").read_text(encoding="utf-8"))


def company(company_id: int) -> dict:
    """The temporary stand-in for the login."""
    return {"X-Company-Id": str(company_id)}


def planned_error(rule: int, case: str) -> dict:
    """The planned error response for a rule, taken from data/error-examples.json."""
    return next(e for e in ERROR_EXAMPLES if e["rule"] == rule and e["case"].startswith(case))


def assert_matches_plan(response, rule: int, case: str):
    planned = planned_error(rule, case)
    assert response.status_code == planned["httpStatus"]
    assert response.json() == planned["response"]


@pytest.fixture
def data_file(tmp_path):
    return tmp_path / "movematch.json"


@pytest.fixture
def client(data_file):
    with TestClient(create_app(data_file)) as api:
        yield api


# ----- reading moving requests ---------------------------------------------------------------------
def test_read_moving_request_has_derived_reference_and_price_range(client):
    response = client.get("/moving-requests/1042")
    assert response.status_code == 200
    body = response.json()
    assert body["reference"] == "MM-1042"  # derived from the ID, not stored
    assert (body["priceMin"], body["priceMax"], body["volumeM3"]) == (1200, 1600, 10.5)
    assert body["status"] == "offers_received"


def test_list_moving_requests(client):
    response = client.get("/moving-requests")
    assert response.status_code == 200
    assert [r["id"] for r in response.json()] == [1038, 1042, 1047]


def test_read_missing_moving_request_returns_404(client):
    response = client.get("/moving-requests/9999")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Requested resource not found."}


@pytest.mark.parametrize("path", ["/moving-requests/0", "/moving-requests/abc", "/offers/-1"])
def test_invalid_id_in_path_returns_422(client, path):
    response = client.get(path)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


# ----- create an offer: success ----------------------------------------------------------------------
def test_create_offer_returns_the_sample_offer(client):
    """data/create-offer.json sent as company 7 must give exactly data/offer.json."""
    created = client.post("/offers", json=CREATE_OFFER, headers=company(7))
    assert created.status_code == 201
    assert created.json() == SAVED_OFFER
    assert created.headers["Location"] == "/offers/311"
    assert client.get(created.headers["Location"]).json() == SAVED_OFFER


def test_first_offer_moves_an_open_request_to_offers_received(client):
    assert client.get("/moving-requests/1047").json()["status"] == "open"
    created = client.post("/offers", json={"movingRequestId": 1047, "price": 800}, headers=company(7))
    assert created.status_code == 201
    assert created.json()["message"] is None  # the message is optional
    assert client.get("/moving-requests/1047").json()["status"] == "offers_received"


@pytest.mark.parametrize("price", [1200, 1600])  # both limits of the range are allowed
def test_price_at_the_limits_of_the_range_is_accepted(client, price):
    created = client.post("/offers", json={"movingRequestId": 1042, "price": price}, headers=company(7))
    assert created.status_code == 201


# ----- create an offer: invalid input (422) -------------------------------------------------------------
def test_price_above_the_range_is_rejected_like_planned(client):
    response = client.post("/offers", json={**CREATE_OFFER, "price": 1750}, headers=company(7))
    assert_matches_plan(response, 4, "Offer price outside the allowed range")
    assert client.get("/offers/311").status_code == 404  # nothing was saved


def test_price_below_the_range_is_rejected(client):
    response = client.post("/offers", json={**CREATE_OFFER, "price": 1199}, headers=company(7))
    assert response.status_code == 422
    assert response.json() == {"code": "invalid_input", "message": "price: must be between 1200 and 1600 CHF."}


@pytest.mark.parametrize("body", [
    {"movingRequestId": 1042, "price": 0},                      # price must be positive
    {"movingRequestId": 1042, "price": -5},
    {"movingRequestId": 1042, "price": 1450.5},                 # whole CHF only
    {"movingRequestId": 1042, "price": "1450"},                 # a number, not text
    {"movingRequestId": 1042},                                  # price missing
    {"price": 1450},                                            # request missing
    {"movingRequestId": 1042, "price": 1450, "companyId": 7},   # unknown field
    {"movingRequestId": 1042, "price": 1450, "message": "x" * 501},
])
def test_invalid_offer_body_returns_422_and_creates_nothing(client, body):
    response = client.post("/offers", json=body, headers=company(7))
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert isinstance(response.json()["message"], str)
    assert client.get("/offers/311").status_code == 404


def test_missing_company_header_returns_422(client):
    response = client.post("/offers", json=CREATE_OFFER)
    assert response.status_code == 422
    assert "x-company-id" in response.json()["message"].lower()


def test_unknown_company_returns_422(client):
    response = client.post("/offers", json=CREATE_OFFER, headers=company(99))
    assert response.status_code == 422
    assert response.json() == {"code": "invalid_input", "message": "X-Company-Id: unknown company."}


# ----- create an offer: failure cases (404, 409) ------------------------------------------------------------
def test_second_offer_of_the_same_company_is_a_conflict(client):
    # Company 8 already has the pending offer 309 on request 1042 (rule 5).
    response = client.post("/offers", json={"movingRequestId": 1042, "price": 1400}, headers=company(8))
    assert_matches_plan(response, 5, "Company already has an offer")


def test_offer_on_an_assigned_request_is_a_conflict(client):
    # Request 1038 is assigned (rule 6).
    response = client.post("/offers", json={"movingRequestId": 1038, "price": 900}, headers=company(9))
    assert_matches_plan(response, 6, "Request no longer accepts offers")


def test_offer_for_a_missing_request_returns_404(client):
    response = client.post("/offers", json={"movingRequestId": 9999, "price": 1000}, headers=company(7))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# ----- read an offer --------------------------------------------------------------------------------------------
def test_read_offer(client):
    response = client.get("/offers/309")
    assert response.status_code == 200
    assert response.json()["companyId"] == 8 and response.json()["status"] == "pending"


def test_read_missing_offer_returns_404(client):
    assert client.get("/offers/9999").status_code == 404


# ----- withdraw an offer ---------------------------------------------------------------------------------------------
def test_withdraw_last_pending_offer_returns_request_to_open(client):
    created = client.post("/offers", json={"movingRequestId": 1047, "price": 800}, headers=company(7))
    offer_url = created.headers["Location"]
    assert client.get("/moving-requests/1047").json()["status"] == "offers_received"
    deleted = client.delete(offer_url)
    assert deleted.status_code == 204 and deleted.content == b""
    assert client.get(offer_url).status_code == 404
    assert client.get("/moving-requests/1047").json()["status"] == "open"  # rule 9
    # Deleted IDs are not reused, and the company may now submit a new offer (rule 5).
    again = client.post("/offers", json={"movingRequestId": 1047, "price": 850}, headers=company(7))
    assert again.status_code == 201 and again.json()["id"] == created.json()["id"] + 1


def test_withdraw_keeps_request_in_offers_received_while_other_offers_are_pending(client):
    assert client.delete("/offers/309").status_code == 204
    assert client.get("/moving-requests/1042").json()["status"] == "offers_received"  # offer 310 is still pending


def test_withdraw_accepted_offer_is_a_conflict(client):
    response = client.delete("/offers/305")
    assert_matches_plan(response, 9, "Withdraw an accepted offer")
    assert client.get("/offers/305").status_code == 200  # still there


def test_withdraw_declined_offer_is_a_conflict(client):
    response = client.delete("/offers/306")
    assert response.status_code == 409
    assert response.json() == {"code": "conflict", "message": "Only a pending offer can be withdrawn."}


def test_withdraw_missing_offer_returns_404(client):
    assert client.delete("/offers/9999").status_code == 404


# ----- persistence and error format --------------------------------------------------------------------------------------
def test_saved_offer_survives_a_restart(data_file):
    with TestClient(create_app(data_file)) as first:
        created = first.post("/offers", json=CREATE_OFFER, headers=company(7))
    with TestClient(create_app(data_file)) as restarted:  # a new app on the same file = a restart
        assert restarted.get(created.headers["Location"]).json() == SAVED_OFFER


def test_unknown_path_and_wrong_method_use_the_same_error_format(client):
    missing = client.get("/nope")
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"
    wrong = client.put("/offers/309", json=CREATE_OFFER)  # PUT is not part of the API
    assert wrong.status_code == 405 and wrong.json()["code"] == "method_not_allowed"


def test_start_page_redirects_to_the_documentation(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307 and response.headers["location"] == "/docs"
    assert client.get("/docs").status_code == 200
