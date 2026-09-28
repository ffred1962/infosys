"""
Разбор JSON-массива из текстового ответа LLM, которую попросили вернуть *только*
JSON (без markdown и пояснений), но которая иногда всё равно оборачивает ответ в
код-fence или добавляет прозу до/после массива. Общее для core/firm_search.py и
core/firm_price_download.py — обе делают одинаковый ненадёжный "структурированный"
запрос к Claude и разбирают его одинаково.
"""

import json


class AiJsonError(Exception):
    """Ответ модели не удалось разобрать как JSON-массив."""


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()
    return stripped


def _extract_balanced(text: str, open_ch: str, close_ch: str, error_message: str) -> str:
    depth = 0
    start = None
    in_string = False
    escape = False

    for i, ch in enumerate(text):
        if start is None:
            if ch == open_ch:
                start = i
                depth = 1
            continue

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise AiJsonError(error_message)


def extract_balanced_json_array(text: str) -> str:
    """Находит первый сбалансированный JSON-массив в тексте.

    Модель иногда добавляет вступительную/завершающую фразу вокруг JSON, даже
    когда попросили вывести только массив — поиск первого "[" и последнего "]"
    ломается, если в этой фразе случайно встретится квадратная скобка, поэтому
    здесь отслеживается глубина вложенности (с учётом строк) до первого
    закрытия внешнего массива.
    """

    return _extract_balanced(text, "[", "]", "Не удалось найти JSON-массив в ответе модели.")


def extract_balanced_json_object(text: str) -> str:
    """То же, что extract_balanced_json_array, но для JSON-объекта {...}."""

    return _extract_balanced(text, "{", "}", "Не удалось найти JSON-объект в ответе модели.")


def parse_json_array(text: str) -> list:
    """Полный разбор: снять код-fence, найти сбалансированный массив, json.loads."""
    array_text = extract_balanced_json_array(strip_code_fence(text))
    try:
        data = json.loads(array_text)
    except json.JSONDecodeError as exc:
        raise AiJsonError("Модель вернула некорректный JSON.") from exc
    if not isinstance(data, list):
        raise AiJsonError("Модель вернула не список.")
    return data


def parse_json_object(text: str) -> dict:
    """Полный разбор для JSON-объекта: снять код-fence, найти сбалансированный
    объект, json.loads."""
    object_text = extract_balanced_json_object(strip_code_fence(text))
    try:
        data = json.loads(object_text)
    except json.JSONDecodeError as exc:
        raise AiJsonError("Модель вернула некорректный JSON.") from exc
    if not isinstance(data, dict):
        raise AiJsonError("Модель вернула не объект.")
    return data
