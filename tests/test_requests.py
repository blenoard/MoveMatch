"""Behaviour checks for the operations added in Milestone 3: furniture catalogue, creating, changing and
deleting moving requests, listing the offers of a request and accepting an offer.

The app runs with a fixed date (20 October 2026), so the sample data in data/ stays valid and the
checks do not depend on the day they are run.
"""
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from movematch.api import create_app

DATA = Path(__file__).resolve().parents[1] / "data"
CREATE_REQUEST = json.loads((DATA / "create-moving-request.json").read_text(encoding="utf-8"))
SAVED_REQUEST = json.loads((DATA / "moving-request.json").read_text(encoding="utf-8"))
FURNITURE_TYPES = json.loads((DATA / "furniture-types.json").read_text(encoding="utf-8"))
ERROR_EXAMPLES = json.loads((DATA / "error-examples.json").read_text(encoding="utf-8"))
TODAY = date(2026, 10, 20)


def customer(customer_id: int) -> dict:
    """The temporary stand-in for the login."""
    return {"X-Customer-Id": str(customer_id)}


def assert_matches_plan(response, rule: int, case: str):
    planned = next(e for e in ERROR_EXAMPLES if e["rule"] == rule and e["case"].startswith(case))
    assert response.status_code == planned["httpStatus"]
    assert response.json() == planned["response"]


@pytest.fixture
def data_file(tmp_path):
    return tmp_path / "movematch.json"


@pytest.fixture
def client(data_file):
    with TestClient(create_app(data_file, today=lambda: TODAY)) as api:
        yield api


# ----- furniture catalogue ---------------------------------------------------------------------------
def test_furniture_types_equal_the_sample_catalogue(client):
    response = client.get("/furniture-types")
    assert response.status_code == 200
    assert response.json() == FURNITURE_TYPES


# ----- create a moving request (Workflow A) ----------------------------------------------------------
def test_create_request_calculates_volume_and_price_range_like_the_sample(client):
    """data/create-moving-request.json sent as customer 1 gives data/moving-request.json with a new ID."""
    created = client.post("/moving-requests", json=CREATE_REQUEST, headers=customer(1))
    assert created.status_code == 201
    body = created.json()
    assert body["id"] == 1048 and body["reference"] == "MM-1048"  # continues after the seed (1047)
    assert created.headers["Location"] == "/moving-requests/1048"
    assert {**body, "id": 1042, "reference": "MM-1042"} == SAVED_REQUEST  # 10.5 m3, CHF 1,200 to 1,600, open
    assert client.get("/moving-requests/1048").json() == body
    assert [r["id"] for r in client.get("/moving-requests").json()] == [1038, 1042, 1047, 1048]


def test_price_range_of_a_short_move_with_lifts(client):
    # 350 + 3 * 10 + 60 * 0.3 = 398 -> 338.3 and 457.7 -> rounded inwards to 350 and 450.
    body = {**CREATE_REQUEST, "distanceKm": 10,
            "fromAddress": {"postalCode": "4051", "city": "Basel", "floor": 4, "hasLift": True},
            "items": [{"furnitureTypeId": 4, "quantity": 2}]}
    created = client.post("/moving-requests", json=body, headers=customer(2))
    assert created.status_code == 201
    assert (created.json()["volumeM3"], created.json()["priceMin"], created.json()["priceMax"]) == (0.3, 350, 450)
    assert created.json()["customerId"] == 2


def test_moving_date_today_is_allowed(client):
    created = client.post("/moving-requests", json={**CREATE_REQUEST, "movingDate": "2026-10-20"}, headers=customer(1))
    assert created.status_code == 201


def test_moving_date_in_the_past_is_rejected_like_planned(client):
    response = client.post("/moving-requests", json={**CREATE_REQUEST, "movingDate": "2026-10-06"},
                           headers=customer(1))
    assert_matches_plan(response, 1, "Moving date lies in the past")
    assert len(client.get("/moving-requests").json()) == 3  # nothing was saved


