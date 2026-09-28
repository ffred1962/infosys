"""
Скачивание актуального прайса фирмы с её сайта — собственный асинхронный
конвейер (httpx + BeautifulSoup сами скачивают и разбирают HTML), Claude
используется только для извлечения структурированных данных из уже готового
текста, БЕЗ инструментов web_search/web_fetch. Используется
POST /api/firm/{firm_id}/download_price.

Почему не agentic-вызов с tools (как было раньше — модель сама решала, что и
когда скачивать через свой внутренний code_execution-оркестратор): единственный
такой вызов мог тянуться до 15 минут, был непрозрачен (не видно, что реально
скачивается и почему) и не давал контроля над количеством/параллельностью
запросов к сайту фирмы — при живом тестировании (см. CLAUDE.md) на сайте с
большим каталогом такой вызов не укладывался по времени, а неудачные попытки
уже съели ощутимую часть платного лимита API за один день. Здесь вместо этого:

1. Сами скачиваем (asyncio + httpx, с ограничением параллельности) главную
   страницу сайта и несколько похожих на "двери" разделов, которые находим по
   ссылкам с неё.
2. Просим Claude (обычный вызов, без tools) извлечь из уже скачанного текста
   двери с ценами; для товаров, упомянутых, но без цены на странице — вернуть
   URL их собственной карточки (мы сохраняем ссылки прямо в тексте, который
   отдаём модели, так что ей есть что скопировать).
3. Скачиваем эти карточки (снова параллельно, один дополнительный раунд) и
   повторяем извлечение.

Итоговое время и число сетевых запросов предсказуемы и ограничены константами
ниже, т.к. Claude больше не ждёт сама сетевых операций — их делаем мы.

Область интереса — ТОЛЬКО двери (входные, межкомнатные, дверные полотна/блоки/
комплекты и фурнитура для них); окна и балконы намеренно исключаются из
результата, даже если сайт публикует их вперемешку с дверями в одном разделе.
"""

import asyncio
import ipaddress
import logging
import os
import re
import socket
from typing import Optional
from urllib.parse import urljoin, urlsplit

import anthropic
import httpx
from bs4 import BeautifulSoup

from core.ai_json import AiJsonError, parse_json_array


logger = logging.getLogger("infosys.firm_price_download")

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
MAX_RESULTS = 80

MAX_CANDIDATE_PAGES = 6   # похожие на "двери" разделы, найденные по ссылкам с главной
MAX_PENDING_PAGES = 40    # карточки отдельных товаров без цены на странице списка
MAX_PAGE_CHARS = 15000    # обрезка текста одной страницы перед отправкой модели
FETCH_CONCURRENCY = 8     # не долбим маленький сайт фирмы десятками запросов разом
MAX_REDIRECTS = 5         # редиректы разруливаем сами (не httpx), см. _fetch_page
HTTP_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
# Многие небольшие сайты (WordPress/OpenCart с примитивными анти-бот плагинами)
# блокируют запросы без правдоподобного User-Agent браузера — это не обход
# защиты, а обычный десктопный UA, чтобы наш единичный редкий запрос не
# отбрасывался тривиальным фильтром по пустому/подозрительному заголовку.
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_DOOR_LINK_RE = re.compile(r"двер|dver|door", re.IGNORECASE)

_ITEM_SCHEMA_HINT = (
    "Для каждого объекта строго такие поля:\n"
    "- name (строка, обязательно) — полное название товара, как на странице;\n"
    "- article (строка или null) — код/артикул товара, если есть. Часто "
    "стоит в самом начале названия, например \"ПБУ-01 Дверь входная "
    "металлическая ...\" — тогда вынеси \"ПБУ-01\" в article, а в name "
    "оставь остальную часть без этого кода. Иначе article: null, name как есть;\n"
    "- unit (строка или null) — единица измерения, если указана (\"шт\", \"м2\", "
    "\"комплект\" и т.п.), иначе null;\n"
    "- price (число или строка с числом, или null) — цена, если видна прямо на "
    "странице (валюту/пробелы можно не убирать, это очистится отдельно); если "
    "цены на этой странице нет — null;\n"
    "- url (строка или null) — заполняй ТОЛЬКО когда price: null, и рядом с "
    "названием в тексте есть ссылка на отдельную страницу этого товара "
    "(ссылки в тексте показаны как \"текст [URL]\") — скопируй URL как есть, "
    "мы сами зайдём по нему за ценой. Если подходящей ссылки нет — тоже null."
)

