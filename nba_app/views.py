from flask import Blueprint, render_template, render_template, request, jsonify, flash, redirect, url_for, session, current_app, send_file
from flask_login import login_required, current_user
from backend.data_scraper import *
from backend.scraper_client import refresh_latest_daily_games
import logging
import os
from gradio_client import Client, handle_file
import pandas as pd
from werkzeug.utils import secure_filename
from .config import Config
from .forms import UploadForm, PredictionForm
from .stats_repository import (
    PREDICTION_INFERENCE_COLUMNS,
    clean_prediction_input,
    get_latest_daily_games,
    get_player_totals,
    get_player_recent_form_overview,
    get_recent_prediction_stats_for_player,
    get_shooting_averages,
    search_prediction_player_names,
)
import plotly.express as px
import plotly
import json

views = Blueprint("views", __name__)

def _daily_games_snapshot():
    games, boxscores, latest_game_date = get_latest_daily_games()
    game_columns = [column for column in ["team", "score", "state"] if column in games.columns]
    boxscore_columns = [column for column in ["team", "Q1", "Q2", "Q3", "Q4", "OT", "2OT", "3OT"] if column in boxscores.columns]
    return {
        "latest_game_date": latest_game_date,
        "games": games[game_columns].to_dict(orient="records") if game_columns else [],
        "boxscores": boxscores[boxscore_columns].to_dict(orient="records") if boxscore_columns else [],
    }

@views.route("/home")
@views.route("/")
@login_required
def home():
    nba_games, nba_boxscores, latest_game_date = get_latest_daily_games()

    print(nba_games.head())
    print(nba_boxscores.head())
    refresh_daily_games_required = True
    data_fetch_required = latest_game_date is None or (nba_games.empty and nba_boxscores.empty)

    if not data_fetch_required:
        nba_games['score'] = pd.to_numeric(nba_games['score'], errors='coerce').fillna(0).astype(int)
        if 'team_logo' not in nba_games.columns:
            nba_games['team_logo'] = nba_games['team'].map(get_team_logo)
        else:
            nba_games['team_logo'] = nba_games.apply(
                lambda row: row['team_logo'] if pd.notna(row['team_logo']) and str(row['team_logo']).strip() else get_team_logo(row['team']),
                axis=1
            )
        quarter_columns = [col for col in ['Q1', 'Q2', 'Q3', 'Q4'] if col in nba_boxscores.columns]
        nba_boxscores[quarter_columns] = nba_boxscores[quarter_columns].apply(pd.to_numeric, errors='coerce').fillna(0).astype(int)

        games_list = nba_games.to_dict(orient='records')
        boxscores_list = nba_boxscores.to_dict(orient='records')
    else:
        games_list = []
        boxscores_list = []

    # Load total stats from SQLite, importing from CSV the first time.
    total_stats = get_player_totals()
    total_stats_dict = total_stats.to_dict(orient='records')
    top_scorer = None
    if not total_stats.empty and 'PTS' in total_stats.columns:
        top_scorer = total_stats.loc[pd.to_numeric(total_stats['PTS'], errors='coerce').idxmax()].to_dict()

    dashboard_metrics = {
        "player_count": len(total_stats_dict),
        "game_count": len(games_list) // 2,
        "team_count": total_stats['Team'].nunique() if 'Team' in total_stats.columns else 0,
        "top_scorer": top_scorer,
    }

    # Render the final view
    return render_template(
        'index.html',
        nba_games=games_list,
        nba_boxscores=boxscores_list,
        total_stats=total_stats_dict,
        dashboard_metrics=dashboard_metrics,
        data_fetch_required=data_fetch_required,
        refresh_daily_games_required=refresh_daily_games_required
    )

