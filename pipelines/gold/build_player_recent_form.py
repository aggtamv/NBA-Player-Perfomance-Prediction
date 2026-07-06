import argparse
from pathlib import Path

from pyspark.sql import Window
from pyspark.sql import functions as F

from pipelines.common import (
    GOLD_PLAYER_RECENT_FORM,
    MODEL_COLUMNS,
    ROLLING_FEATURES,
    SILVER_PLAYER_GAME_LOGS,
    create_spark,
    read_layer_csv,
    write_layer_csv,
)


def build_player_recent_form(input_path=SILVER_PLAYER_GAME_LOGS, output_path=GOLD_PLAYER_RECENT_FORM, write_csv=True):
    spark = create_spark("nba-gold-player-recent-form")
    input_path = Path(input_path)
    output_path = Path(output_path)

    silver = read_layer_csv(spark, input_path)

    silver = silver.withColumn("gameDateTs", F.to_timestamp("gameDateTs"))
    for column in MODEL_COLUMNS:
        silver = silver.withColumn(column, F.col(column).cast("double"))

    player_window = (
        Window.partitionBy("personId")
        .orderBy(F.col("gameDateTs").cast("long"))
        .rowsBetween(-10, -1)
    )

    featured = silver
    for column in ROLLING_FEATURES:
        featured = featured.withColumn(f"last_10_{column}_avg", F.avg(F.col(column)).over(player_window))

    featured = featured.withColumn("complete_games_in_prior_window", F.count(F.lit(1)).over(player_window))

    selected_columns = [
        "personId",
        "player",
        "gameId",
        "gameDate",
        "team",
        "opponent",
        "home",
        "win",
        "complete_games_in_prior_window",
    ] + MODEL_COLUMNS + [f"last_10_{column}_avg" for column in ROLLING_FEATURES]

    result = featured.select(*selected_columns)
    row_count = result.count()
    csv_file = write_layer_csv(result, output_path)
    spark.stop()
    return row_count, csv_file


def parse_args():
    parser = argparse.ArgumentParser(description="Build Gold player recent-form features.")
    parser.add_argument("--input", default=str(SILVER_PLAYER_GAME_LOGS), help="Silver input directory")
    parser.add_argument("--output", default=str(GOLD_PLAYER_RECENT_FORM), help="Gold output directory")
    parser.add_argument("--no-csv", action="store_true", help="Accepted for compatibility; local layers are always CSV")
    return parser.parse_args()


def main():
    args = parse_args()
    row_count, output_path = build_player_recent_form(args.input, args.output, write_csv=not args.no_csv)
    print(f"Gold player recent form: {row_count} feature rows written to {output_path}")


if __name__ == "__main__":
    main()
