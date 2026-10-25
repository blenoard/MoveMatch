"""Application logic: the business rules. This module has no HTTP or FastAPI dependencies.

Rule numbers refer to "Business rules and possible operations" in the README.
"""
from .storage import JsonStore

# Rule 6: offers are only possible while the request is in one of these states.
ACCEPTS_OFFERS = ("open", "offers_received")


class MoveMatchError(Exception):
    """A business or lookup error. `code` is mapped to an HTTP status in api.py."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code  # "invalid_input" (422), "not_found" (404) or "conflict" (409)
        self.message = message


class MoveMatchService:
    def __init__(self, store: JsonStore):
        self.store = store

    # ----- helpers -----------------------------------------------------------
    @staticmethod
    def find(rows: list[dict], record_id: int) -> dict:
        for row in rows:
            if row["id"] == record_id:
                return row
        raise MoveMatchError("not_found", "Requested resource not found.")

    @staticmethod
    def with_reference(request: dict) -> dict:
        # The reference "MM-1042" is only a display format of the ID; it is not stored (see README).
        return {**request, "reference": f"MM-{request['id']}"}

    # ----- moving requests (read only in this milestone) -----------------------
    def list_moving_requests(self) -> list[dict]:
        with self.store.lock:
            return [self.with_reference(r) for r in self.store.load()["moving_requests"]]

    def get_moving_request(self, request_id: int) -> dict:
        with self.store.lock:
            return self.with_reference(self.find(self.store.load()["moving_requests"], request_id))

    # ----- offers --------------------------------------------------------------
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