_EXTRACT_SYSTEM_PROMPT = (
    "Тебе дан уже скачанный текст одной или нескольких страниц сайта компании "
    "(с пометкой, какая страница где начинается). Найди среди этого текста "
    "ТОЛЬКО двери: входные двери, межкомнатные двери, дверные полотна, "
    "дверные блоки/комплекты, дверные коробки, фурнитура для дверей.\n\n"
    "НЕ включай в ответ окна (окна, оконные конструкции, монтаж окон) и "
    "балконы (балконы, балконное остекление, лоджии) — даже если они "
    "перечислены на той же странице вместе с дверями.\n\n"
    "Компания может специализироваться в основном на окнах/балконах, но "
    "дополнительно продавать двери отдельным разделом — это не повод считать, "
    "что дверей нет: внимательно проверь весь предоставленный текст.\n\n"
    f"{_ITEM_SCHEMA_HINT}\n\n"
    f"Не более {MAX_RESULTS} объектов. Ответ — ТОЛЬКО JSON-массив таких "
    "объектов, без markdown-разметки и пояснений. Указывай только то, что "
    "реально есть в предоставленном тексте — не выдумывай товары, цены или "
    "URL. Если дверей в тексте вообще нет — верни []."
)


class FirmPriceDownloadError(Exception):
    """Ошибка скачивания прайса (нет API-ключа, сайт недоступен, сбой Claude API)."""


def _same_domain(url: str, root_netloc: str) -> bool:
    netloc = urlsplit(url).netloc.lower()
    root = root_netloc.lower()
    return netloc == root or netloc == f"www.{root}" or f"www.{netloc}" == root


_UNSAFE_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".localdomain")
# Часть IPv4 в "нестандартной" записи: десятичная, восьмеричная (0177) или hex (0x7f).
_NUMERIC_HOST_PART_RE = re.compile(r"^(?:0[xX][0-9a-fA-F]*|[0-9]+)$")


def _is_unsafe_ip(ip: "ipaddress.IPv4Address | ipaddress.IPv6Address") -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _is_unsafe_host(host: str) -> bool:
    """True, если хост нельзя считать публичным. DNS здесь не резолвим
    (функция вызывается из async-кода), поэтому проверяем только то, что видно
    по самой строке: литеральные IP (в т.ч. нестандартные записи IPv4 вроде
    127.1, 2130706433, 0x7f000001, 0177.0.0.1), localhost, безточечные
    имена и служебные суффиксы (.local/.internal/.lan/.localdomain)."""
    host = host.strip().lower().rstrip(".")
    if not host:
        return True
    try:
        return _is_unsafe_ip(ipaddress.ip_address(host))
    except ValueError:
        pass
    # Нестандартная числовая запись IPv4: все части — числа (dec/oct/0xhex).
    if all(_NUMERIC_HOST_PART_RE.match(part) for part in host.split(".")):
        try:
            canonical = socket.inet_aton(host)
        except OSError:
            return True  # похоже на IP, но не разбирается однозначно — не рискуем
        return _is_unsafe_ip(ipaddress.IPv4Address(canonical))
    if host == "localhost" or "." not in host:
        return True
    return host.endswith(_UNSAFE_HOST_SUFFIXES)


