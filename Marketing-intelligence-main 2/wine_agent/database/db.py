"""SQLite persistence layer for wine intelligence data."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from wine_agent.models.wine import WineIntelligenceReport
from wine_agent.config.settings import config


def _get_connection() -> sqlite3.Connection:
    db_path = config.database_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wine_queries (
            id          TEXT PRIMARY KEY,
            wine_name   TEXT NOT NULL,
            producer    TEXT,
            vintage     INTEGER,
            query_json  TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            wine_name   TEXT NOT NULL,
            vintage     INTEGER,
            source      TEXT,
            price_cad   REAL,
            recorded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS critic_scores (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            wine_name   TEXT NOT NULL,
            vintage     INTEGER,
            critic      TEXT,
            score       REAL,
            recorded_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def save_report(report: WineIntelligenceReport) -> None:
    conn = _get_connection()
    now = datetime.utcnow().isoformat()

    # Serialise the entire report as JSON
    report_dict = {
        "query_id": report.query_id,
        "wine_name": report.wine_name,
        "producer": report.producer,
        "vintage": report.vintage,
        "generated_at": report.generated_at,
        "executive_summary": report.executive_summary,
        "buyer_recommendation": report.buyer_recommendation,
        "opportunity_score": report.opportunity_score,
        "risk_flags": report.risk_flags,
    }

    conn.execute(
        "INSERT OR REPLACE INTO wine_queries (id, wine_name, producer, vintage, query_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (report.query_id, report.wine_name, report.producer,
         report.vintage, json.dumps(report_dict), now)
    )

    for pp in report.price_benchmarks:
        conn.execute(
            "INSERT INTO price_history (wine_name, vintage, source, price_cad, recorded_at) VALUES (?,?,?,?,?)",
            (report.wine_name, report.vintage, pp.source, pp.price_cad, now)
        )

    for cs in report.critic_scores:
        conn.execute(
            "INSERT INTO critic_scores (wine_name, vintage, critic, score, recorded_at) VALUES (?,?,?,?,?)",
            (report.wine_name, report.vintage, cs.critic, cs.score, now)
        )

    conn.commit()
    conn.close()


def get_price_history(wine_name: str, vintage: Optional[int] = None) -> list[dict]:
    conn = _get_connection()
    if vintage:
        rows = conn.execute(
            "SELECT * FROM price_history WHERE wine_name LIKE ? AND vintage=? ORDER BY recorded_at DESC",
            (f"%{wine_name}%", vintage)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM price_history WHERE wine_name LIKE ? ORDER BY recorded_at DESC",
            (f"%{wine_name}%",)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
