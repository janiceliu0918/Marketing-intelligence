"""Winery official website parser.

Fetches tech-sheet information (grape varieties, vinification, aging) via
targeted HTTP requests, then uses Claude to extract structured data from
the raw HTML/text — avoiding brittle CSS selectors across hundreds of sites.
"""
import logging
import re
from typing import Optional
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
import anthropic

from wine_agent.config.settings import config
from wine_agent.models.wine import WineClassification

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Well-known producer homepage map (extend as needed)
_KNOWN_PRODUCERS: dict[str, str] = {
    "château talbot": "https://www.chateau-talbot.com",
    "château margaux": "https://www.chateau-margaux.com",
    "château latour": "https://www.chateau-latour.com",
    "château pichon baron": "https://www.pichonbaron.com",
    "château léoville barton": "https://www.leoville-barton.com",
    "domaine romanée-conti": "https://www.romanee-conti.fr",
    "domaine leroy": "https://domaine-leroy.com",
    "sassicaia": "https://www.sassicaia.com",
    "ornellaia": "https://www.ornellaia.com",
    "opus one": "https://www.opusonewinery.com",
}


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=6))
def _fetch(url: str) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def _clean_html(html: str, max_chars: int = 6000) -> str:
    """Strip boilerplate and return readable text, capped for LLM context."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    # Collapse blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


def _llm_extract_classification(raw_text: str, wine_name: str, vintage: Optional[int]) -> WineClassification:
    """Ask Claude to parse winery page text into a structured WineClassification."""
    if not config.anthropic_api_key:
        logger.warning("No ANTHROPIC_API_KEY — skipping LLM extraction from winery page")
        return WineClassification()

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    prompt = f"""You are a Master of Wine analysing winery technical documentation.

Wine being researched: {wine_name} {vintage or ''}

Below is text extracted from the winery's website. Extract ONLY facts that are
explicitly stated. Return a JSON object with these keys (use null for missing):
- appellation  (e.g. "Saint-Julien")
- country
- region       (e.g. "Bordeaux")
- sub_region
- classification (e.g. "4ème Grand Cru Classé")
- aoc_vdp_level (e.g. "AOC")
- grape_varieties  (object: {{"Cabernet Sauvignon": 70, "Merlot": 30}})
- vintage_year (integer)
- oak_aging_months (integer)
- alcohol_pct (float)
- vintage_rating  (string: one of "Exceptional", "Outstanding", "Very Good", "Good", "Average", "Poor", or null)

WINERY PAGE TEXT:
{raw_text}

Respond ONLY with the JSON object, no explanation."""

    try:
        message = client.messages.create(
            model=config.claude_model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        raw_json = message.content[0].text.strip()
        # Strip markdown code fences if present
        raw_json = re.sub(r"^```[a-z]*\n?", "", raw_json)
        raw_json = re.sub(r"\n?```$", "", raw_json)
        data = json.loads(raw_json)
        return WineClassification(
            appellation=data.get("appellation") or "",
            country=data.get("country") or "",
            region=data.get("region") or "",
            sub_region=data.get("sub_region") or "",
            classification=data.get("classification") or "",
            aoc_vdp_level=data.get("aoc_vdp_level") or "",
            grape_varieties=data.get("grape_varieties") or {},
            vintage_year=data.get("vintage_year"),
            oak_aging_months=data.get("oak_aging_months"),
            alcohol_pct=data.get("alcohol_pct"),
            vintage_rating=data.get("vintage_rating"),
        )
    except Exception as e:
        logger.warning("LLM winery extraction failed: %s", e)
        return WineClassification()


def fetch_winery_classification(producer: str, wine_name: str,
                                vintage: Optional[int] = None) -> WineClassification:
    """
    Main entry point: look up winery URL, fetch page, extract classification.
    Falls back to a minimal classification object if anything fails.
    """
    base_url = _KNOWN_PRODUCERS.get(producer.lower().strip())
    if not base_url:
        logger.info("No known URL for producer '%s' — skipping winery fetch", producer)
        return WineClassification()

    try:
        html = _fetch(base_url)
        clean_text = _clean_html(html)
        return _llm_extract_classification(clean_text, wine_name, vintage)
    except Exception as e:
        logger.warning("Winery fetch failed for %s: %s", base_url, e)
        return WineClassification()
