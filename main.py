#!/usr/bin/env python3
"""
Bonvin Wine Market Intelligence Agent — CLI entry point.

Usage examples:
  python main.py "Château Talbot" --vintage 2019 --quote 45 --currency EUR
  python main.py "Sassicaia" --vintage 2020 --quote 180 --currency EUR --export all
  python main.py "Opus One" --vintage 2019 --no-export
"""
import argparse
import logging
import sys
from pathlib import Path

from wine_agent.agent.wine_agent import WineIntelligenceAgent
from wine_agent.database.db import init_db, save_report
from wine_agent.reports.generator import print_report, export_markdown, export_excel, export_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bonvin Wine Market Intelligence Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("wine_name", help="Wine name, e.g. 'Château Talbot'")
    parser.add_argument("--producer", default="", help="Producer name if different from wine name")
    parser.add_argument("--vintage", type=int, default=None, help="Vintage year, e.g. 2019")
    parser.add_argument("--quote", type=float, default=None, help="Supplier price per bottle (numeric)")
    parser.add_argument("--currency", default="EUR", choices=["EUR", "USD", "GBP", "CAD"],
                        help="Supplier quote currency (default: EUR)")
    parser.add_argument("--export", default="markdown",
                        choices=["none", "markdown", "excel", "json", "all"],
                        help="Export format(s) (default: markdown)")
    parser.add_argument("--output-dir", default=None, help="Output directory for reports")
    parser.add_argument("--no-db", action="store_true", help="Skip saving to database")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not args.no_db:
        init_db()

    print(f"\n🍷  Bonvin Wine Intelligence Agent")
    print(f"    Analysing: {args.wine_name} {args.vintage or ''}")
    if args.quote:
        print(f"    Supplier quote: {args.currency} {args.quote:.2f}/bottle")
    print("    Connecting to data sources...\n")

    agent = WineIntelligenceAgent()

    report = agent.analyse(
        wine_name=args.wine_name,
        producer=args.producer or args.wine_name,
        vintage=args.vintage,
        supplier_quote=args.quote,
        supplier_currency=args.currency,
    )

    # Print to console
    print_report(report)

    # Save to DB
    if not args.no_db:
        save_report(report)
        print(f"\n  Report saved to database (ID: {report.query_id})")

    # Export files
    if args.export in ("markdown", "all"):
        path = export_markdown(report, args.output_dir)
        print(f"  Markdown: {path}")

    if args.export in ("excel", "all"):
        path = export_excel(report, args.output_dir)
        if path:
            print(f"  Excel:    {path}")

    if args.export in ("json", "all"):
        path = export_json(report, args.output_dir)
        print(f"  JSON:     {path}")

    print()


if __name__ == "__main__":
    main()
