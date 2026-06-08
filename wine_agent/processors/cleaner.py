"""Data cleaning and normalisation utilities for scraped wine data."""
import re
from typing import Optional
import pandas as pd


def normalise_wine_name(raw: str) -> str:
    """Normalise wine name: strip accent ambiguity, collapse whitespace."""
    name = raw.strip()
    name = re.sub(r"\s+", " ", name)
    return name


def normalise_vintage(raw: str | int | None) -> Optional[int]:
    """Extract a 4-digit vintage year from various raw inputs."""
    if raw is None:
        return None
    text = str(raw)
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group(0)) if match else None


def clean_price_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise a DataFrame of scraped prices.
    Expected columns: source, price_original, currency, price_cad, bottle_size_ml
    """
    df = df.copy()

    # Drop rows missing core fields
    df = df.dropna(subset=["price_cad"])
    df = df[df["price_cad"] > 0]

    # Normalise bottle sizes to 750ml equivalents
    if "bottle_size_ml" in df.columns:
        df["price_cad_750"] = df.apply(
            lambda r: r["price_cad"] * (750 / r["bottle_size_ml"])
            if r.get("bottle_size_ml") and r["bottle_size_ml"] > 0
            else r["price_cad"],
            axis=1,
        )
    else:
        df["price_cad_750"] = df["price_cad"]

    # Remove outliers beyond 3 standard deviations
    mean = df["price_cad_750"].mean()
    std = df["price_cad_750"].std()
    if std > 0:
        df = df[abs(df["price_cad_750"] - mean) <= 3 * std]

    return df.reset_index(drop=True)


def build_price_summary(df: pd.DataFrame) -> dict:
    """Return summary statistics from a cleaned price DataFrame."""
    if df.empty:
        return {}
    col = "price_cad_750" if "price_cad_750" in df.columns else "price_cad"
    return {
        "mean": round(df[col].mean(), 2),
        "median": round(df[col].median(), 2),
        "min": round(df[col].min(), 2),
        "max": round(df[col].max(), 2),
        "std": round(df[col].std(), 2),
        "count": len(df),
    }
