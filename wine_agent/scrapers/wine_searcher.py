"""Wine-Searcher data collector.

Uses the official Wine-Searcher API when a key is configured, otherwise
falls back to a structured web-scraping path (requires respectful rate-limiting
and compliance with site ToS — use for personal/internal research only).
"""
import re
import time
import logging
from typing import Optional
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from wine_agent.config.settings import config
from wine_agent.models.wine import PricePoint

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "C$": "CAD", "CA$": "CAD"}


def _parse_price_string(raw: str) -> tuple[float, str]:
    """Return (amount, currency_code) from a raw price string."""
    raw = raw.strip()
    for sym, code in _CURRENCY_SYMBOLS.items():
        if raw.startswith(sym):
            try:
                amount = float(raw.replace(sym, "").replace(",", "").strip())
                return amount, code
            except ValueError:
                continue
    # Fallback: pull digits
    digits = re.findall(r"[\d,.]+", raw)
    if digits:
        return float(digits[0].replace(",", "")), "USD"
    return 0.0, "USD"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_page(url: str, params: dict | None = None) -> requests.Response:
    resp = requests.get(url, headers=_HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    time.sleep(1.5)   # polite crawl delay
    return resp


def fetch_via_api(wine_name: str, vintage: Optional[int] = None) -> list[PricePoint]:
    """Fetch prices using the Wine-Searcher commercial API."""
    if not config.wine_searcher_api_key:
        return []

    endpoint = "https://api.wine-searcher.com/api/wine"
    params = {
        "apikey": config.wine_searcher_api_key,
        "wine": wine_name,
        "vintage": vintage or "",
        "format": "json",
        "currency": "USD",
    }
    try:
        resp = _fetch_page(endpoint, params)
        data = resp.json()
        points = []
        for item in data.get("prices", [])[:20]:
            raw_price = float(item.get("price", 0))
            currency = item.get("currency", "USD")
            price_cad = raw_price * config.fx_rate(currency)
            points.append(PricePoint(
                source="wine_searcher_api",
                price_original=raw_price,
                currency=currency,
                price_cad=round(price_cad, 2),
                bottle_size_ml=int(item.get("bottle_size", 750)),
                as_of_date=str(item.get("date", "")),
            ))
        return points
    except Exception as e:
        logger.warning("Wine-Searcher API error: %s", e)
        return []


def fetch_market_prices(wine_name: str, vintage: Optional[int] = None) -> dict:
    """
    Return a summary dict with global_avg_cad, min_cad, max_cad and raw price points.
    Tries API first, then web scraping fallback.
    """
    points = fetch_via_api(wine_name, vintage)

    if not points:
        points = _scrape_wine_searcher(wine_name, vintage)

    if not points:
        logger.warning("No price data found for '%s' vintage %s", wine_name, vintage)
        return {"global_avg_cad": None, "min_cad": None, "max_cad": None, "price_points": []}

    prices_cad = [p.price_cad for p in points if p.price_cad > 0]
    return {
        "global_avg_cad": round(sum(prices_cad) / len(prices_cad), 2) if prices_cad else None,
        "min_cad": round(min(prices_cad), 2) if prices_cad else None,
        "max_cad": round(max(prices_cad), 2) if prices_cad else None,
        "price_points": points,
        "sample_size": len(prices_cad),
    }


def _scrape_wine_searcher(wine_name: str, vintage: Optional[int] = None) -> list[PricePoint]:
    """Lightweight scraping fallback — parses search result page."""
    query = f"{wine_name} {vintage or ''}".strip()
    search_url = "https://www.wine-searcher.com/find/" + query.replace(" ", "+")

    try:
        resp = _fetch_page(search_url)
    except Exception as e:
        logger.warning("Wine-Searcher scrape failed: %s", e)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    points = []

    # Price containers on Wine-Searcher result pages
    for card in soup.select(".offer-item, [class*='price-block']")[:15]:
        price_el = card.select_one("[class*='price'], .price")
        if not price_el:
            continue
        raw_text = price_el.get_text(strip=True)
        amount, currency = _parse_price_string(raw_text)
        if amount <= 0:
            continue
        price_cad = amount * config.fx_rate(currency)
        points.append(PricePoint(
            source="wine_searcher_web",
            price_original=amount,
            currency=currency,
            price_cad=round(price_cad, 2),
        ))

    return points