def test_all_quantities_zero_is_rejected_like_planned(client):
    items = [{"furnitureTypeId": 1, "quantity": 0}, {"furnitureTypeId": 4, "quantity": 0}]
    response = client.post("/moving-requests", json={**CREATE_REQUEST, "items": items}, headers=customer(1))
    assert_matches_plan(response, 2, "No furniture item")


@pytest.mark.parametrize("change", [
    {"items": []},                                           # at least one item
    {"items": [{"furnitureTypeId": 99, "quantity": 1}]},     # unknown furniture type
    {"items": [{"furnitureTypeId": 1, "quantity": 1}, {"furnitureTypeId": 1, "quantity": 2}]},  # listed twice
    {"items": [{"furnitureTypeId": 1, "quantity": 1.5}]},    # whole numbers only
    {"distanceKm": 0},
    {"movingDate": "14.11.2026"},                            # ISO format expected
    {"fromAddress": {"postalCode": "40570", "city": "Basel", "floor": 3, "hasLift": False}},
    {"status": "assigned"},                                  # unknown field: the backend sets the status
])
def test_invalid_request_body_returns_422_and_creates_nothing(client, change):
    response = client.post("/moving-requests", json={**CREATE_REQUEST, **change}, headers=customer(1))
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert len(client.get("/moving-requests").json()) == 3


def test_missing_or_unknown_customer_returns_422(client):
    missing = client.post("/moving-requests", json=CREATE_REQUEST)
    assert missing.status_code == 422 and "x-customer-id" in missing.json()["message"].lower()
    unknown = client.post("/moving-requests", json=CREATE_REQUEST, headers=customer(99))
    assert unknown.status_code == 422
    assert unknown.json() == {"code": "invalid_input", "message": "X-Customer-Id: unknown customer."}


# ----- change a moving request (rule 8) ---------------------------------------------------------------
def test_change_open_request_recalculates_the_price_range(client):
    # Request 1047 is open: Liestal -> Basel, 15 km, 6 m3, CHF 700 to 900.
    body = {**CREATE_REQUEST, "movingDate": "2026-11-21"}
    response = client.put("/moving-requests/1047", json=body)
    assert response.status_code == 200
    changed = response.json()
    assert (changed["volumeM3"], changed["priceMin"], changed["priceMax"]) == (10.5, 1200, 1600)
    assert (changed["id"], changed["customerId"], changed["status"]) == (1047, 2, "open")  # unchanged
    assert client.get("/moving-requests/1047").json() == changed


def test_change_request_with_offers_is_a_conflict_like_planned(client):
    response = client.put("/moving-requests/1042", json=CREATE_REQUEST)
    assert_matches_plan(response, 8, "Edit a request that already has offers")


def test_change_request_checks_input_and_existence(client):
    assert client.put("/moving-requests/9999", json=CREATE_REQUEST).status_code == 404
    past = client.put("/moving-requests/1047", json={**CREATE_REQUEST, "movingDate": "2026-10-06"})
    assert past.status_code == 422
    assert client.get("/moving-requests/1047").json()["movingDate"] == "2026-11-21"  # unchanged


# ----- delete a moving request (rule 8) ----------------------------------------------------------------
def test_delete_request_removes_it_together_with_its_offers(client):
    assert client.delete("/moving-requests/1042").status_code == 204
    assert client.get("/moving-requests/1042").status_code == 404
    assert client.get("/offers/309").status_code == 404 and client.get("/offers/310").status_code == 404
    assert client.get("/offers/305").status_code == 200  # offers of other requests stay


def test_delete_assigned_request_is_a_conflict_like_planned(client):
    response = client.delete("/moving-requests/1038")
    assert_matches_plan(response, 8, "Delete a request that is already assigned")
    assert client.get("/moving-requests/1038").status_code == 200


def test_delete_missing_request_returns_404(client):
    assert client.delete("/moving-requests/9999").status_code == 404