@views.route('/api/daily-games/refresh', methods=['GET'])
@login_required
def refresh_daily_games():
    game_date = request.args.get('date')
    try:
        before_snapshot = _daily_games_snapshot()

        if game_date:
            games, team_boxscores, player_boxscores = fetch_nba_daily_boxscores(game_date)
        else:
            games, team_boxscores = refresh_latest_daily_games()
            player_boxscores = []
        from .data_importer import import_daily_games_to_sqlite
        import_daily_games_to_sqlite(force=True)
        after_snapshot = _daily_games_snapshot()

        return jsonify({
            "status": "ok",
            "changed": before_snapshot != after_snapshot,
            "games_rows": len(games),
            "team_boxscore_rows": len(team_boxscores),
            "player_boxscore_rows": len(player_boxscores),
        })
    except Exception as e:
        current_app.logger.exception("Failed to fetch NBA daily games")
        return jsonify({"status": "error", "message": str(e)}), 500

@views.route('/stats')
@login_required
def stats():
    def percent_value(value):
        if value is None or pd.isna(value):
            return None
        return float(value) * 100

    def format_delta(value):
        if value is None or pd.isna(value):
            return None
        return float(value) * 100

    def format_table_value(column, value):
        if value is None or pd.isna(value):
            return "-"
        if column == "Year":
            return str(int(value))
        if isinstance(value, (int, float)):
            if abs(float(value)) <= 2:
                return f"{float(value) * 100:.1f}%"
            return f"{float(value):.2f}"
        return value

    def format_table(df):
        rows = []
        for record in df.to_dict(orient="records"):
            rows.append({
                column: format_table_value(column, value)
                for column, value in record.items()
            })
        return rows

    def json_records(df, columns):
        records = df[columns].where(pd.notna(df[columns]), None).to_dict(orient="records")
        return json.dumps(records)

    def format_recent_form_value(column, value):
        if value is None or pd.isna(value):
            return "-"
        if column == "gameDate":
            return pd.to_datetime(value).strftime("%Y-%m-%d")
        if column == "last_10_threePointersPercentage_avg":
            return f"{float(value) * 100:.1f}%"
        if column.startswith("last_10_") or column == "complete_games_in_prior_window":
            return f"{float(value):.1f}"
        return value

    try:
        shooting_avg, adj_shooting_avg = get_shooting_averages()
        shooting_avg = shooting_avg.sort_values('Year')
        adj_shooting_avg = adj_shooting_avg.sort_values('Year')
        shooting_display = shooting_avg.drop(columns=["source_file"], errors="ignore")
        adj_shooting_display = adj_shooting_avg.drop(columns=["source_file"], errors="ignore")
        
        raw_metric_options = [
            metric for metric in ['FGA_0_3', 'FGA_3_10', 'FGA_10_16', 'FGA_16_3P', 'FGA_3P', 'FG_0_3', 'FG_3P', 'TS%', 'eFG%', 'FTr', '3PAr']
            if metric in shooting_display.columns
        ]
        adjusted_metric_options = [
            metric for metric in ['FG%', '2P%', '3P%', 'eFG%', 'TS%', 'FTr', '3PAr', 'FG+', '2P+', '3P+', 'eFG+', 'TS+']
            if metric in adj_shooting_display.columns
        ]
        raw_default_metrics = [metric for metric in ['FGA_0_3', 'FGA_3P', 'FG_0_3', 'FG_3P'] if metric in raw_metric_options]
        adjusted_default_metrics = [metric for metric in ['FG%', '3P%', 'eFG%', 'TS%', 'FTr', '3PAr'] if metric in adjusted_metric_options]

        latest_raw = shooting_avg.iloc[-1].to_dict()
        latest_adjusted = adj_shooting_avg.iloc[-1].to_dict()
        previous_adjusted = adj_shooting_avg.iloc[-2].to_dict() if len(adj_shooting_avg) > 1 else {}
        first_adjusted = adj_shooting_avg.iloc[0].to_dict()
        latest_year = int(latest_adjusted.get('Year', latest_raw.get('Year', 0)))
        first_year = int(adj_shooting_avg.iloc[0]['Year'])

        stats_metrics = {
            "year_range": f"{first_year}-{latest_year}",
            "latest_year": latest_year,
            "latest_ts": percent_value(latest_adjusted.get('TS%')),
            "latest_ts_delta": format_delta(latest_adjusted.get('TS%') - previous_adjusted.get('TS%', latest_adjusted.get('TS%'))),
            "latest_efg": percent_value(latest_adjusted.get('eFG%')),
            "latest_efg_delta": format_delta(latest_adjusted.get('eFG%') - previous_adjusted.get('eFG%', latest_adjusted.get('eFG%'))),
            "latest_3par": percent_value(latest_adjusted.get('3PAr')),
            "latest_3par_delta": format_delta(latest_adjusted.get('3PAr') - previous_adjusted.get('3PAr', latest_adjusted.get('3PAr'))),
            "three_point_rate_change": format_delta(latest_adjusted.get('3PAr', 0) - first_adjusted.get('3PAr', 0)),
        }

        shooting_avg_json = json_records(shooting_display, ['Year'] + raw_metric_options)
        adj_shooting_avg_json = json_records(adj_shooting_display, ['Year'] + adjusted_metric_options)
        shooting_table = format_table(shooting_display.tail(10).sort_values('Year', ascending=False))
        adj_shooting_table = format_table(adj_shooting_display.tail(10).sort_values('Year', ascending=False))
        shooting_columns = shooting_display.columns.tolist()
        adj_shooting_columns = adj_shooting_display.columns.tolist()

    except Exception as e:
        print(f"Error loading shooting averages: {e}")
        shooting_avg_json = '[]'
        adj_shooting_avg_json = '[]'
        shooting_table = []
        adj_shooting_table = []
        shooting_columns = []
        adj_shooting_columns = []
        raw_metric_options = []
        adjusted_metric_options = []
        raw_default_metrics = []
        adjusted_default_metrics = []
        stats_metrics = {
            "year_range": None,
            "latest_year": None,
            "latest_ts": None,
            "latest_ts_delta": None,
            "latest_efg": None,
            "latest_efg_delta": None,
            "latest_3par": None,
            "latest_3par_delta": None,
            "three_point_rate_change": None,
        }

    try:
        recent_form = get_player_recent_form_overview()
        recent_form_columns = [
            "player",
            "team",
            "opponent",
            "gameDate",
            "last_10_points_avg",
            "last_10_assists_avg",
            "last_10_reboundsTotal_avg",
            "last_10_threePointersPercentage_avg",
            "last_10_plusMinusPoints_avg",
        ]
        recent_form_columns = [column for column in recent_form_columns if column in recent_form.columns]
        if not recent_form.empty and "team" in recent_form.columns:
            recent_form["team_logo"] = recent_form["team"].map(get_team_logo)
        recent_form_chart_columns = [
            "player",
            "team",
            "team_logo",
            "last_10_points_avg",
            "last_10_assists_avg",
            "last_10_reboundsTotal_avg",
        ]
        recent_form_chart_columns = [column for column in recent_form_chart_columns if column in recent_form.columns]
        recent_form_chart_json = json_records(recent_form, recent_form_chart_columns) if not recent_form.empty else "[]"
        recent_form_table = [
            {
                column: format_recent_form_value(column, value)
                for column, value in record.items()
            }
            for record in recent_form[recent_form_columns].to_dict(orient="records")
        ] if not recent_form.empty else []
        stats_metrics["gold_players"] = int(recent_form["player"].nunique()) if not recent_form.empty else 0
        stats_metrics["gold_top_player"] = recent_form.iloc[0]["player"] if not recent_form.empty else None
        stats_metrics["gold_top_points"] = float(recent_form.iloc[0]["last_10_points_avg"]) if not recent_form.empty else None
    except Exception as e:
        print(f"Error loading Gold player recent form: {e}")
        recent_form_chart_json = "[]"
        recent_form_table = []
        recent_form_columns = []
        stats_metrics["gold_players"] = 0
        stats_metrics["gold_top_player"] = None
        stats_metrics["gold_top_points"] = None

    return render_template(
        'stats.html',
        shooting_avg_json=shooting_avg_json,
        adj_shooting_avg_json=adj_shooting_avg_json,
        shooting_table=shooting_table,
        adj_shooting_table=adj_shooting_table,
        shooting_columns=shooting_columns,
        adj_shooting_columns=adj_shooting_columns,
        raw_metric_options=raw_metric_options,
        adjusted_metric_options=adjusted_metric_options,
        raw_default_metrics=raw_default_metrics,
        adjusted_default_metrics=adjusted_default_metrics,
        stats_metrics=stats_metrics,
        recent_form_chart_json=recent_form_chart_json,
        recent_form_table=recent_form_table,
        recent_form_columns=recent_form_columns
    )