def _is_safe_url(url: str) -> bool:
    """Базовая защита от SSRF при переходе по редиректам чужой страницы:
    только http/https и не буквальный приватный/служебный/loopback IP-адрес
    (например 127.0.0.1 или 169.254.169.254 — типичный адрес cloud-metadata).
    Это не герметичная защита (DNS rebinding сюда не входит), но разумный
    минимум для демо-проекта, скачивающего прайс с сайта, который фирма сама
    указала в своей карточке — не попытка построить непробиваемый периметр."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.hostname
    if not host:
        return False
    return not _is_unsafe_host(host)


def _html_to_text_with_links(html: str, base_url: str) -> str:
    """HTML -> текст, но со ссылками, "впечатанными" прямо в текст как
    "текст ссылки [абсолютный URL]" — иначе обычный get_text() выкидывает href,
    и модели нечем будет указать нам, куда перейти за ценой конкретного товара.
    Ссылка без видимого текста (например обёрнутая вокруг картинки, картинка к
    этому моменту уже удалена) всё равно сохраняется как голый "[URL]" — иначе
    именно самые обычные для каталогов ссылки-картинки без текста молча теряли
    бы свой адрес, и второй раунд (докачка карточки товара) не срабатывал бы
    именно там, где нужен чаще всего."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "img"]):
        tag.decompose()
    for a in soup.find_all("a", href=True):
        absolute = urljoin(base_url, a["href"])
        text = a.get_text(strip=True)
        a.replace_with(f"{text} [{absolute}]" if text else f"[{absolute}]")
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:MAX_PAGE_CHARS]


def _extract_candidate_links(html: str, base_url: str, root_netloc: str) -> list[str]:
    """Ссылки с главной страницы, чей текст или адрес похож на раздел дверей."""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if not _DOOR_LINK_RE.search(text) and not _DOOR_LINK_RE.search(href):
            continue
        absolute = urljoin(base_url, href)
        if not _same_domain(absolute, root_netloc) or absolute in seen:
            continue
        seen.add(absolute)
        candidates.append(absolute)
        if len(candidates) >= MAX_CANDIDATE_PAGES:
            break
    return candidates


async def _fetch_page(
    client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore
) -> Optional[tuple[str, str]]:
    """Скачивает одну страницу, сама разруливая редиректы (httpx-клиент ниже
    создаётся с follow_redirects по умолчанию выключенным) — на каждом хопе
    заново проверяем схему/адрес через _is_safe_url, чтобы редирект чужой
    страницы на приватный/служебный адрес (SSRF) не выполнялся молча. Одна
    недоступная/небезопасная/нередиректящаяся-до-конца страница просто
    пропускается (возвращается None) — не должна ронять всю загрузку прайса."""
    current_url = url
    async with semaphore:
        for _ in range(MAX_REDIRECTS + 1):
            if not _is_safe_url(current_url):
                logger.warning("Отклонён небезопасный адрес: %s", current_url)
                return None
            try:
                response = await client.get(current_url)
            except httpx.HTTPError as exc:
                logger.warning("Не удалось скачать %s: %s", current_url, exc)
                return None
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    return None
                current_url = urljoin(current_url, location)
                continue
            break
        else:
            logger.warning("Слишком много редиректов для %s", url)
            return None

    if response.status_code >= 400:
        logger.warning("Страница %s ответила %s", current_url, response.status_code)
        return None
    content_type = response.headers.get("content-type", "")
    if content_type and "html" not in content_type:
        return None
    return current_url, response.text


async def _fetch_pages(
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore, urls: list[str]
) -> list[tuple[str, str]]:
    """Скачивает страницы параллельно (ограничено semaphore), возвращает только
    успешно скачанные (итоговый_url_после_редиректов, html) — упавшие молча
    пропускаются."""
    results = await asyncio.gather(*[_fetch_page(client, url, semaphore) for url in urls])
    return [r for r in results if r is not None]


def _build_pages_prompt(pages: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"=== Страница: {url} ===\n{text}" for url, text in pages)


