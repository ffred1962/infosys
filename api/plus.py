"""
API для выполнения математических операций.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict


logger = logging.getLogger("infosys.api.plus")


class PlusRequest(BaseModel):
    """
    Модель запроса для операции сложения.
    
    Attributes:
        a: Первое число (float)
        b: Второе число (float)
    """
    a: float = Field(..., description="Первое число для сложения")
    b: float = Field(..., description="Второе число для сложения")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "a": 5.5,
                "b": 3.2,
            }
        }
    )


class PlusResponse(BaseModel):
    """
    Модель ответа для операции сложения.
    
    Attributes:
        result: Результат сложения двух чисел
    """
    result: float = Field(..., description="Результат сложения")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"result": 8.7}
        }
    )


router = APIRouter(prefix="/api", tags=["Calculator"])


@router.post(
    "/plus",
    response_model=PlusResponse,
    status_code=200,
    summary="Сложить два числа",
    description="Принимает два числа в теле запроса и возвращает их сумму.",
    response_description="Сумма переданных чисел.",
    responses={
        422: {"description": "Ошибка валидации входных данных."},
    },
)
def plus(request: PlusRequest) -> PlusResponse:
    """
    Endpoint для сложения двух чисел.
    
    **Параметры:**
    - `a` (float): Первое число
    - `b` (float): Второе число
    
    **Возвращает:**
    - `result` (float): Сумма a + b
    
    **Примеры:**
    - a=5, b=3 → result=8
    - a=2.5, b=1.5 → result=4.0
    """
    logger.info("POST /api/plus input: a=%s, b=%s", request.a, request.b)
    try:
        result = request.a + request.b
        logger.info("POST /api/plus result: %s", result)
        return PlusResponse(result=result)
    except Exception as error:
        logger.exception("POST /api/plus failed")
        raise
