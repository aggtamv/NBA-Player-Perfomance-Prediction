from flask import Blueprint, render_template, render_template, request, jsonify, flash, redirect, url_for, session, current_app, send_file
from flask_login import login_required, current_user
from backend.data_scraper import *
import logging
import os
from gradio_client import Client, handle_file
import pandas as pd
from werkzeug.utils import secure_filename
from .config import Config
from .forms import UploadForm, PredictionForm
from .stats_repository import (
    get_player_totals,
    get_recent_prediction_stats_for_player,
    get_shooting_averages,
    search_prediction_player_names,
)
import plotly.express as px
import plotly
import json

views = Blueprint("views", __name__)

@views.route("/home")
@views.route("/")
@login_required
def home():
    # Try to load today's CSV files first
    nba_games = get_csv('games', 'daily_games')
    nba_boxscores = get_csv('boxscores', 'daily_games')
    data_fetch_required = nba_games.empty and nba_boxscores.empty

    if not data_fetch_required:
        # If CSVs loaded successfully, format them
        nba_games.rename(columns={'0': 'team', '1': 'score', '2': 'state'}, inplace=True)
        nba_boxscores.rename(columns={'Unnamed: 0': 'team', '1': 'Q1', '2': 'Q2', '3': 'Q3', '4': 'Q4'}, inplace=True)

        nba_games['score'] = pd.to_numeric(nba_games['score'], errors='coerce').fillna(0).astype(int)
        if 'team_logo' not in nba_games.columns:
            nba_games['team_logo'] = nba_games['team'].map(TEAM_LOGOS).fillna('nba.svg')
        else:
            nba_games['team_logo'] = nba_games.apply(
                lambda row: row['team_logo'] if pd.notna(row['team_logo']) else TEAM_LOGOS.get(row['team'], 'nba.svg'),
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
        data_fetch_required=data_fetch_required
    )

@views.route('/api/daily-games/refresh', methods=['GET'])
@login_required
def refresh_daily_games():
    game_date = request.args.get('date')
    try:
        games, team_boxscores, player_boxscores = fetch_nba_daily_boxscores(game_date)
        return jsonify({
            "status": "ok",
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
    try:
        shooting_avg, adj_shooting_avg = get_shooting_averages()
        shooting_avg = shooting_avg.sort_values('Year')
        adj_shooting_avg = adj_shooting_avg.sort_values('Year')
        
        raw_metrics = ['FGA_0_3', 'FGA_3P', 'FG_0_3', 'FG_3P']
        adjusted_metrics = ['FG%', '3P%', 'eFG%', 'TS%', 'FTr', '3PAr']
        chart_colors = ['#17408b', '#c9082a', '#d9911b', '#15803d', '#6d28d9', '#0f766e']

        long_shooting = shooting_avg.melt(
            id_vars='Year',
            value_vars=[metric for metric in raw_metrics if metric in shooting_avg.columns],
            var_name='Metric',
            value_name='Average'
        )
        long_adj_shooting = adj_shooting_avg.melt(
            id_vars='Year',
            value_vars=[metric for metric in adjusted_metrics if metric in adj_shooting_avg.columns],
            var_name='Metric',
            value_name='Average'
        )

        fig1 = px.line(
            long_shooting,
            x="Year",
            y="Average",
            color="Metric",
            markers=True,
            color_discrete_sequence=chart_colors,
            title="Shot Profile and Finishing"
        )
        fig2 = px.line(
            long_adj_shooting,
            x="Year",
            y="Average",
            color="Metric",
            markers=True,
            color_discrete_sequence=chart_colors,
            title="Efficiency and Shot Mix"
        )

        for fig in (fig1, fig2):
            fig.update_layout(
                template='plotly_white',
                height=420,
                margin=dict(l=38, r=24, t=58, b=40),
                legend_title_text='',
                font=dict(family='Inter, Segoe UI, Arial', color='#111827'),
                paper_bgcolor='rgba(255,255,255,0)',
                plot_bgcolor='rgba(255,255,255,0.84)',
                hovermode='x unified',
            )
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(gridcolor='rgba(207, 218, 232, 0.7)')

        latest_raw = shooting_avg.iloc[-1].to_dict()
        latest_adjusted = adj_shooting_avg.iloc[-1].to_dict()
        first_adjusted = adj_shooting_avg.iloc[0].to_dict()
        latest_year = int(latest_adjusted.get('Year', latest_raw.get('Year', 0)))
        first_year = int(adj_shooting_avg.iloc[0]['Year'])

        stats_metrics = {
            "year_range": f"{first_year}-{latest_year}",
            "latest_year": latest_year,
            "latest_ts": latest_adjusted.get('TS%'),
            "latest_efg": latest_adjusted.get('eFG%'),
            "latest_3par": latest_adjusted.get('3PAr'),
            "three_point_rate_change": latest_adjusted.get('3PAr', 0) - first_adjusted.get('3PAr', 0),
        }

        shooting_avg_json = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
        adj_shooting_avg_json = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)
        shooting_table = shooting_avg.tail(10).sort_values('Year', ascending=False).round(3).to_dict(orient='records')
        adj_shooting_table = adj_shooting_avg.tail(10).sort_values('Year', ascending=False).round(3).to_dict(orient='records')
        shooting_columns = shooting_avg.columns.tolist()
        adj_shooting_columns = adj_shooting_avg.columns.tolist()

    except Exception as e:
        print(f"Error loading shooting averages: {e}")
        shooting_avg_json = '{}'
        adj_shooting_avg_json = '{}'
        shooting_table = []
        adj_shooting_table = []
        shooting_columns = []
        adj_shooting_columns = []
        stats_metrics = {
            "year_range": None,
            "latest_year": None,
            "latest_ts": None,
            "latest_efg": None,
            "latest_3par": None,
            "three_point_rate_change": None,
        }

    return render_template(
        'stats.html',
        shooting_avg_json=shooting_avg_json,
        adj_shooting_avg_json=adj_shooting_avg_json,
        shooting_table=shooting_table,
        adj_shooting_table=adj_shooting_table,
        shooting_columns=shooting_columns,
        adj_shooting_columns=adj_shooting_columns,
        stats_metrics=stats_metrics
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
