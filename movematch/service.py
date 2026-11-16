"""Application logic: the business rules. This module has no HTTP or FastAPI dependencies.

Rule numbers refer to "Business rules and possible operations" in the README.
"""
from datetime import date
from typing import Callable

from .storage import JsonStore

# Rule 6: offers are only possible while the request is in one of these states.
ACCEPTS_OFFERS = ("open", "offers_received")

# Rule 3: rates of the draft price formula (whole CHF) and the margin of the price range.
BASE_PRICE = 350
PRICE_PER_KM = 3
PRICE_PER_M3 = 60
PRICE_PER_FLOOR_WITHOUT_LIFT = 50
MARGIN_PERCENT = 15
ROUND_TO = 50


class MoveMatchError(Exception):
    """A business or lookup error. `code` is mapped to an HTTP status in api.py."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code  # "invalid_input" (422), "not_found" (404) or "conflict" (409)
        self.message = message


class MoveMatchService:
    def __init__(self, store: JsonStore, today: Callable[[], date] = date.today):
        self.store = store
        self.today = today  # injected so that tests can use a fixed date

    # ----- helpers -----------------------------------------------------------
    @staticmethod
    def find(rows: list[dict], record_id: int) -> dict:
        for row in rows:
            if row["id"] == record_id:
                return row
        raise MoveMatchError("not_found", "Requested resource not found.")

    def present(self, request: dict) -> dict:
        """The request as the API returns it: stored fields plus the derived ones."""
        # The reference "MM-1042" is only a display format of the ID; it is not stored (see README).
        shown = {**request, "reference": f"MM-{request['id']}"}
        # Rule 10: an assigned request counts as completed once its moving date has passed.
        # The status is derived when the request is read; nobody sets it manually.
        if request["status"] == "assigned" and date.fromisoformat(request["movingDate"]) < self.today():
            shown["status"] = "completed"
        return shown

    @staticmethod
    def price_range(estimate: int) -> tuple[int, int]:
        """Rule 3: estimate +/- 15 %, rounded inwards to CHF 50 (whole-number arithmetic)."""
        step = 100 * ROUND_TO
        lowest = -(-estimate * (100 - MARGIN_PERCENT) // step) * ROUND_TO  # rounded up
        highest = estimate * (100 + MARGIN_PERCENT) // step * ROUND_TO  # rounded down
        return lowest, highest

    def calculated_fields(self, data: dict, fields: dict) -> dict:
        """Checks rules 1 and 2 and returns the fields the backend calculates (rule 3)."""
        # Rule 1: the moving date must not lie in the past (today is allowed).
        if date.fromisoformat(fields["movingDate"]) < self.today():
            raise MoveMatchError("invalid_input", "movingDate: must not lie in the past.")
        volumes = {furniture["id"]: furniture["volumeM3"] for furniture in data["furniture_types"]}
        type_ids = [item["furnitureTypeId"] for item in fields["items"]]
        if any(type_id not in volumes for type_id in type_ids):
            raise MoveMatchError("invalid_input", "items: unknown furniture type.")
        if len(type_ids) != len(set(type_ids)):
            raise MoveMatchError("invalid_input", "items: each furniture type may appear only once.")
        # Rule 2: at least one item with a quantity of 1 or more.
        if not any(item["quantity"] >= 1 for item in fields["items"]):
            raise MoveMatchError(
                "invalid_input", "items: at least one item with a quantity of 1 or more is required.")
        volume = round(sum(volumes[item["furnitureTypeId"]] * item["quantity"] for item in fields["items"]), 2)
        floors = sum(address["floor"] for address in (fields["fromAddress"], fields["toAddress"])
                     if not address["hasLift"])
        estimate = round(BASE_PRICE + PRICE_PER_KM * fields["distanceKm"] + PRICE_PER_M3 * volume
                         + PRICE_PER_FLOOR_WITHOUT_LIFT * floors)
        price_min, price_max = self.price_range(estimate)
        return {"volumeM3": volume, "priceMin": price_min, "priceMax": price_max, "currency": "CHF"}

    # ----- furniture catalogue -------------------------------------------------
    def list_furniture_types(self) -> list[dict]:
        with self.store.lock:
            return self.store.load()["furniture_types"]

    # ----- moving requests -----------------------------------------------------
    def list_moving_requests(self) -> list[dict]:
        with self.store.lock:
            return [self.present(r) for r in self.store.load()["moving_requests"]]

    def get_moving_request(self, request_id: int) -> dict:
        with self.store.lock:
            return self.present(self.find(self.store.load()["moving_requests"], request_id))

    def create_moving_request(self, fields: dict, customer_id: int) -> dict:
        """Workflow A, steps 2 to 4. Checks: customer exists, rules 1 and 2; then calculates rule 3."""
        with self.store.lock:
            data = self.store.load()
            if not any(customer["id"] == customer_id for customer in data["customers"]):
                raise MoveMatchError("invalid_input", "X-Customer-Id: unknown customer.")
            calculated = self.calculated_fields(data, fields)
            # Older data files have no counter yet: continue after the highest existing ID.
            next_id = data.get("next_request_id") or max((r["id"] for r in data["moving_requests"]), default=0) + 1
            request = {"id": next_id, "customerId": customer_id, "status": "open", **fields, **calculated}
            data["next_request_id"] = next_id + 1  # IDs of deleted requests are never reused
            data["moving_requests"].append(request)
            self.store.save(data)
            return self.present(request)

    def replace_moving_request(self, request_id: int, fields: dict) -> dict:
        """Rule 8: a request can only be edited while it is `open`. The price range is recalculated."""
        with self.store.lock:
            data = self.store.load()
            request = self.find(data["moving_requests"], request_id)  # 404
            if request["status"] != "open":
                raise MoveMatchError("conflict", "A request can only be edited while it is open.")
            request.update({**fields, **self.calculated_fields(data, fields)})
            self.store.save(data)
            return self.present(request)

    def delete_moving_request(self, request_id: int) -> None:
        """Rule 8: really deletes the request together with its offers; not possible once assigned."""
        with self.store.lock:
            data = self.store.load()
            request = self.find(data["moving_requests"], request_id)  # 404
            if request["status"] not in ACCEPTS_OFFERS:
                raise MoveMatchError("conflict", "An assigned request cannot be deleted.")
            data["moving_requests"].remove(request)
            data["offers"] = [o for o in data["offers"] if o["movingRequestId"] != request_id]
            self.store.save(data)

    # ----- offers --------------------------------------------------------------
    def list_offers(self, request_id: int) -> list[dict]:
        """The offers of one request, so that the customer can compare them."""
        with self.store.lock:
            return [o for o in self.store.load()["offers"] if o["movingRequestId"] == request_id]

    def get_offer(self, offer_id: int) -> dict:
        with self.store.lock:
            return self.find(self.store.load()["offers"], offer_id)

    def create_offer(self, fields: dict, company_id: int) -> dict:
        """Workflow B, step 4. Checks in this order: request exists, company exists, rules 6, 5 and 4."""
        with self.store.lock:
            data = self.store.load()
            request = self.find(data["moving_requests"], fields["movingRequestId"])  # 404
            if not any(company["id"] == company_id for company in data["companies"]):
                raise MoveMatchError("invalid_input", "X-Company-Id: unknown company.")
            # Rule 6: the request must still accept offers.
            if request["status"] not in ACCEPTS_OFFERS:
                raise MoveMatchError("conflict", "Offers are only possible while the request is open or has offers.")
            # Rule 5: one offer per company and request.
            if any(o["movingRequestId"] == request["id"] and o["companyId"] == company_id for o in data["offers"]):
                raise MoveMatchError("conflict", "This company already has an offer on this request.")
            # Rule 4: the price must lie within the range of the request (both limits included).
            if not request["priceMin"] <= fields["price"] <= request["priceMax"]:
                raise MoveMatchError(
                    "invalid_input", f"price: must be between {request['priceMin']} and {request['priceMax']} CHF.")
            offer = {
                "id": data["next_offer_id"],
                "movingRequestId": request["id"],
                "companyId": company_id,
                "price": fields["price"],
                "currency": "CHF",
                "message": fields.get("message"),
                "status": "pending",
            }
            data["next_offer_id"] += 1  # IDs of deleted offers are never reused
            data["offers"].append(offer)
            if request["status"] == "open":  # Workflow B, step 5
                request["status"] = "offers_received"
            self.store.save(data)
            return offer

    def accept_offer(self, offer_id: int) -> dict:
        """Workflow A, step 5 (rule 7). One step: offer accepted, the others declined, request assigned."""
        with self.store.lock:
            data = self.store.load()
            offer = self.find(data["offers"], offer_id)  # 404, for example withdrawn in the meantime
            request = self.find(data["moving_requests"], offer["movingRequestId"])
            if request["status"] not in ACCEPTS_OFFERS:
                raise MoveMatchError("conflict", "This request already has an accepted offer.")
            if offer["status"] != "pending":
                raise MoveMatchError("conflict", "Only a pending offer can be accepted.")
            for other in data["offers"]:
                if other["movingRequestId"] == request["id"]:
                    other["status"] = "declined"
            offer["status"] = "accepted"
            request["status"] = "assigned"
            self.store.save(data)
            return offer

    def delete_offer(self, offer_id: int) -> None:
        """Workflow B, step 6 (withdraw an offer). Rule 9: only a pending offer can be withdrawn."""
        with self.store.lock:
            data = self.store.load()
            offer = self.find(data["offers"], offer_id)  # 404
            if offer["status"] == "accepted":
                raise MoveMatchError("conflict", "An accepted offer is binding and cannot be withdrawn.")
            if offer["status"] != "pending":
                raise MoveMatchError("conflict", "Only a pending offer can be withdrawn.")
            data["offers"].remove(offer)
            request = self.find(data["moving_requests"], offer["movingRequestId"])
            still_pending = any(o["movingRequestId"] == request["id"] and o["status"] == "pending"
                                for o in data["offers"])
            # Rule 9: if it was the last pending offer, the request returns to `open`.
            if request["status"] == "offers_received" and not still_pending:
                request["status"] = "open"
            self.store.save(data)
