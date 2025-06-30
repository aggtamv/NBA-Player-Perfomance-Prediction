import logging
import requests
import pandas as pd
from io import StringIO
import os
import time
from datetime import date, timedelta, datetime


def player_stats(choice: list = None):
    try:
        type_list = ['totals', 'per_game', 'per_minute', 'per_poss', 'advanced', 'play-by-play', 'shooting', 'adj_shooting']
        if choice:
            type_list = choice
        for i in range(2025, 2026, 1):
            for stats_type in type_list:
                year = i
                url = f'https://www.basketball-reference.com/leagues/NBA_{year}_{stats_type}.html'  # Change to the specific target URL
                response = requests.get(url)
                print("--URL--", url)
                # Check if request was successful
                if response.status_code != 200:
                    print(response)
                    
                    return f'Failed to retrieve data while scraping for {stats_type}-{year}'
                
                html_content = StringIO(response.text)
                try:
                    tables = pd.read_html(html_content)
                except ValueError:
                    print(f"No table found for {year} - {stats_type}")
                    continue

                if not tables:
                    print(f"No tables parsed for {year} - {stats_type}")
                    continue
                
                # First tables is players data
                nba_data = tables[0]

                # If the DataFrame is empty, skip it
                if nba_data.empty:
                    print(f"Empty DataFrame for {year} - {stats_type}, skipping...")
                    continue
                
                df_name = f'players_data_{year}.csv'
                parent_folder = f'data/{stats_type}'
                file_path = os.path.join(parent_folder, df_name)
                os.makedirs(parent_folder, exist_ok=True)

                nba_data.to_csv(file_path, encoding='utf-8-sig', index=False) #Save without the index column
                print(f"✅ Data successfully saved to '{file_path}'")
                # Optionally, store data into an external database, or return data for display
                print(f'Success scraping year {year}')

                # Wait 10 seconds between requests so wont get limit
                time.sleep(10)
        
        return "✅ Finished scraping all data."
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def daily_matchups():
    try:
        current_date = date.today() 
        day = current_date.day
        month = current_date.month
        year = current_date.year
        url = f'https://www.basketball-reference.com/boxscores/'
        response = requests.get(url)
                
        # Check if request was successful
        if response.status_code != 200:
            print(response)
            return f'Failed to retrieve data.'
        
        html_content = StringIO(response.text)
        tables = pd.read_html(html_content)
        nba_games = pd.DataFrame()
        nba_boxscores = pd.DataFrame()
        for table in tables:
        # First table is games data
            if table.shape == (2,3) and table.iloc[0, 2] == 'Final':
                nba_games = pd.concat([nba_games, table])
            if  table.shape == (2,5):
                nba_boxscores = pd.concat([nba_boxscores, table])
        df_name = f'games_{current_date}.csv'
        df_boxscores = f'boxscores_{current_date}.csv'
        parent_folder = f'./data/daily_games'
        file_path = os.path.join(parent_folder, df_name)
        file_path_boxscores = os.path.join(parent_folder, df_boxscores)
        os.makedirs(parent_folder, exist_ok=True)

        nba_games.to_csv(file_path, encoding='utf-8', index=False) #Save without the index column
        nba_boxscores.to_csv(file_path_boxscores,encoding='utf-8', index=False)
        print(f"✅ Data successfully saved to '{file_path, file_path_boxscores}'")
        return nba_games, nba_boxscores
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def get_csv(df_name, folder, current_date=None):
    from datetime import date, timedelta

    if current_date is None:
        if folder != 'daily_games':
            current_date = date.today().year
        elif folder == 'daily_games':
            current_date = date.today()

    df_name = f'{df_name}_{current_date}.csv'
    parent_folder = f'data/{folder}'
    file_path = os.path.join(parent_folder, df_name)
    # Try loading the saved CSVs
    if os.path.exists(file_path):
        print("Loading data from saved CSVs")
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        
        if folder == 'totals':
            df = df[df['Player'] != 'League Average']
            df.drop('Awards', axis=1, inplace = True)
        return df
    else:
        print(f"❌ File not found: {file_path}")
        return pd.DataFrame()
    