def test_ids_of_deleted_requests_are_not_reused(client):
    first = client.post("/moving-requests", json=CREATE_REQUEST, headers=customer(1)).json()["id"]
    assert client.delete(f"/moving-requests/{first}").status_code == 204
    assert client.post("/moving-requests", json=CREATE_REQUEST, headers=customer(1)).json()["id"] == first + 1


# ----- list the offers of a request --------------------------------------------------------------------
def test_list_offers_of_a_request(client):
    response = client.get("/offers", params={"movingRequestId": 1042})
    assert response.status_code == 200
    assert [(o["id"], o["price"], o["status"]) for o in response.json()] == [(309, 1320, "pending"),
                                                                           (310, 1580, "pending")]
    assert client.get("/offers", params={"movingRequestId": 1047}).json() == []


def test_list_offers_needs_a_valid_request_id(client):
    assert client.get("/offers").status_code == 422
    assert client.get("/offers", params={"movingRequestId": 0}).status_code == 422


# ----- accept an offer (rule 7) ------------------------------------------------------------------------
def test_accept_offer_assigns_the_request_and_declines_the_other_offers(client):
    response = client.post("/offers/309/accept")
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert client.get("/offers/310").json()["status"] == "declined"
    assert client.get("/moving-requests/1042").json()["status"] == "assigned"
    assert client.get("/offers/306").json()["status"] == "declined"  # other requests are untouched
    assert client.get("/moving-requests/1047").json()["status"] == "open"


def test_accept_second_offer_is_a_conflict_like_planned(client):
    assert client.post("/offers/309/accept").status_code == 200
    response = client.post("/offers/310/accept")
    assert_matches_plan(response, 7, "Request already has an accepted offer")
    assert client.get("/offers/309").json()["status"] == "accepted"  # nothing changed


def test_accept_withdrawn_offer_returns_404_like_planned(client):
    created = client.post("/offers", json={"movingRequestId": 1047, "price": 800}, headers={"X-Company-Id": "7"})
    assert client.delete(created.headers["Location"]).status_code == 204
    response = client.post(created.headers["Location"] + "/accept")
    assert_matches_plan(response, 7, "Accepted offer does not exist any more")


def test_accepted_request_no_longer_accepts_changes(client):
    assert client.post("/offers/309/accept").status_code == 200
    assert client.delete("/offers/309").status_code == 409  # accepted offers are binding (rule 9)
    assert client.delete("/moving-requests/1042").status_code == 409  # rule 8
    late = client.post("/offers", json={"movingRequestId": 1042, "price": 1300}, headers={"X-Company-Id": "7"})
    assert late.status_code == 409  # rule 6


# ----- completed is derived from the date (rule 10) ------------------------------------------------------
def test_assigned_request_is_completed_after_its_moving_date(data_file):
    # Request 1038 is assigned and moves on 7 November 2026.
    with TestClient(create_app(data_file, today=lambda: date(2026, 11, 7))) as on_the_day:
        assert on_the_day.get("/moving-requests/1038").json()["status"] == "assigned"
    with TestClient(create_app(data_file, today=lambda: date(2026, 11, 8))) as day_after:
        assert day_after.get("/moving-requests/1038").json()["status"] == "completed"
        assert day_after.delete("/moving-requests/1038").status_code == 409  # still not deletable


# ----- persistence and the interface ----------------------------------------------------------------------
def test_created_request_survives_a_restart(data_file):
    with TestClient(create_app(data_file, today=lambda: TODAY)) as first:
        created = first.post("/moving-requests", json=CREATE_REQUEST, headers=customer(1))
    with TestClient(create_app(data_file, today=lambda: TODAY)) as restarted:
        assert restarted.get(created.headers["Location"]).json() == created.json()


def test_interface_is_served_under_app(client):
    page = client.get("/app/")
    assert page.status_code == 200 and "MoveMatch" in page.text
    assert client.get("/app/app.js").status_code == 200
