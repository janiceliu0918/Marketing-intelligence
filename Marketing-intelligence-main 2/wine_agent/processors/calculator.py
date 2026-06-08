"""BC landed cost and retail price calculator for imported wine."""
from typing import Optional
from wine_agent.config.settings import config, ImportDutyConfig
from wine_agent.models.wine import LandedCostBreakdown


def _duty_rate(country: str, duties: ImportDutyConfig) -> float:
    """Return the applicable import duty rate for a given country of origin."""
    eu_countries = {
        "france", "italy", "spain", "germany", "portugal", "austria",
        "greece", "hungary", "romania", "bulgaria", "slovenia", "croatia",
    }
    if country.lower() in eu_countries:
        return duties.import_duty_eu
    if country.lower() in {"united states", "usa", "us"}:
        return duties.import_duty_us
    return duties.import_duty_other


def calculate_landed_cost(
    supplier_price_per_bottle: float,
    supplier_currency: str,
    country_of_origin: str,
    bottle_size_ml: int = 750,
    bottles_per_case: int = 12,
    duties: Optional[ImportDutyConfig] = None,
) -> LandedCostBreakdown:
    """
    Calculate the fully-loaded BC landed cost from a supplier's FOB price.

    Flow:
      FOB (CAD)
      + Freight & Insurance
      + Import Duty (on FOB+F+I = CIF)
      + Federal Excise Tax
      ─────────────────────
      = Landed Cost (before LDB)
      × LDB Markup (89% of landed)
      + GST (5%)
      ─────────────────────
      = Estimated LDB Shelf Price
    """
    if duties is None:
        duties = config.import_duties

    fx = config.fx_rate(supplier_currency)
    fob_cad = supplier_price_per_bottle * fx

    # Freight & Insurance — per bottle share
    freight_per_bottle = duties.freight_per_case / bottles_per_case
    insurance_per_bottle = fob_cad * duties.insurance_rate

    cif_cad = fob_cad + freight_per_bottle + insurance_per_bottle

    duty_rate = _duty_rate(country_of_origin, duties)
    import_duty_cad = cif_cad * duty_rate

    # Federal excise: CAD/litre → per bottle
    litres_per_bottle = bottle_size_ml / 1000
    excise_cad = duties.federal_excise_per_litre * litres_per_bottle

    landed_before_ldb = cif_cad + import_duty_cad + excise_cad

    # LDB markup applied on top of landed cost
    ldb_markup_cad = landed_before_ldb * duties.ldb_markup_rate
    subtotal = landed_before_ldb + ldb_markup_cad

    # GST on top
    gst_cad = subtotal * duties.gst_rate
    total_shelf_cad = subtotal + gst_cad

    # Suggested retail: round up to nearest $0.99
    suggested_retail = _round_retail(total_shelf_cad)

    return LandedCostBreakdown(
        fob_price_cad=round(fob_cad, 2),
        freight_cad=round(freight_per_bottle, 2),
        insurance_cad=round(insurance_per_bottle, 2),
        import_duty_cad=round(import_duty_cad, 2),
        federal_excise_cad=round(excise_cad, 2),
        ldb_markup_cad=round(ldb_markup_cad, 2),
        gst_cad=round(gst_cad, 2),
        total_landed_cad=round(total_shelf_cad, 2),
        suggested_retail_cad=suggested_retail,
        supplier_quote_cad=round(fob_cad, 2),
    )


def add_market_comparison(
    breakdown: LandedCostBreakdown,
    market_avg_cad: Optional[float],
) -> LandedCostBreakdown:
    """Annotate the breakdown with a quote-vs-market signal."""
    if market_avg_cad is None or breakdown.fob_price_cad <= 0:
        return breakdown

    ratio = breakdown.fob_price_cad / market_avg_cad
    if ratio < 0.90:
        breakdown.quote_vs_market = "Below Market (>10% discount)"
        breakdown.gross_margin_pct = round((1 - ratio) * 100, 1)
    elif ratio > 1.10:
        breakdown.quote_vs_market = "Above Market (>10% premium)"
        breakdown.gross_margin_pct = round((ratio - 1) * -100, 1)
    else:
        breakdown.quote_vs_market = "At Market (±10%)"
        breakdown.gross_margin_pct = round((1 - ratio) * 100, 1)

    return breakdown


def _round_retail(price: float) -> float:
    """Round to nearest dollar then subtract $0.01 (psychological pricing)."""
    return round(price / 1.0) - 0.01 if price > 1 else price
