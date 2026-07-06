# Local PySpark Medallion Pipelines

This folder contains local, no-subscription PySpark pipelines for the NBA project.

The pipeline follows a medallion layout:

```text
Bronze -> raw ingested data
Silver -> cleaned and typed data
Gold   -> analytics/model-ready features
```

## Setup

Install project dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PySpark runs locally and does not require Databricks. Local Spark requires Java. Install Java 17 or 21, then set `JAVA_HOME`.

PowerShell example:

```powershell
$env:JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-21"
$env:PATH="$env:JAVA_HOME\bin;$env:PATH"
java -version
```

On Windows, Spark may still print a `winutils.exe` warning. The local pipeline avoids Spark's Hadoop file writer and stores each layer as a normal CSV file, so that warning should not block the run.

The default local Spark settings are intentionally conservative for Windows and demo usage:

```text
SPARK_LOCAL_MASTER=local[1]
SPARK_DRIVER_MEMORY=2g
SPARK_SQL_SHUFFLE_PARTITIONS=4
PIPELINE_DEMO_SINCE_YEAR=2024
```

You can override them in PowerShell before running the pipeline if your machine has more memory.

## Run The Full Pipeline

```powershell
.\.venv\Scripts\python.exe -m pipelines.run_medallion
```

By default this runs a demo-sized build using games from 2024 onward. It keeps the project presentation-friendly without writing several huge layer files.

For a very quick smoke test:

```powershell
.\.venv\Scripts\python.exe -m pipelines.run_medallion --row-limit 50000
```

For the full historical build:

```powershell
.\.venv\Scripts\python.exe -m pipelines.run_medallion --full
```

To run the PySpark pipeline and import the Gold dataset into the Flask SQLite database:

```powershell
.\.venv\Scripts\python.exe -m pipelines.refresh_analytics
```

This runs:

```text
data/archive/PlayerStatistics.csv
  -> data/bronze/player_game_logs/csv/data.csv
  -> data/silver/player_game_logs/csv/data.csv
  -> data/gold/player_recent_form/csv/data.csv
```

## Layer Commands

Bronze ingestion:

```powershell
.\.venv\Scripts\python.exe -m pipelines.bronze.ingest_player_game_logs
```

Silver cleaning:

```powershell
.\.venv\Scripts\python.exe -m pipelines.silver.clean_player_game_logs
```

Gold feature build:

```powershell
.\.venv\Scripts\python.exe -m pipelines.gold.build_player_recent_form
```

Backward-compatible command:

```powershell
.\.venv\Scripts\python.exe -m pipelines.build_player_recent_form
```

## Current Gold Dataset

`data/gold/player_recent_form/csv/data.csv` contains one row per complete player game plus rolling prior-10-game features:

```text
last_10_numMinutes_avg
last_10_points_avg
last_10_assists_avg
last_10_reboundsTotal_avg
last_10_fieldGoalsPercentage_avg
last_10_threePointersPercentage_avg
last_10_plusMinusPoints_avg
```

These outputs can be imported into SQLite for the Flask app or used for model retraining. If this is moved to Databricks or a machine with Hadoop tools configured, the same transformations can be switched back to Parquet for larger datasets.

The Flask app imports `data/gold/player_recent_form/csv/data.csv` into the `player_recent_form` SQLite table and uses that table for player search and prediction inputs. If the Gold table is missing, it falls back to the older sample player statistics path.
