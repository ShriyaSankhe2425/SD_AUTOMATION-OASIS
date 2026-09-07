"""CLI entry point for the purchase order parsing system.

Usage: python main.py [OPTIONS] INPUT_PATH
"""

import logging
import sys
from pathlib import Path

import click

import config
from pipeline import audit, export, extraction
from pipeline.run import process_document
from reference.loader import load_reference_data

logger = logging.getLogger(__name__)


@click.command()
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--model", default=config.DEFAULT_MODEL, show_default=True,
              help="Gemini model ID (passed through to the API as-is).")
@click.option("--output", "output_dir", type=click.Path(file_okay=False, path_type=Path),
              default=config.DEFAULT_OUTPUT_DIR, show_default=True, help="Output directory.")
@click.option("--threshold", type=click.IntRange(0, 100), default=config.DEFAULT_THRESHOLD,
              show_default=True, help="Fuzzy match minimum score 0-100.")
@click.option("--data-dir", type=click.Path(file_okay=False, path_type=Path),
              default=config.DATA_DIR, show_default=True,
              help="Directory containing the Excel reference files.")
@click.option("--verbose", is_flag=True, help="Write an audit .log file alongside the CSV.")
def main(input_path: Path, model: str, output_dir: Path, threshold: int,
         data_dir: Path, verbose: bool) -> None:
    """Extract structured data from a purchase order document (PDF or image),
    match it against Excel reference data, and export the result to CSV."""
    audit.setup_logging(verbose)

    if input_path.suffix.lower() not in config.SUPPORTED_EXTENSIONS:
        raise click.ClickException(
            f"Unsupported file type '{input_path.suffix}'. "
            f"Supported: {', '.join(sorted(config.SUPPORTED_EXTENSIONS))}"
        )
    if not config.GOOGLE_API_KEY:
        raise click.ClickException(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your "
            "Google AI Studio API key (https://aistudio.google.com/apikey)."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    reference = load_reference_data(data_dir)
    client = extraction.get_client(config.GOOGLE_API_KEY)

    try:
        results = process_document(input_path, client, model, reference, threshold)
    except Exception as exc:
        raise click.ClickException(f"Could not read {input_path}: {exc}") from exc
    if not results:
        raise click.ClickException(f"No pages found in {input_path}.")

    all_rows: list[dict] = []
    audit_records: list[str] = []
    failed_pages = 0

    for result in results:
        po, matches = result.po, result.matches
        if po.parse_error:
            failed_pages += 1
        all_rows.extend(export.po_to_rows(po, matches))
        audit_records.append(audit.format_page_record(po, matches))

    if not all_rows:
        raise click.ClickException("No pages yielded any extraction; nothing to write.")

    csv_path = output_dir / f"{input_path.stem}_output.csv"
    export.write_csv(all_rows, csv_path)
    click.echo(f"Wrote {len(all_rows)} row(s) to {csv_path}")

    if verbose:
        log_path = output_dir / f"{input_path.stem}_output.log"
        audit.write_audit_log(audit_records, log_path)
        click.echo(f"Audit log: {log_path}")

    if failed_pages:
        click.echo(f"Warning: {failed_pages} page(s) failed extraction "
                   f"(see parse_error column).", err=True)


if __name__ == "__main__":
    main()
