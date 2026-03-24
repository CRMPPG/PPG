"""CLI interface for PPG distressed property analysis."""

import csv
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ppg.analysis.distress_scorer import rank_properties, score_property
from ppg.models.database import init_db, get_session, Property
from ppg.pipeline import run_csv_pipeline, run_recorder_pipeline, run_scraper_pipeline
from ppg.scrapers.csv_import import import_csv
from ppg.scrapers.generic_assessor import GenericAssessorScraper

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """PPG - Distressed Property Analysis Pipeline.

    Scrape county assessor data, compare against listings, and identify
    the most distressed properties.
    """


@cli.command()
@click.argument("listing_csv", type=click.Path(exists=True))
@click.argument("assessor_csv", type=click.Path(exists=True))
@click.option("--db", default=None, help="Database URL (default: sqlite:///ppg.db)")
@click.option("--top", default=20, help="Show top N results")
@click.option("--export", type=click.Path(), help="Export results to CSV")
def analyze(listing_csv, assessor_csv, db, top, export):
    """Analyze listings against assessor data from CSV files.

    LISTING_CSV: CSV file with property listings (address, price, etc.)
    ASSESSOR_CSV: CSV file with county assessor records
    """
    console.print(f"[bold]Loading listings from[/bold] {listing_csv}")
    console.print(f"[bold]Loading assessor data from[/bold] {assessor_csv}")

    ranked = run_csv_pipeline(listing_csv, assessor_csv, database_url=db)

    console.print(f"\n[bold green]Matched and scored {len(ranked)} properties[/bold green]\n")
    _display_results(ranked[:top])

    if export:
        _export_csv(ranked, export)
        console.print(f"\n[bold]Exported {len(ranked)} records to {export}[/bold]")


@cli.command()
@click.argument("listing_csv", type=click.Path(exists=True))
@click.option("--county-url", required=True, help="County assessor base URL")
@click.option("--county-name", default="Unknown", help="County name")
@click.option("--state", default="", help="State abbreviation")
@click.option("--delay", default=2.0, help="Delay between requests (seconds)")
@click.option("--db", default=None, help="Database URL")
@click.option("--top", default=20, help="Show top N results")
@click.option("--export", type=click.Path(), help="Export results to CSV")
def scrape(listing_csv, county_url, county_name, state, delay, db, top, export):
    """Scrape county assessor and compare against listings.

    Fetches assessor data live for each listing address.
    """
    scraper = GenericAssessorScraper(
        base_url=county_url,
        county_name=county_name,
        state=state,
        delay_seconds=delay,
    )

    console.print(f"[bold]Scraping {county_name} County assessor at {county_url}[/bold]")
    console.print(f"[bold]Listings from[/bold] {listing_csv}")

    ranked = run_scraper_pipeline(scraper, listing_csv, database_url=db)

    console.print(f"\n[bold green]Matched and scored {len(ranked)} properties[/bold green]\n")
    _display_results(ranked[:top])

    if export:
        _export_csv(ranked, export)


@cli.command()
@click.argument("listing_csv", type=click.Path(exists=True))
@click.option("--no-headless", is_flag=True, help="Show browser window (for debugging)")
@click.option("--delay", default=3.0, help="Delay between recorder searches (seconds)")
@click.option("--db", default=None, help="Database URL")
@click.option("--top", default=20, help="Show top N results")
@click.option("--export", type=click.Path(), help="Export results to CSV")
def recorder(listing_csv, no_headless, delay, db, top, export):
    """Search Clark County Recorder for distress documents on MLS listings.

    LISTING_CSV: MLS export CSV with parcel numbers and property details.
    Searches for Notices of Default, Lis Pendens, Liens, and Trustee Sales
    against the Clark County NV Recorder (AcclaimWeb).
    """
    console.print("[bold]Clark County Recorder - Distressed Property Search[/bold]")
    console.print(f"[bold]Listings from[/bold] {listing_csv}")
    console.print(f"[bold]Headless:[/bold] {not no_headless}  [bold]Delay:[/bold] {delay}s\n")

    ranked = run_recorder_pipeline(
        listing_csv,
        headless=not no_headless,
        delay=delay,
        database_url=db,
    )

    distressed = [p for p in ranked if p.get("distress_score", 0) > 0]
    console.print(
        f"\n[bold green]Scored {len(ranked)} properties, "
        f"{len(distressed)} with distress signals[/bold green]\n"
    )
    _display_results(ranked[:top])

    if export:
        _export_csv(ranked, export)
        console.print(f"\n[bold]Exported {len(ranked)} records to {export}[/bold]")


