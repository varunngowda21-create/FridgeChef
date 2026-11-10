import logging
import uuid
from typing import Any

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("fridgechef.errors")


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.headers = headers


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found.", details: Any | None = None):
        super().__init__(code="RESOURCE_NOT_FOUND", message=message, status_code=status.HTTP_404_NOT_FOUND, details=details)


class IngredientNotFoundError(AppError):
    def __init__(self, message: str = "Ingredient not found.", details: Any | None = None):
        super().__init__(code="INGREDIENT_NOT_FOUND", message=message, status_code=status.HTTP_404_NOT_FOUND, details=details)


class RecipeNotFoundError(AppError):
    def __init__(self, message: str = "Recipe not found.", details: Any | None = None):
        super().__init__(code="RECIPE_NOT_FOUND", message=message, status_code=status.HTTP_404_NOT_FOUND, details=details)


class MealPlanNotFoundError(AppError):
    def __init__(self, message: str = "Meal plan not found.", details: Any | None = None):
        super().__init__(code="MEAL_PLAN_NOT_FOUND", message=message, status_code=status.HTTP_404_NOT_FOUND, details=details)


class ShoppingListNotFoundError(AppError):
    def __init__(self, message: str = "Shopping list not found.", details: Any | None = None):
        super().__init__(code="SHOPPING_LIST_NOT_FOUND", message=message, status_code=status.HTTP_404_NOT_FOUND, details=details)


class ItemNotFoundError(AppError):
    def __init__(self, message: str = "Item not found.", details: Any | None = None):
        super().__init__(code="ITEM_NOT_FOUND", message=message, status_code=status.HTTP_404_NOT_FOUND, details=details)


def format_error_response(
    code: str,
    message: str,
    status_code: int,
    request_id: str,
    details: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.warning(
        f"AppError: {exc.code} - {exc.message}",
        extra={
            "request_id": request_id,
            "status_code": exc.status_code,
            "error_code": exc.code,
            "endpoint": request.url.path,
        },
    )
    return format_error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        request_id=request_id,
        details=exc.details,
        headers=exc.headers,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    errors = jsonable_encoder(exc.errors())
    logger.warning(
        f"Validation error: {errors}",
        extra={
            "request_id": request_id,
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "error_code": "VALIDATION_ERROR",
            "endpoint": request.url.path,
        },
    )
    return format_error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        request_id=request_id,
        details=errors,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    code_map = {
        404: "NOT_FOUND",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        405: "METHOD_NOT_ALLOWED",
        413: "PAYLOAD_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return format_error_response(
        code=code,
        message=str(exc.detail),
        status_code=exc.status_code,
        request_id=request_id,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "request_id": request_id,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "error_code": "INTERNAL_SERVER_ERROR",
            "endpoint": request.url.path,
        },
    )
    return format_error_response(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request_id=request_id,
    )