async def _extract_items(
    client: anthropic.AsyncAnthropic, pages: list[tuple[str, str]]
) -> list[dict]:
    pages_text = _build_pages_prompt(pages)
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=8192,
            system=_EXTRACT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": pages_text}],
        )
    except anthropic.APIError as exc:
        logger.exception("Ошибка Claude API при разборе страниц прайса")
        raise FirmPriceDownloadError(f"Ошибка обращения к Claude API: {exc}") from exc

    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        data = parse_json_array(text)
    except AiJsonError as exc:
        raise FirmPriceDownloadError(str(exc)) from exc

    return [item for item in data if isinstance(item, dict)]


async def download_firm_price(firm_name: str, website: str) -> list[dict]:
    """Скачивает актуальный прайс на двери с сайта фирмы: сами скачиваем и
    разбираем HTML, Claude только извлекает структурированные данные из уже
    готового текста — без непредсказуемых по времени tool-вызовов."""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise FirmPriceDownloadError(
            "Не задан ANTHROPIC_API_KEY — скачивание прайса недоступно. Установите "
            "переменную окружения ANTHROPIC_API_KEY и перезапустите сервер."
        )

    root_netloc = urlsplit(website).netloc
    semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS
    ) as http_client, anthropic.AsyncAnthropic(
        api_key=api_key, timeout=180.0, max_retries=0
    ) as anthropic_client:
        homepage_fetched = await _fetch_pages(http_client, semaphore, [website])
        if not homepage_fetched:
            raise FirmPriceDownloadError(f"Не удалось открыть сайт {website}.")
        homepage_url, homepage_html = homepage_fetched[0]

        candidate_urls = [
            u
            for u in _extract_candidate_links(homepage_html, homepage_url, root_netloc)
            if u != homepage_url
        ]

        pages = [(homepage_url, _html_to_text_with_links(homepage_html, homepage_url))]
        if candidate_urls:
            fetched = await _fetch_pages(http_client, semaphore, candidate_urls)
            pages.extend((url, _html_to_text_with_links(html, url)) for url, html in fetched)

        round1 = await _extract_items(anthropic_client, pages)

        pending_urls: list[str] = []
        seen_pending: set[str] = set()
        for item in round1:
            url = item.get("url")
            if item.get("price") is None and isinstance(url, str) and url.strip():
                absolute = url.strip()
                if _same_domain(absolute, root_netloc) and absolute not in seen_pending:
                    seen_pending.add(absolute)
                    pending_urls.append(absolute)
            if len(pending_urls) >= MAX_PENDING_PAGES:
                break

        all_items = list(round1)
        if pending_urls:
            fetched_pending = await _fetch_pages(http_client, semaphore, pending_urls)
            if fetched_pending:
                pending_pages = [
                    (url, _html_to_text_with_links(html, url)) for url, html in fetched_pending
                ]
                # Второй раунд — лучшее из возможного, не критический: если он
                # упадёт (сбой Claude API и т.п.), не выбрасываем уже добытые
                # в первом раунде товары с реальными ценами, а просто
                # довольствуемся ими одними.
                try:
                    round2 = await _extract_items(anthropic_client, pending_pages)
                    all_items.extend(round2)
                except FirmPriceDownloadError as exc:
                    logger.warning(
                        "Второй раунд извлечения (карточки товаров) не удался, "
                        "используем то, что нашли на страницах списка: %s",
                        exc,
                    )

    return _parse_results(all_items)


def _parse_results(data: list[dict]) -> list[dict]:
    results = []
    for item in data:
        name = _clean_str(item.get("name"))
        if not name:
            continue
        price_raw = item.get("price")
        if price_raw is None:
            continue
        results.append(
            {
                "name": name,
                "article": _clean_str(item.get("article")),
                "unit": _clean_str(item.get("unit")),
                "price": price_raw,
            }
        )
    return results[:MAX_RESULTS]


def _clean_str(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