def game_stats(season: str = "2024-25", season_type: str = "Regular Season"):
    assert season_type in ["Regular Season", "Playoffs"], "season_type must be 'Regular Season' or 'Playoffs'"
    all_games_df = pd.DataFrame() #Initialize an empty DataFrame to store all games data
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "x-nba-stats-origin": "stats",
            "Referer": "https://www.nba.com/",
            "Accept": "application/json, text/plain, */*",
            }
        

        # 1st) Retrieve game ids for a specific season
        
        all_season_url = (
            f"https://stats.nba.com/stats/leaguegamefinder?"
            f"LeagueID=00&Season={season}&SeasonType={season_type.replace(' ', '+')}"
            )
        # 2nd) Get the game ids from the response
        games_response = requests.get(all_season_url, headers=headers)
        data = games_response.json()
        print("Games response:", games_response)
        games = data["resultSets"][0]
        df_games = pd.DataFrame(games["rowSet"], columns=games["headers"])
        game_ids = df_games["GAME_ID"].unique().tolist()
        print("Game IDs:", game_ids)
        if not game_ids:
            return "No games found for the specified season and type."
        logging.info(f"Found {len(game_ids)} game ids.")
        # 3rd) Get the first game id
        
        for game_id in game_ids:
            if game_id:  
                url = f"https://stats.nba.com/stats/boxscoretraditionalv2?GameID={game_id}&StartPeriod=0&EndPeriod=0&StartRange=0&EndRange=0&RangeType=0"
                resp = requests.get(url, headers=headers)
                data = resp.json()
                player_stats = data["resultSets"][0]  # "PlayerStats"
                df_players = pd.DataFrame(player_stats["rowSet"], columns=player_stats["headers"])
                print("Player stats:", df_players)
                temp_games = data["resultSets"][0] # "GamesStats"
                print("Games stats:", temp_games)
                if not df_players.empty:
                    logging.info(f"🏀 Game ID: {game_id}")
                    logging.info("Players Box Score:")
                    logging.info(df_players.head())
                    # Team stats
                    team_stats = data["resultSets"][1]  # "TeamStats"
                    df_teams = pd.DataFrame(team_stats["rowSet"], columns=team_stats["headers"])

                    # Get unique teams
                    teams = df_players["TEAM_ABBREVIATION"].unique()
                    if len(teams) < 2:
                        logging.warning(f"Not enough teams found for game ID {game_id}. Skipping...")
                        continue
                    df_home = df_players[df_players["TEAM_ABBREVIATION"] == teams[0]]
                    df_away = df_players[df_players["TEAM_ABBREVIATION"] == teams[1]]

                    # Add game_stats to the DataFrame
                    all_games_df = pd.concat([all_games_df, df_home], ignore_index=True)
                    all_games_df = pd.concat([all_games_df, df_away], ignore_index=True)
                    time.sleep(2)  # Sleep to avoid hitting the API too fast
                    logging.info(f"✅ Game stats saved for game ID {game_id}")
                else:
                    logging.warning(f"No player stats found for game ID {game_id}. Skipping...")
            else:
                logging.warning("Empty game ID found. Skipping...") 
        all_games_df.to_csv(f'data/game_stats/game_stats_{season}.csv', index=False)
    except Exception as e:
        logging.error(f"❌ Error occurred: {e}")
    
    return all_games_df

def create_sample(df_name: str = 'PlayerStatistics', folder: str = 'data/samples'):
    """
    Load a sample CSV from the /data directory, which is one level above the backend folder.
    """
    if not df_name.endswith('.csv'):
        df_name += '.csv'

    # Step 1: Get the current file's directory (e.g., backend/)
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Step 2: Go up to the project root and into /data/
    project_root = os.path.abspath(os.path.join(current_dir, '..'))
    file_path = os.path.join(project_root, folder, df_name)

    print(f"🔍 Looking for file at: {file_path}")

    if os.path.exists(file_path):
        print("✅ File found, loading...")
        df = pd.read_csv(file_path, encoding='utf-8-sig', low_memory=False)

        # Define your inference columns
        inference_cols = [
            'numMinutes', 'points', 'assists', 'blocks', 'steals',
            'fieldGoalsAttempted', 'fieldGoalsMade', 'fieldGoalsPercentage',
            'threePointersAttempted', 'threePointersMade', 'threePointersPercentage',
            'freeThrowsAttempted', 'freeThrowsMade', 'freeThrowsPercentage',
            'reboundsDefensive', 'reboundsOffensive', 'reboundsTotal',
            'foulsPersonal', 'turnovers', 'plusMinusPoints'
        ]

        # Example cleanup
        df['Player'] = df['firstName'] + ' ' + df['lastName']
        df.drop(columns=['firstName', 'lastName'], inplace=True)

        return df, inference_cols
    else:
        print(f"❌ File not found: {file_path}")
        return None, None
    
