"""API data shapes (what the API accepts and returns). Existence and rule checks belong in service.py."""
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

PositiveInt = Annotated[int, Field(strict=True, ge=1)]


class InputModel(BaseModel):
    """Base for everything a client sends: unknown fields are rejected."""
    model_config = ConfigDict(extra="forbid")


class Address(BaseModel):
    postalCode: str = Field(pattern=r"^[0-9]{4}$")
    city: str = Field(min_length=1)
    floor: int = Field(strict=True, ge=0)
    hasLift: bool = Field(strict=True)


class RequestItem(BaseModel):
    furnitureTypeId: PositiveInt
    quantity: int = Field(strict=True, ge=0)


class MovingRequest(BaseModel):
    id: PositiveInt
    reference: str  # "MM-" + id, derived by the service and not stored
    customerId: PositiveInt
    status: Literal["open", "offers_received", "assigned", "completed"]
    fromAddress: Address
    toAddress: Address
    distanceKm: PositiveInt
    movingDate: date
    items: list[RequestItem]
    volumeM3: float
    priceMin: PositiveInt
    priceMax: PositiveInt
    currency: Literal["CHF"]


class OfferInput(InputModel):
    movingRequestId: PositiveInt
    price: PositiveInt  # whole CHF
    message: str | None = Field(default=None, max_length=500)


class Offer(BaseModel):
    id: PositiveInt
    movingRequestId: PositiveInt
    companyId: PositiveInt
    price: PositiveInt
    currency: Literal["CHF"]
    message: str | None = None
    status: Literal["pending", "accepted", "declined"]


class Error(BaseModel):
    code: str
    message: str
