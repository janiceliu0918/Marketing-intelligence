"""Vivino data collector — ratings, reviews, and consumer sentiment signals."""
import re
import time
import logging
from typing import Optional
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from wine_agent.config.settings import config
from wine_agent.models.wine import PricePoint, ConsumerSentiment

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "x-vivino-api-version": "2",
}

# Vivino's unofficial API endpoint (public, no auth needed)
_VIVINO_SEARCH = "https://www.vivino.com/api/explore/explore"
_VIVINO_WINE   = "https://www.vivino.com/api/wines/{wine_id}"

# Common positive/negative flavour keywords to track
_POSITIVE_KEYWORDS = [
    "smooth", "elegant", "complex", "balanced", "rich", "velvety",
    "fruit-forward", "aromatic", "long finish", "great value", "structured",
    "silky", "refined", "mineral", "fresh",
]
_NEGATIVE_KEYWORDS = [
    "tannic", "harsh", "thin", "watery", "acidic", "short finish",
    "overpriced", "flat", "bitter", "astringent",
]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def _vivino_api(url: str, params: Optional[dict] = None) -> dict:
    resp = requests.get(url, headers=_HEADERS, params=params, timeout=12)
    resp.raise_for_status()
    time.sleep(1.0)
    return resp.json()


def _extract_keywords(reviews: list[str], keywords: list[str]) -> list[str]:
    found = []
    combined = " ".join(reviews).lower()
    for kw in keywords:
        if kw.lower() in combined:
            found.append(kw)
    return found


def fetch_vivino_data(wine_name: str, vintage: Optional[int] = None) -> dict:
    """
    Search Vivino for a wine and return structured rating + sentiment data.
    Returns a dict with 'sentiment', 'price_point', and 'wine_id'.
    """
    params = {
        "q": f"{wine_name} {vintage or ''}".strip(),
        "language": "en",
        "country_codes[]": "",
        "per_page": 5,
    }

    try:
        data = _vivino_api(_VIVINO_SEARCH, params)
    except Exception as e:
        logger.warning("Vivino search failed: %s", e)
        return _empty_result()

    matches = data.get("explore_vintage", {}).get("matches", [])
    if not matches:
        return _empty_result()

    # Take the top match
    top = matches[0]
    vintage_obj = top.get("vintage", {})
    wine_obj = vintage_obj.get("wine", {})
    stats = vintage_obj.get("statistics", {})

    wine_id = wine_obj.get("id")
    avg_rating = stats.get("ratings_average")
    rating_count = stats.get("ratings_count", 0)

    # Price data from Vivino
    price_info = top.get("price", {})
    price_cad: Optional[float] = None
    price_original: Optional[float] = None
    currency = "USD"
    if price_info:
        price_original = price_info.get("amount")
        currency = price_info.get("currency", {}).get("code", "USD")
        if price_original:
            price_cad = round(float(price_original) * config.fx_rate(currency), 2)

    # Flavour tags from Vivino's taste structure
    taste = vintage_obj.get("taste", {})
    flavour_tags = []
    for group in taste.get("flavor", []):
        for item in group.get("primary_keywords", []):
            name = item.get("name", "")
            if name:
                flavour_tags.append(name)

    # Sentiment — approximate from rating distribution
    sentiment_score = _rating_to_sentiment(avg_rating)

    # Fetch top reviews for keyword extraction (best-effort)
    review_texts = _fetch_top_reviews(wine_id) if wine_id else []
    positive_kws = _extract_keywords(review_texts, _POSITIVE_KEYWORDS)
    negative_kws = _extract_keywords(review_texts, _NEGATIVE_KEYWORDS)

    sentiment = ConsumerSentiment(
        platform="vivino",
        average_rating=avg_rating,
        rating_count=rating_count,
        positive_keywords=positive_kws,
        negative_keywords=negative_kws,
        flavour_tags=flavour_tags[:10],
        sentiment_score=sentiment_score,
    )

    pp = None
    if price_cad:
        pp = PricePoint(
            source="vivino",
            price_original=float(price_original),
            currency=currency,
            price_cad=price_cad,
        )

    return {"sentiment": sentiment, "price_point": pp, "wine_id": wine_id}


def _fetch_top_reviews(wine_id: int, count: int = 10) -> list[str]:
    """Fetch latest public review notes for a given Vivino wine ID."""
    url = f"https://www.vivino.com/api/wines/{wine_id}/reviews"
    try:
        data = _vivino_api(url, {"per_page": count})
        reviews = data.get("reviews", [])
        return [r.get("note", "") for r in reviews if r.get("note")]
    except Exception:
        return []


def _rating_to_sentiment(rating: Optional[float]) -> Optional[float]:
    if rating is None:
        return None
    # Vivino ratings 1-5; map linearly to -1..1 with neutral at 3.5
    return round((rating - 3.5) / 1.5, 3)


def _empty_result() -> dict:
    return {"sentiment": None, "price_point": None, "wine_id": None}
