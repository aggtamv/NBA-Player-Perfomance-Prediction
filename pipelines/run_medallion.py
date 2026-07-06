import argparse

from pipelines.bronze.ingest_player_game_logs import ingest_player_game_logs
from pipelines.gold.build_player_recent_form import build_player_recent_form
from pipelines.silver.clean_player_game_logs import clean_player_game_logs
from pipelines.common import DEFAULT_DEMO_SINCE_YEAR


def run_player_recent_form_pipeline(write_csv=True, since_year=DEFAULT_DEMO_SINCE_YEAR, row_limit=None):
    bronze_rows, bronze_path = ingest_player_game_logs(since_year=since_year, row_limit=row_limit)
    silver_rows, silver_path = clean_player_game_logs()
    gold_rows, gold_path = build_player_recent_form(write_csv=write_csv)

    return {
        "bronze": {"rows": bronze_rows, "path": str(bronze_path)},
        "silver": {"rows": silver_rows, "path": str(silver_path)},
        "gold": {"rows": gold_rows, "path": str(gold_path)},
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Run the local Bronze -> Silver -> Gold player feature pipeline.")
    parser.add_argument("--no-csv", action="store_true", help="Accepted for compatibility; local layers are always CSV")
    parser.add_argument("--since-year", type=int, default=DEFAULT_DEMO_SINCE_YEAR, help="Only ingest games from this year onward")
    parser.add_argument("--row-limit", type=int, default=None, help="Optional hard row limit for quick demo runs")
    parser.add_argument("--full", action="store_true", help="Process the full historical player statistics file")
    return parser.parse_args()


def main():
    args = parse_args()
    since_year = None if args.full else args.since_year
    result = run_player_recent_form_pipeline(
        write_csv=not args.no_csv,
        since_year=since_year,
        row_limit=args.row_limit,
    )
    for layer, details in result.items():
        print(f"{layer}: {details['rows']} rows -> {details['path']}")


if __name__ == "__main__":
    main()
