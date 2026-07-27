"""
Поиск реальных фирм через веб-поиск на стороне Claude API (Anthropic Messages API,
инструмент web_search). Работает как обычный синхронный вызов из бэкенда — не требует
Claude Desktop/Code ни на сервере, ни у клиента. Используется POST /api/firm/search.
"""

import logging
import os
from typing import Optional

import anthropic

from core.ai_json import AiJsonError, parse_json_array


logger = logging.getLogger("infosys.firm_search")

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
MAX_RESULTS = 10

_SYSTEM_PROMPT = (
    "Ты помогаешь найти реальные компании через веб-поиск. Используй инструмент "
    "веб-поиска, чтобы найти реально существующие компании указанного типа в "
    f"указанном городе (Украина), не более {MAX_RESULTS} штук. "
    "В ответе выведи ТОЛЬКО JSON-массив объектов без markdown-разметки и пояснений, "
    "каждый объект строго с полями: name (строка, обязательно), phone (строка или "
    "null), website (строка или null), address (строка или null), source (строка с "
    "названием сайта/каталога, где найдена информация, или null), notes (короткая "
    "строка с дополнительной инфой или null). Указывай только реально найденные, "
    "проверяемые компании — не выдумывай данные. Если ничего не нашлось, выведи "
    "пустой массив []."
)


class FirmSearchError(Exception):
    """Ошибка поиска фирм (нет API-ключа, сбой Claude API, некорректный ответ)."""


def search_firms(city_name: str, firm_type_name: str) -> list[dict]:
    """Ищет реальные фирмы заданного типа в заданном городе через Claude API."""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise FirmSearchError(
            "Не задан ANTHROPIC_API_KEY — поиск фирм недоступен. Установите "
            "переменную окружения ANTHROPIC_API_KEY и перезапустите сервер."
        )

    # Реальный веб-поиск с несколькими последовательными вызовами инструмента
    # (max_uses=5) может занимать несколько минут — 90s оказалось мало на
    # практике. max_retries=0: повтор на таймауте только удвоил бы ожидание,
    # не решая саму медлительность запроса.
    client = anthropic.Anthropic(api_key=api_key, timeout=240.0, max_retries=0)
    user_prompt = f'Найди реальные компании типа "{firm_type_name}" в городе {city_name} (Украина).'

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            tools=[{"type": "web_search_20260318", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as exc:
        logger.exception("Ошибка Claude API при поиске фирм")
        raise FirmSearchError(f"Ошибка обращения к Claude API: {exc}") from exc

    text = "".join(block.text for block in response.content if block.type == "text")
    return _parse_results(text)


def _parse_results(text: str) -> list[dict]:
    try:
        data = parse_json_array(text)
    except AiJsonError as exc:
        raise FirmSearchError(str(exc)) from exc

    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = _clean_str(item.get("name"))
        if not name:
            continue
        results.append(
            {
                "name": name,
                "phone": _clean_str(item.get("phone")),
                "website": _clean_str(item.get("website")),
                "address": _clean_str(item.get("address")),
                "source": _clean_str(item.get("source")),
                "notes": _clean_str(item.get("notes")),
            }
        )
    return results[:MAX_RESULTS]


def _clean_str(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