import os
import pandas as pd

def get_shooting_avg():
    try:
        folder_names = ['adj_shooting', 'shooting']
        parent_folder = 'data'
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..'))

        for folder in folder_names:
            file_path = os.path.join(project_root, parent_folder, folder)
            if not os.path.exists(file_path):
                print(f"Path does not exist: {file_path}")
                continue

            all_dfs = []
            year = 2000

            for fname in sorted(os.listdir(file_path)):
                if not fname.endswith('.csv') or not fname.startswith('players_data_'):
                    continue

                try:
                    df = pd.read_csv(os.path.join(file_path, fname), header=[0, 1])
                    df.columns = ['_'.join(filter(None, col)).strip() for col in df.columns.values]

                    if folder == 'adj_shooting':
                        rename_map = {
                            'Shooting %_FG%': 'FG%',
                            'Shooting %_2P%': '2P%',
                            'Shooting %_3P%': '3P%',
                            'Shooting %_eFG%': 'eFG%',
                            'Shooting %_FT%': 'FT%',
                            'Shooting %_TS%': 'TS%',
                            'Shooting %_FTr': 'FTr',
                            'Shooting %_3PAr': '3PAr',
                            'League-Adjusted_FG+': 'FG+',
                            'League-Adjusted_2P+': '2P+',
                            'League-Adjusted_3P+': '3P+',
                            'League-Adjusted_eFG+': 'eFG+',
                            'League-Adjusted_FT+': 'FT+',
                            'League-Adjusted_TS+': 'TS+',
                            'League-Adjusted_FTr+': 'FTr+',
                            'League-Adjusted_3PAr+': '3PAr+',
                            'Added_FG Add': 'FG Add',
                            'Added_TS Add': 'TS Add',
                        }

                        df.rename(columns=rename_map, inplace=True)
                        selected_cols = list(rename_map.values())
                    else:
                        # shooting: raw shooting stats
                        rename_map = {
                            '% of FGA by Distance_0-3': 'FGA_0_3',
                            '% of FGA by Distance_3-10': 'FGA_3_10',
                            '% of FGA by Distance_10-16': 'FGA_10_16',
                            '% of FGA by Distance_16-3P': 'FGA_16_3P',
                            '% of FGA by Distance_3P': 'FGA_3P',
                            'FG% by Distance_0-3': 'FG_0_3',
                            'FG% by Distance_3-10': 'FG_3_10',
                            'FG% by Distance_10-16': 'FG_10_16',
                            'FG% by Distance_16-3P': 'FG_16_3P',
                            'FG% by Distance_3P': 'FG_3P',
                            'FG%': 'FG%',
                            '2P': '2P%',
                            '3P': '3P%',
                            'Dist.': 'Dist',
                            'TS%': 'TS%',
                            'eFG%': 'eFG%',
                            'FTr': 'FTr',
                            '3PAr': '3PAr'
                        }

                        df.rename(columns=rename_map, inplace=True)
                        selected_cols = list(rename_map.values())

                    # Filter only if all selected columns exist
                    df = df[[col for col in selected_cols if col in df.columns]]
                    df = df.apply(pd.to_numeric, errors='coerce')
                    df.dropna(inplace=True)

                    df['Year'] = year
                    all_dfs.append(df)
                    year += 1

                except Exception as file_err:
                    print(f"Error processing file {fname}: {file_err}")

            final_df = pd.concat(all_dfs, ignore_index=True)
            # Group by year and compute mean of all stats
            yearly_avg = final_df.groupby('Year').mean(numeric_only=True).reset_index()

            # Save the yearly averages
            out_path = os.path.join(file_path, f"{folder}_avg.csv")
            yearly_avg.to_csv(out_path, index=False)
            print(f"Saved yearly average to: {out_path}")


    except Exception as e:
        print(f"Error in get_shooting_avg: {e}")

    
# To execute locally
if __name__ == "__main__":
    #message = player_stats(['totals'])
    message = get_shooting_avg()
    print(message)