@views.route('/prediction', methods=['GET', 'POST'])
@login_required
def prediction():
    form = PredictionForm()
    prediction_result = None
    player_stats = None

    if form.validate_on_submit():
        client = Client("aggtamv/nba_plusminus")

        # If user uploaded a CSV
        if form.file.data:
            file = form.file.data
            filename = secure_filename(file.filename)
            filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
            file.save(filepath)

            uploaded_stats = pd.read_csv(filepath)
            if set(PREDICTION_INFERENCE_COLUMNS).issubset(uploaded_stats.columns):
                clean_prediction_input(uploaded_stats, PREDICTION_INFERENCE_COLUMNS).to_csv(filepath, index=False)

            try:
                prediction_result = client.predict(file=handle_file(filepath), api_name="/predict_from_csv")
            except Exception as e:
                return f"Error during prediction: {e}", 500

        # If user selected a player name
        elif form.player_name.data:
            player_name = form.player_name.data.strip()
            print(f"Player name provided: {player_name}")

            try:
                filtered_stats, inference_cols = get_recent_prediction_stats_for_player(player_name)

                print(f"Filtered player stats:\n{filtered_stats}")

                # Save to temp CSV for Gradio
                temp_path = os.path.join(Config.UPLOAD_FOLDER, f"{player_name}_temp.csv")
                filtered_stats.to_csv(temp_path, index=False)

                prediction_result = client.predict(file=handle_file(temp_path), api_name="/predict_from_csv")
                print(f"Prediction result for {player_name}: {prediction_result}")

                player_stats = filtered_stats  # so you can show in template

            except Exception as e:
                return f"Error during prediction: {e}", 500

    has_player_stats = player_stats is not None and not player_stats.empty
    return render_template(
        'prediction.html',
        form=form,
        prediction=prediction_result,
        player_stats=player_stats,
        has_player_stats=has_player_stats,
    )


    has_player_stats = not player_stats.empty if player_stats is not None else False
    return render_template(
        'prediction.html',
        form=form,
        prediction=prediction_result,
        player_stats=player_stats,
        has_player_stats=has_player_stats,
    )

@views.route('/api/players/search', methods=['GET'])
@login_required
def search_players():
    query = request.args.get('q', '')
    try:
        players = search_prediction_player_names(query)
        return jsonify({"players": players})
    except Exception as e:
        current_app.logger.exception("Failed to search players")
        return jsonify({"players": [], "error": str(e)}), 500

@views.route('/generate_random_input', methods=['GET'])
def generate_random_input():
    client = Client("aggtamv/nba_plusminus")
    try:
        result = client.predict(api_name="/generate_random_input")
        # Assuming the result is JSON serializable dict or list
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def get_all_player_names(df):
    import pandas as pd
    df['Player'] = df['firstName'] + ' ' + df['lastName']
    player_names = sorted(df['Player'].unique())
    return player_names
