"""Central configuration for the Wine Market Intelligence Agent."""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ImportDutyConfig:
    """BC import duty and tax configuration for wine."""
    # BC Liquor Distribution Branch markup tiers (as of 2024)
    ldb_markup_rate: float = 0.89        # 89% LDB markup on landed cost
    gst_rate: float = 0.05               # 5% GST
    pst_rate: float = 0.00               # Wine exempt from PST in BC
    federal_excise_per_litre: float = 0.688  # CAD per litre (>7% ABV)
    import_duty_eu: float = 0.00         # CETA: 0% for EU wines
    import_duty_us: float = 0.062        # 6.2% for US wines (non-CETA)
    import_duty_other: float = 0.112     # 11.2% general MFN rate
    freight_per_case: float = 8.50       # Estimated CAD per 12-bottle case
    insurance_rate: float = 0.005        # 0.5% of FOB value
    brokerage_per_shipment: float = 150  # CAD, amortised estimate


@dataclass
class AppConfig:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    wine_searcher_api_key: str = field(default_factory=lambda: os.getenv("WINE_SEARCHER_API_KEY", ""))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///wine_intelligence.db"))
    reports_dir: str = field(default_factory=lambda: os.getenv("REPORTS_DIR", "reports_output"))
    claude_model: str = "claude-sonnet-4-6"
    default_currency: str = "CAD"
    default_bottle_size_ml: int = 750
    cad_usd_rate: float = field(default_factory=lambda: float(os.getenv("CAD_USD_RATE", "1.36")))
    cad_eur_rate: float = field(default_factory=lambda: float(os.getenv("CAD_EUR_RATE", "1.48")))
    cad_gbp_rate: float = field(default_factory=lambda: float(os.getenv("CAD_GBP_RATE", "1.73")))
    import_duties: ImportDutyConfig = field(default_factory=ImportDutyConfig)

    def fx_rate(self, from_currency: str) -> float:
        """Return CAD per 1 unit of from_currency."""
        mapping = {"USD": self.cad_usd_rate, "EUR": self.cad_eur_rate,
                   "GBP": self.cad_gbp_rate, "CAD": 1.0}
        return mapping.get(from_currency.upper(), 1.0)


config = AppConfig()
