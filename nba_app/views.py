from flask import Blueprint, render_template, render_template, request, jsonify, flash, redirect, url_for, session, current_app, send_file
from flask_login import login_required, current_user
from backend.data_scraper import daily_matchups, get_csv, create_sample, get_shooting_avg
import logging
import os
from gradio_client import Client, handle_file
import pandas as pd
from werkzeug.utils import secure_filename
from .config import Config
from .forms import UploadForm, PredictionForm
import plotly.express as px
import plotly
import json

views = Blueprint("views", __name__)

@views.route("/home")
@views.route("/")
@login_required
def home():
    nba_games = get_csv('games', 'daily_games')
    nba_boxscores = get_csv('boxscores', 'daily_games')
    print(nba_games)
    if nba_games.empty and nba_boxscores.empty:
        nba_games, nba_boxscores = daily_matchups()
        
    nba_games.rename(columns={'0': 'team', '1': 'score', '2': 'state'}, inplace=True)
    nba_boxscores.rename(columns={'Unnamed: 0': 'team', '1': 'Q1', '2': 'Q2', '3': 'Q3', '4':'Q4'}, inplace=True)
    games_list = nba_games.to_dict(orient='records')
    boxscores_list = nba_boxscores.to_dict(orient='records')
    print("the games list:", games_list)
    """print("🎯 Games list:", games_list)
    print("🎯 Boxscores list:", boxscores_list)"""

    total_stats = get_csv('players_data', 'totals')
    total_stats_dict = total_stats.to_dict(orient='records')

    
    
    return render_template('index.html', nba_games = games_list, nba_boxscores=boxscores_list, total_stats=total_stats_dict,)

@views.route('/stats')
@login_required
def stats():
    try:
        shooting_avg = pd.read_csv('data/shooting/shooting_avg.csv')
        adj_shooting_avg = pd.read_csv('data/adj_shooting/adj_shooting_avg.csv')
        
        # If empty, regenerate
        if shooting_avg.empty or adj_shooting_avg.empty:
            get_shooting_avg()
            shooting_avg = pd.read_csv('data/shooting/shooting_avg.csv')
            adj_shooting_avg = pd.read_csv('data/adj_shooting/adj_shooting_avg.csv')
        
        # Convert to long format for Plotly line plot
        long_shooting = shooting_avg.melt(id_vars='Year', var_name='Stat', value_name='Average')
        long_adj_shooting = adj_shooting_avg.melt(id_vars='Year', var_name='Stat', value_name='Average')

        # Create Plotly line figures WITHOUT fig.show()
        fig1 = px.line(long_shooting, x="Year", y="Average", color="Stat", title="Raw Shooting Averages Over Years")
        fig2 = px.line(long_adj_shooting, x="Year", y="Average", color="Stat", title="Adjusted Shooting Averages Over Years")

        # Serialize figures to JSON for rendering in template
        shooting_avg_json = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
        adj_shooting_avg_json = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)

    except Exception as e:
        print(f"Error loading shooting averages: {e}")
        shooting_avg_json = '{}'
        adj_shooting_avg_json = '{}'

    return render_template(
        'stats.html',
        shooting_avg_json=shooting_avg_json,
        adj_shooting_avg_json=adj_shooting_avg_json
    )


@views.route('/prediction', methods=['GET', 'POST'])
@login_required
def prediction():
    form = PredictionForm()
    prediction_result = None
    player_stats = None
    player_names = []

    # Load full player stats once to get all player names
    try:
        full_stats_df, inference_cols = create_sample('PlayerStatistics.csv', 'data/samples')
        player_names = sorted(full_stats_df['Player'].dropna().unique())
    except Exception as e:
        print(f"Error loading player names: {e}")

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
                # Filter by player name in full DataFrame
                filtered_stats = full_stats_df[full_stats_df['Player'].str.contains(player_name, case=False)]
                filtered_stats = filtered_stats[inference_cols]
                filtered_stats = filtered_stats.head(10)

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
        player_names=player_names
    )


    has_player_stats = not player_stats.empty if player_stats is not None else False
    return render_template(
        'prediction.html',
        form=form,
        prediction=prediction_result,
        player_stats=player_stats,
        has_player_stats=has_player_stats,
        player_names=player_names
    )

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