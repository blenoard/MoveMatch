"""HTTP boundary: parse input, call the service, map outcomes to HTTP."""
from datetime import date
from pathlib import Path
from typing import Annotated, Callable

from fastapi import Depends, FastAPI, Header, Path as PathParameter, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .models import Error, FurnitureType, MovingRequest, MovingRequestInput, Offer, OfferInput
from .service import MoveMatchError, MoveMatchService
from .storage import JsonStore

# The browser interface (plain HTML, CSS and JavaScript) is served by the same application under /app.
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

RecordId = Annotated[int, PathParameter(ge=1)]
# Temporary stand-ins for the login (security lesson): the acting user is named by a header.
CompanyId = Annotated[int, Header(alias="X-Company-Id", ge=1,
                                  description="Temporary stand-in for the login: the ID of the acting company.")]
CustomerId = Annotated[int, Header(alias="X-Customer-Id", ge=1,
                                   description="Temporary stand-in for the login: the ID of the acting customer.")]
ERRORS = {
    404: {"model": Error, "description": "Resource not found"},
    409: {"model": Error, "description": "Conflict with the current state"},
    422: {"model": Error, "description": "Invalid input or a violated business rule"},
}
LOCATION = {"Location": {"description": "Relative URL of the created resource", "schema": {"type": "string"}}}


def create_app(data_file: Path, today: Callable[[], date] = date.today) -> FastAPI:
    app = FastAPI(title="MoveMatch API", version="0.2.0",
                  description="Milestone 3: all operations of the contract and a browser interface under /app. "
                              "No login yet: see the X-Company-Id and X-Customer-Id headers.")
    # Setup: the store is created once; the service receives it (dependency injection by constructor).
    app.state.service = MoveMatchService(JsonStore(data_file), today)

    def get_service(request: Request) -> MoveMatchService:
        return request.app.state.service

    Service = Annotated[MoveMatchService, Depends(get_service)]

    # ----- error mapping: every error body is {"code": ..., "message": ...} --------------------
    @app.exception_handler(MoveMatchError)
    async def business_error(request: Request, error: MoveMatchError):
        status = {"invalid_input": 422, "not_found": 404, "conflict": 409}[error.code]
        return JSONResponse(status_code=status, content={"code": error.code, "message": error.message})

    @app.exception_handler(RequestValidationError)
    async def input_error(request: Request, error: RequestValidationError):
        messages = [".".join(str(part) for part in e["loc"]) + ": " + e["msg"] for e in error.errors()]
        return JSONResponse(status_code=422, content={"code": "invalid_input", "message": "; ".join(messages)})

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(error.status_code, "http_error")
        return JSONResponse(status_code=error.status_code, headers=error.headers,
                            content={"code": code, "message": str(error.detail)})

    # Convenience: the start page leads to the interactive documentation (not part of the contract).
    @app.get("/", include_in_schema=False)
    def start_page():
        return RedirectResponse("/docs")

    # ----- furniture catalogue -------------------------------------------------------------------
    @app.get("/furniture-types", response_model=list[FurnitureType], tags=["Furniture types"],
             operation_id="listFurnitureTypes")
    def list_furniture_types(service: Service):
        return service.list_furniture_types()

    # ----- moving requests -------------------------------------------------------------------------
    @app.get("/moving-requests", response_model=list[MovingRequest], tags=["Moving requests"],
             operation_id="listMovingRequests")
    def list_moving_requests(service: Service):
        return service.list_moving_requests()

    @app.post("/moving-requests", response_model=MovingRequest, status_code=201, tags=["Moving requests"],
              operation_id="createMovingRequest", responses={422: ERRORS[422], 201: {"headers": LOCATION}})
    def create_moving_request(body: MovingRequestInput, response: Response, service: Service,
                              customer_id: CustomerId):
        created = service.create_moving_request(body.model_dump(mode="json"), customer_id)
        response.headers["Location"] = f"/moving-requests/{created['id']}"
        return created

    @app.get("/moving-requests/{moving_request_id}", response_model=MovingRequest, tags=["Moving requests"],
             operation_id="readMovingRequest", responses={k: ERRORS[k] for k in (404, 422)})
    def read_moving_request(moving_request_id: RecordId, service: Service):
        return service.get_moving_request(moving_request_id)

    @app.put("/moving-requests/{moving_request_id}", response_model=MovingRequest, tags=["Moving requests"],
             operation_id="replaceMovingRequest", responses=ERRORS)
    def replace_moving_request(moving_request_id: RecordId, body: MovingRequestInput, service: Service):
        return service.replace_moving_request(moving_request_id, body.model_dump(mode="json"))

    @app.delete("/moving-requests/{moving_request_id}", status_code=204, response_class=Response,
                tags=["Moving requests"], operation_id="deleteMovingRequest", responses=ERRORS)
    def delete_moving_request(moving_request_id: RecordId, service: Service):
        service.delete_moving_request(moving_request_id)
        return Response(status_code=204)

    # ----- offers ----------------------------------------------------------------------------------
    @app.get("/offers", response_model=list[Offer], tags=["Offers"], operation_id="listOffers",
             responses={422: ERRORS[422]})
    def list_offers(service: Service, moving_request_id: Annotated[int, Query(alias="movingRequestId", ge=1)]):
        return service.list_offers(moving_request_id)

    @app.post("/offers", response_model=Offer, status_code=201, tags=["Offers"], operation_id="createOffer",
              responses={404: ERRORS[404], 409: ERRORS[409], 422: ERRORS[422], 201: {"headers": LOCATION}})
    def create_offer(body: OfferInput, response: Response, service: Service, company_id: CompanyId):
        offer = service.create_offer(body.model_dump(), company_id)
        response.headers["Location"] = f"/offers/{offer['id']}"
        return offer

    @app.get("/offers/{offer_id}", response_model=Offer, tags=["Offers"], operation_id="readOffer",
             responses={k: ERRORS[k] for k in (404, 422)})
    def read_offer(offer_id: RecordId, service: Service):
        return service.get_offer(offer_id)

    @app.delete("/offers/{offer_id}", status_code=204, response_class=Response, tags=["Offers"],
                operation_id="withdrawOffer", responses=ERRORS)
    def withdraw_offer(offer_id: RecordId, service: Service):
        service.delete_offer(offer_id)
        return Response(status_code=204)

    @app.post("/offers/{offer_id}/accept", response_model=Offer, tags=["Offers"], operation_id="acceptOffer",
              responses=ERRORS)
    def accept_offer(offer_id: RecordId, service: Service):
        return service.accept_offer(offer_id)

    # The interface is mounted last, so that it can never hide an API route.
    app.mount("/app", StaticFiles(directory=FRONTEND, html=True), name="frontend")
    return app
