import csv
import os
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"

BRONZE_ROOT = DATA_ROOT / "bronze"
SILVER_ROOT = DATA_ROOT / "silver"
GOLD_ROOT = DATA_ROOT / "gold"

PLAYER_STATISTICS_SOURCE = DATA_ROOT / "archive" / "PlayerStatistics.csv"
BRONZE_PLAYER_GAME_LOGS = BRONZE_ROOT / "player_game_logs"
SILVER_PLAYER_GAME_LOGS = SILVER_ROOT / "player_game_logs"
GOLD_PLAYER_RECENT_FORM = GOLD_ROOT / "player_recent_form"

PLAYER_IDENTITY_COLUMNS = [
    "firstName",
    "lastName",
    "personId",
    "gameId",
    "gameDate",
    "playerteamCity",
    "playerteamName",
    "opponentteamCity",
    "opponentteamName",
    "win",
    "home",
]

MODEL_COLUMNS = [
    "numMinutes",
    "points",
    "assists",
    "blocks",
    "steals",
    "fieldGoalsAttempted",
    "fieldGoalsMade",
    "fieldGoalsPercentage",
    "threePointersAttempted",
    "threePointersMade",
    "threePointersPercentage",
    "freeThrowsAttempted",
    "freeThrowsMade",
    "freeThrowsPercentage",
    "reboundsDefensive",
    "reboundsOffensive",
    "reboundsTotal",
    "foulsPersonal",
    "turnovers",
    "plusMinusPoints",
]

ROLLING_FEATURES = [
    "numMinutes",
    "points",
    "assists",
    "reboundsTotal",
    "fieldGoalsPercentage",
    "threePointersPercentage",
    "plusMinusPoints",
]

PLAYER_GAME_LOG_COLUMNS = PLAYER_IDENTITY_COLUMNS + MODEL_COLUMNS

DEFAULT_DEMO_SINCE_YEAR = int(os.getenv("PIPELINE_DEMO_SINCE_YEAR", "2024"))


def create_spark(app_name):
    if not os.getenv("JAVA_HOME"):
        raise RuntimeError(
            "JAVA_HOME is not set. Install Java 17 or 21 and set JAVA_HOME before running local PySpark."
        )

    return (
        SparkSession.builder
        .appName(app_name)
        .master(os.getenv("SPARK_LOCAL_MASTER", "local[1]"))
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "2g"))
        .config("spark.sql.shuffle.partitions", os.getenv("SPARK_SQL_SHUFFLE_PARTITIONS", "4"))
        .config("spark.default.parallelism", os.getenv("SPARK_DEFAULT_PARALLELISM", "4"))
        .getOrCreate()
    )


def parquet_path(layer_path):
    return Path(layer_path) / "parquet"


def csv_path(layer_path):
    return Path(layer_path) / "csv"


def layer_csv_file(layer_path):
    return csv_path(layer_path) / "data.csv"


def read_layer_csv(spark, layer_path):
    return (
        spark.read
        .option("header", True)
        .option("inferSchema", False)
        .csv(str(layer_csv_file(layer_path)))
    )


def write_layer_csv(df, layer_path):
    csv_file = layer_csv_file(layer_path)
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    safe_df = df.select([F.col(column).cast("string").alias(column) for column in df.columns])
    columns = safe_df.columns

    with csv_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in safe_df.toLocalIterator():
            writer.writerow([row[column] for column in columns])

    return csv_file