@cli.command()
@click.argument("csv_file", type=click.Path(exists=True))
@click.option("--top", default=20, help="Show top N results")
@click.option("--export", type=click.Path(), help="Export results to CSV")
def score(csv_file, top, export):
    """Score properties from a single CSV file (no matching needed).

    Use this when your CSV already contains both listing and assessor fields.
    """
    records = import_csv(csv_file)
    ranked = rank_properties(records)

    console.print(f"\n[bold green]Scored {len(ranked)} properties[/bold green]\n")
    _display_results(ranked[:top])

    if export:
        _export_csv(ranked, export)


@cli.command()
@click.option("--db", default=None, help="Database URL")
@click.option("--min-score", default=0.0, help="Minimum distress score")
@click.option("--top", default=20, help="Show top N results")
def report(db, min_score, top):
    """Show stored distressed properties from the database."""
    init_db(db)
    session = get_session(db)
    query = (
        session.query(Property)
        .filter(Property.distress_score >= min_score)
        .order_by(Property.distress_score.desc())
        .limit(top)
    )
    properties = query.all()

    if not properties:
        console.print("[yellow]No properties found matching criteria.[/yellow]")
        return

    records = []
    for p in properties:
        records.append({
            "address": p.address,
            "city": p.city,
            "list_price": p.list_price,
            "assessed_value": p.assessed_value,
            "distress_score": p.distress_score,
            "tax_delinquent": p.tax_delinquent,
            "in_foreclosure": p.in_foreclosure,
            "days_on_market": p.days_on_market,
        })

    _display_results(records)


def _display_results(properties: list[dict]):
    """Render a rich table of scored properties."""
    table = Table(title="Distressed Properties (ranked)", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Address", min_width=25)
    table.add_column("City", min_width=10)
    table.add_column("List Price", justify="right")
    table.add_column("Assessed Value", justify="right")
    table.add_column("Ratio", justify="right")
    table.add_column("Distress Score", justify="right", style="bold")
    table.add_column("Key Flags")

    for i, prop in enumerate(properties, 1):
        flags = []
        if prop.get("notice_of_default"):
            flags.append("NOD")
        if prop.get("lis_pendens"):
            flags.append("LIS PENDENS")
        if prop.get("trustee_sale_scheduled"):
            flags.append("TRUSTEE SALE")
        if prop.get("tax_delinquent"):
            flags.append("TAX DELINQ")
        if prop.get("in_foreclosure") and not prop.get("notice_of_default"):
            flags.append("FORECLOSURE")
        if prop.get("is_bank_owned"):
            flags.append("REO")
        if prop.get("has_liens"):
            flags.append("LIENS")
        if prop.get("is_vacant"):
            flags.append("VACANT")
        if prop.get("code_violations", 0):
            flags.append(f"VIOLATIONS({prop['code_violations']})")

        score_val = prop.get("distress_score", 0)
        score_style = "green" if score_val < 30 else "yellow" if score_val < 60 else "red"

        list_price = prop.get("list_price")
        assessed = prop.get("assessed_value")
        ratio = prop.get("price_to_assessed_ratio")

        table.add_row(
            str(i),
            prop.get("address", "N/A"),
            prop.get("city", ""),
            f"${list_price:,.0f}" if list_price else "-",
            f"${assessed:,.0f}" if assessed else "-",
            f"{ratio:.2f}" if ratio else "-",
            f"[{score_style}]{score_val:.1f}[/{score_style}]",
            ", ".join(flags) if flags else "-",
        )

    console.print(table)


def _export_csv(properties: list[dict], filepath: str):
    """Export results to CSV."""
    if not properties:
        return
    export_fields = [
        "address", "city", "state", "zip_code", "county", "parcel_number",
        "property_type", "bedrooms", "bathrooms", "sqft", "year_built",
        "list_price", "assessed_value", "market_value", "price_to_assessed_ratio",
        "annual_tax_amount", "tax_delinquent", "tax_delinquent_amount",
        "notice_of_default", "nod_date", "lis_pendens", "trustee_sale_scheduled",
        "recorder_document_count",
        "has_liens", "lien_amount", "in_foreclosure", "is_bank_owned", "is_vacant",
        "code_violations", "days_on_market", "distress_score",
    ]
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=export_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(properties)


if __name__ == "__main__":
    cli()
