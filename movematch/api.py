"""HTTP boundary: parse input, call the service, map outcomes to HTTP."""
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Path as PathParameter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .models import Error, MovingRequest, Offer, OfferInput
from .service import MoveMatchError, MoveMatchService
from .storage import JsonStore

RecordId = Annotated[int, PathParameter(ge=1)]
# Temporary stand-in for the login (security lesson): the company is named by a header.
CompanyId = Annotated[int, Header(alias="X-Company-Id", ge=1,
                                  description="Temporary stand-in for the login: the ID of the acting company.")]
ERRORS = {
    404: {"model": Error, "description": "Resource not found"},
    409: {"model": Error, "description": "Conflict with the current state"},
    422: {"model": Error, "description": "Invalid input or a violated business rule"},
}
LOCATION = {"Location": {"description": "Relative URL of the created resource", "schema": {"type": "string"}}}


def create_app(data_file: Path) -> FastAPI:
    app = FastAPI(title="MoveMatch API", version="0.1.0",
                  description="Milestone 2: first implemented part (moving requests read-only, offers). "
                              "No login yet: see the X-Company-Id header.")
    # Setup: the store is created once; the service receives it (dependency injection by constructor).
    app.state.service = MoveMatchService(JsonStore(data_file))

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

    # ----- moving requests (read only) -----------------------------------------------------------
    @app.get("/moving-requests", response_model=list[MovingRequest], tags=["Moving requests"],
             operation_id="listMovingRequests")
    def list_moving_requests(service: Service):
        return service.list_moving_requests()

    @app.get("/moving-requests/{moving_request_id}", response_model=MovingRequest, tags=["Moving requests"],
             operation_id="readMovingRequest", responses={k: ERRORS[k] for k in (404, 422)})
    def read_moving_request(moving_request_id: RecordId, service: Service):
        return service.get_moving_request(moving_request_id)

    # ----- offers ----------------------------------------------------------------------------------
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

    return app
