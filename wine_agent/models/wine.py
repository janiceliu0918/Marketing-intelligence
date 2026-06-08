"""Core data models for wine market intelligence."""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class WineClassification:
    appellation: str = ""           # e.g. Saint-Julien, Pomerol
    country: str = ""               # e.g. France, Italy
    region: str = ""                # e.g. Bordeaux, Burgundy
    sub_region: str = ""            # e.g. Médoc, Côte de Nuits
    classification: str = ""        # e.g. Grand Cru Classé 4ème, Premier Cru
    aoc_vdp_level: str = ""         # e.g. AOC, VDP.G, Prädikatswein
    grape_varieties: dict = field(default_factory=dict)   # {"Cabernet Sauvignon": 70, "Merlot": 30}
    vintage_year: Optional[int] = None
    vintage_rating: Optional[str] = None   # e.g. "Exceptional", "Good"
    oak_aging_months: Optional[int] = None
    alcohol_pct: Optional[float] = None


@dataclass
class PricePoint:
    source: str = ""               # "wine_searcher", "vivino", "supplier"
    price_original: float = 0.0
    currency: str = "USD"
    price_cad: float = 0.0         # Normalised to CAD
    bottle_size_ml: int = 750
    as_of_date: str = ""


@dataclass
class CriticScore:
    critic: str = ""               # "Wine Advocate", "Wine Spectator", "Jancis Robinson"
    score: Optional[float] = None  # numeric, e.g. 93
    score_max: float = 100.0
    tasting_note: str = ""
    review_date: str = ""


@dataclass
class ConsumerSentiment:
    platform: str = "vivino"
    average_rating: Optional[float] = None   # e.g. 4.2 / 5
    rating_count: int = 0
    positive_keywords: list = field(default_factory=list)
    negative_keywords: list = field(default_factory=list)
    flavour_tags: list = field(default_factory=list)
    sentiment_score: Optional[float] = None  # -1 to 1


@dataclass
class LandedCostBreakdown:
    fob_price_cad: float = 0.0
    freight_cad: float = 0.0
    insurance_cad: float = 0.0
    import_duty_cad: float = 0.0
    federal_excise_cad: float = 0.0
    ldb_markup_cad: float = 0.0
    gst_cad: float = 0.0
    total_landed_cad: float = 0.0
    suggested_retail_cad: float = 0.0       # LDB shelf price estimate
    gross_margin_pct: Optional[float] = None
    supplier_quote_cad: Optional[float] = None
    quote_vs_market: Optional[str] = None   # "Below Market", "At Market", "Above Market"


@dataclass
class WineIntelligenceReport:
    query_id: str = ""
    wine_name: str = ""
    producer: str = ""
    vintage: Optional[int] = None
    supplier_quote_eur: Optional[float] = None
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    classification: WineClassification = field(default_factory=WineClassification)
    price_benchmarks: list[PricePoint] = field(default_factory=list)
    critic_scores: list[CriticScore] = field(default_factory=list)
    consumer_sentiment: Optional[ConsumerSentiment] = None
    landed_cost: Optional[LandedCostBreakdown] = None

    # LLM-generated narrative fields
    executive_summary: str = ""
    vintage_assessment: str = ""
    market_positioning: str = ""
    buyer_recommendation: str = ""
    risk_flags: list[str] = field(default_factory=list)
    opportunity_score: Optional[int] = None   # 1-10 composite score
