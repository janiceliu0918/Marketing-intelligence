"""Unit tests for the BC landed cost calculator."""
import pytest
from wine_agent.processors.calculator import calculate_landed_cost, add_market_comparison
from wine_agent.config.settings import ImportDutyConfig


@pytest.fixture
def duties():
    return ImportDutyConfig()


def test_eu_wine_zero_duty(duties):
    """CETA: French wine should have 0% import duty."""
    result = calculate_landed_cost(
        supplier_price_per_bottle=45.0,
        supplier_currency="EUR",
        country_of_origin="France",
        duties=duties,
    )
    assert result.import_duty_cad == 0.0


def test_us_wine_has_duty(duties):
    """US wine should attract ~6.2% duty on CIF value."""
    result = calculate_landed_cost(
        supplier_price_per_bottle=50.0,
        supplier_currency="USD",
        country_of_origin="United States",
        duties=duties,
    )
    assert result.import_duty_cad > 0


def test_shelf_price_exceeds_fob(duties):
    """Shelf price must always exceed FOB after all markups."""
    result = calculate_landed_cost(
        supplier_price_per_bottle=30.0,
        supplier_currency="EUR",
        country_of_origin="Italy",
        duties=duties,
    )
    assert result.suggested_retail_cad > result.fob_price_cad


def test_all_components_positive(duties):
    """Every cost component should be non-negative."""
    result = calculate_landed_cost(
        supplier_price_per_bottle=60.0,
        supplier_currency="EUR",
        country_of_origin="Spain",
        duties=duties,
    )
    assert result.fob_price_cad >= 0
    assert result.freight_cad >= 0
    assert result.federal_excise_cad >= 0
    assert result.ldb_markup_cad >= 0
    assert result.gst_cad >= 0


def test_market_comparison_below(duties):
    """Quote significantly below market should be flagged."""
    result = calculate_landed_cost(30.0, "EUR", "France", duties=duties)
    # Suppose market avg is much higher (CAD ~85)
    result = add_market_comparison(result, market_avg_cad=85.0)
    assert result.quote_vs_market is not None
    assert "Below" in result.quote_vs_market


def test_market_comparison_above(duties):
    """Quote significantly above market should be flagged."""
    result = calculate_landed_cost(100.0, "EUR", "France", duties=duties)
    result = add_market_comparison(result, market_avg_cad=60.0)
    assert "Above" in result.quote_vs_market


def test_market_comparison_at_market(duties):
    """Quote close to market should return At Market."""
    result = calculate_landed_cost(50.0, "EUR", "France", duties=duties)
    # FOB in CAD ≈ 50 * 1.48 = 74; market avg 75 → ratio ≈ 0.987
    result = add_market_comparison(result, market_avg_cad=result.fob_price_cad * 1.02)
    assert "At Market" in result.quote_vs_market
