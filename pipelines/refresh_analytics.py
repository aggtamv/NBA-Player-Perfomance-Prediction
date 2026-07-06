import argparse

from flask import Flask

from nba_app.config import Config
from nba_app.data_importer import import_gold_recent_form_to_sqlite
from nba_app.models import db
from pipelines.common import DEFAULT_DEMO_SINCE_YEAR
from pipelines.run_medallion import run_player_recent_form_pipeline


def create_import_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app


def refresh_analytics(since_year=DEFAULT_DEMO_SINCE_YEAR, row_limit=None):
    pipeline_result = run_player_recent_form_pipeline(since_year=since_year, row_limit=row_limit)

    app = create_import_app()
    with app.app_context():
        db.create_all()
        import_result = import_gold_recent_form_to_sqlite(force=True)

    return {
        "pipeline": pipeline_result,
        "sqlite": import_result,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Run PySpark Gold build and import the output into SQLite.")
    parser.add_argument("--since-year", type=int, default=DEFAULT_DEMO_SINCE_YEAR, help="Only ingest games from this year onward")
    parser.add_argument("--row-limit", type=int, default=None, help="Optional hard row limit for quick demo runs")
    parser.add_argument("--full", action="store_true", help="Process the full historical player statistics file")
    return parser.parse_args()


def main():
    args = parse_args()
    since_year = None if args.full else args.since_year
    result = refresh_analytics(since_year=since_year, row_limit=args.row_limit)

    for layer, details in result["pipeline"].items():
        print(f"{layer}: {details['rows']} rows -> {details['path']}")

    sqlite = result["sqlite"]
    print(f"sqlite: {sqlite['rows']} rows -> {sqlite['table']} ({sqlite['status']})")


if __name__ == "__main__":
    main()
