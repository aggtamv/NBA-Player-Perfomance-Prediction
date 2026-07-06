import logging
from urllib import response
import certifi
import requests
import pandas as pd
from io import StringIO
import os
import time
import threading
import re
from datetime import date, timedelta, datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

NBA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
}

TEAM_LOGOS = {
    "Atlanta Hawks": "Atlanta.svg",
    "Boston Celtics": "Boston.svg",
    "Brooklyn Nets": "Brooklyn.svg",
    "Charlotte Hornets": "charlotte-hornets.svg",
    "Chicago Bulls": "Chicago.svg",
    "Cleveland Cavaliers": "Cleveland.svg",
    "Dallas Mavericks": "Dallas.svg",
    "Denver Nuggets": "Denver.svg",
    "Detroit Pistons": "Detroit.svg",
    "Golden State Warriors": "Golden_State.svg",
    "Houston Rockets": "Houston.svg",
    "Indiana Pacers": "Indiana.svg",
    "LA Clippers": "LA_Clippers.svg",
    "Los Angeles Clippers": "LA_Clippers.svg",
    "Los Angeles Lakers": "LA_Lakers.svg",
    "Memphis Grizzlies": "Memphis.svg",
    "Miami Heat": "Miami.svg",
    "Milwaukee Bucks": "Milwaukee.svg",
    "Minnesota Timberwolves": "Minnesota.svg",
    "New Orleans Pelicans": "New_Orleans.svg",
    "New York Knicks": "New York.svg",
    "Oklahoma City Thunder": "Oklahoma_City.svg",
    "Orlando Magic": "Orlando.svg",
    "Philadelphia 76ers": "philidephia-ers.svg",
    "Phoenix Suns": "Phoenix.svg",
    "Portland Trail Blazers": "Portland.svg",
    "Sacramento Kings": "Sacramento.svg",
    "San Antonio Spurs": "San_Antonio.svg",
    "Toronto Raptors": "toronto-raptors.svg",
    "Utah Jazz": "Utah.svg",
    "Washington Wizards": "Washington.svg",
}

TEAM_LOGO_ALIASES = {
    "Atlanta": "Atlanta Hawks",
    "Boston": "Boston Celtics",
    "Brooklyn": "Brooklyn Nets",
    "Charlotte": "Charlotte Hornets",
    "Chicago": "Chicago Bulls",
    "Cleveland": "Cleveland Cavaliers",
    "Dallas": "Dallas Mavericks",
    "Denver": "Denver Nuggets",
    "Detroit": "Detroit Pistons",
    "Golden State": "Golden State Warriors",
    "Houston": "Houston Rockets",
    "Indiana": "Indiana Pacers",
    "LA Clippers": "LA Clippers",
    "L.A. Clippers": "LA Clippers",
    "LA Lakers": "Los Angeles Lakers",
    "L.A. Lakers": "Los Angeles Lakers",
    "Los Angeles Lakers": "Los Angeles Lakers",
    "Memphis": "Memphis Grizzlies",
    "Miami": "Miami Heat",
    "Milwaukee": "Milwaukee Bucks",
    "Minnesota": "Minnesota Timberwolves",
    "New Orleans": "New Orleans Pelicans",
    "New York": "New York Knicks",
    "Oklahoma City": "Oklahoma City Thunder",
    "Orlando": "Orlando Magic",
    "Philadelphia": "Philadelphia 76ers",
    "Phoenix": "Phoenix Suns",
    "Portland": "Portland Trail Blazers",
    "Sacramento": "Sacramento Kings",
    "San Antonio": "San Antonio Spurs",
    "Toronto": "Toronto Raptors",
    "Utah": "Utah Jazz",
    "Washington": "Washington Wizards",
}

def get_team_logo(team_name):
    full_team_name = TEAM_LOGO_ALIASES.get(team_name, team_name)
    return TEAM_LOGOS.get(full_team_name, "nba.svg")

MOJIBAKE_MARKERS = ("Ã", "Ä", "Å", "Â", "â") + tuple(chr(code) for code in range(0x80, 0xA0))

def repair_mojibake(value):
    if not isinstance(value, str) or not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value

    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value

def repair_dataframe_text(df):
    text_columns = df.select_dtypes(include=["object", "string"]).columns
    if len(text_columns) == 0:
        return df

    df = df.copy()
    for column in text_columns:
        df[column] = df[column].map(repair_mojibake)
    return df

_DAILY_REFRESH_LOCK = threading.Lock()
_DAILY_REFRESH_IN_PROGRESS = False

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
                nba_data = repair_dataframe_text(tables[0])

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
        headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers)     
        print(f"Request URL: {url}")
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Headers: {response.headers}")
        print(f"Response Content (first 500 chars): {response.text[:500]}")
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

def _format_game_date(game_date=None):
    if game_date is None:
        return date.today().isoformat()
    if isinstance(game_date, datetime):
        return game_date.date().isoformat()
    if isinstance(game_date, date):
        return game_date.isoformat()
    return str(game_date)

def _nba_get_json(url, params=None):
    verify_ssl = os.getenv("NBA_VERIFY_SSL", "false").lower() not in {"0", "false", "no"}
    response = requests.get(
        url,
        params=params,
        headers=NBA_HEADERS,
        timeout=30,
        verify=certifi.where() if verify_ssl else False,
    )
    response.raise_for_status()
    return response.json()

def _extract_scoreboard_games(scoreboard_response):
    if isinstance(scoreboard_response, dict):
        if "scoreboard" in scoreboard_response:
            return scoreboard_response.get("scoreboard", {}).get("games", [])
        if "games" in scoreboard_response:
            return scoreboard_response.get("games", [])
    return []

def _team_name(team):
    city = team.get("teamCity", "")
    name = team.get("teamName", "")
    return f"{city} {name}".strip()

def _period_score_map(team):
    scores = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    for period in team.get("periods", []) or []:
        number = int(period.get("period", 0) or 0)
        if number <= 0:
            continue
        if number <= 4:
            key = f"Q{number}"
        elif number == 5:
            key = "OT"
        else:
            key = f"{number - 4}OT"
        scores[key] = int(period.get("score", 0) or 0)
    return scores

def _team_score_row(game, team, opponent, side):
    team_name = _team_name(team)
    return {
        "game_id": game.get("gameId"),
        "game_code": game.get("gameCode"),
        "team": team_name,
        "team_tricode": team.get("teamTricode"),
        "opponent": _team_name(opponent),
        "home_away": side,
        "team_logo": get_team_logo(team_name),
        "score": int(team.get("score", 0) or 0),
        "state": game.get("gameStatusText", ""),
        "game_status": game.get("gameStatus"),
        "game_time_utc": game.get("gameTimeUTC"),
        "series_text": game.get("seriesText", ""),
    }

def _team_boxscore_row(game, team, opponent, side):
    row = _team_score_row(game, team, opponent, side)
    row.update(_period_score_map(team))
    team_stats = team.get("statistics") or {}
    for key, value in team_stats.items():
        if key not in row:
            row[key] = value
    return row

def _player_boxscore_rows(game, team, opponent, side):
    rows = []
    for player in team.get("players", []) or []:
        row = {
            "game_id": game.get("gameId"),
            "game_code": game.get("gameCode"),
            "team": _team_name(team),
            "team_tricode": team.get("teamTricode"),
            "opponent": _team_name(opponent),
            "home_away": side,
            "person_id": player.get("personId"),
            "player": player.get("name"),
            "first_name": player.get("firstName"),
            "family_name": player.get("familyName"),
            "jersey_num": player.get("jerseyNum"),
            "starter": player.get("starter"),
            "played": player.get("played"),
            "status": player.get("status"),
            "not_playing_reason": player.get("notPlayingReason"),
            "not_playing_description": player.get("notPlayingDescription"),
        }
        row.update(player.get("statistics") or {})
        rows.append(row)
    return rows

def fetch_nba_daily_boxscores(game_date=None, save=True):
    """
    Fetch NBA.com scores and boxscores for a specific date.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        games, team boxscores, player boxscores.
    """
    requested_game_date = _format_game_date(game_date) if game_date is not None else None
    scoreboard_url = "https://stats.nba.com/stats/scoreboardv3"
    live_scoreboard_url = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"

    if requested_game_date is None:
        scoreboard = _nba_get_json(live_scoreboard_url)
        game_date = scoreboard.get("scoreboard", {}).get("gameDate") or date.today().isoformat()
    else:
        game_date = requested_game_date
        try:
            scoreboard = _nba_get_json(
                scoreboard_url,
                params={"GameDate": game_date, "LeagueID": "00"},
            )
        except requests.RequestException as exc:
            print(f"stats.nba.com scoreboard failed: {exc}")
            scoreboard = _nba_get_json(live_scoreboard_url)
            cdn_game_date = scoreboard.get("scoreboard", {}).get("gameDate")
            if cdn_game_date != game_date:
                raise ValueError(
                    f"NBA live scoreboard is for {cdn_game_date}, not requested date {game_date}."
                ) from exc

    games = _extract_scoreboard_games(scoreboard)

    games_rows = []
    team_boxscore_rows = []
    player_boxscore_rows = []
    per_game_dir = os.path.join("data", "boxscores", game_date)

    for game in games:
        game_id = game.get("gameId")
        boxscore_game = game
        if game_id:
            boxscore_url = f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
            try:
                boxscore = _nba_get_json(boxscore_url)
                boxscore_game = boxscore.get("game", game)
            except requests.RequestException as exc:
                print(f"Failed to fetch boxscore for game {game_id}: {exc}")

        home = boxscore_game.get("homeTeam") or game.get("homeTeam") or {}
        away = boxscore_game.get("awayTeam") or game.get("awayTeam") or {}

        games_rows.append(_team_score_row(boxscore_game, away, home, "away"))
        games_rows.append(_team_score_row(boxscore_game, home, away, "home"))

        current_team_rows = [
            _team_boxscore_row(boxscore_game, away, home, "away"),
            _team_boxscore_row(boxscore_game, home, away, "home"),
        ]
        team_boxscore_rows.extend(current_team_rows)

        current_player_rows = []
        current_player_rows.extend(_player_boxscore_rows(boxscore_game, away, home, "away"))
        current_player_rows.extend(_player_boxscore_rows(boxscore_game, home, away, "home"))
        player_boxscore_rows.extend(current_player_rows)

        if save and game_id:
            os.makedirs(per_game_dir, exist_ok=True)
            pd.DataFrame(current_team_rows).to_csv(
                os.path.join(per_game_dir, f"{game_id}_team_boxscore.csv"),
                index=False,
                encoding="utf-8-sig",
            )
            pd.DataFrame(current_player_rows).to_csv(
                os.path.join(per_game_dir, f"{game_id}_player_boxscore.csv"),
                index=False,
                encoding="utf-8-sig",
            )

    games_df = pd.DataFrame(games_rows)
    team_boxscores_df = pd.DataFrame(team_boxscore_rows)
    player_boxscores_df = pd.DataFrame(player_boxscore_rows)

    if save:
        daily_dir = os.path.join("data", "daily_games")
        os.makedirs(per_game_dir, exist_ok=True)
        os.makedirs(daily_dir, exist_ok=True)
        games_df.to_csv(
            os.path.join(daily_dir, f"games_{game_date}.csv"),
            index=False,
            encoding="utf-8-sig",
        )
        team_boxscores_df.to_csv(
            os.path.join(daily_dir, f"boxscores_{game_date}.csv"),
            index=False,
            encoding="utf-8-sig",
        )
        player_boxscores_df.to_csv(
            os.path.join(per_game_dir, f"player_boxscores_{game_date}.csv"),
            index=False,
            encoding="utf-8-sig",
        )

    return games_df, team_boxscores_df, player_boxscores_df

def _daily_games_file_path(df_name, game_date=None):
    return os.path.join("data", "daily_games", f"{df_name}_{_format_game_date(game_date)}.csv")

def _csv_has_rows(file_path):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    try:
        return not pd.read_csv(file_path, encoding="utf-8-sig").empty
    except pd.errors.EmptyDataError:
        return False

def latest_cached_daily_games_date():
    daily_dir = os.path.join("data", "daily_games")
    if not os.path.isdir(daily_dir):
        return None

    game_dates = []
    for filename in os.listdir(daily_dir):
        match = re.match(r"games_(\d{4}-\d{2}-\d{2})\.csv$", filename)
        if match:
            game_dates.append(match.group(1))

    for game_date in sorted(game_dates, reverse=True):
        if daily_games_cache_ready(game_date):
            return game_date

    return None

def daily_games_cache_ready(game_date=None, max_age_days=7):
    if game_date is None:
        latest_game_date = latest_cached_daily_games_date()
        if latest_game_date is None:
            return False
        latest_date = datetime.strptime(latest_game_date, "%Y-%m-%d").date()
        return latest_date >= date.today() - timedelta(days=max_age_days)

    required_files = [
        _daily_games_file_path("games", game_date),
        _daily_games_file_path("boxscores", game_date),
    ]
    return all(_csv_has_rows(file_path) for file_path in required_files)

def fetch_latest_nba_daily_boxscores(start_date=None, lookback_days=30):
    current_date = date.today() if start_date is None else datetime.strptime(_format_game_date(start_date), "%Y-%m-%d").date()

    if start_date is None:
        try:
            games, team_boxscores, player_boxscores = fetch_nba_daily_boxscores()
            if not games.empty and not team_boxscores.empty:
                return games, team_boxscores, player_boxscores
        except Exception as exc:
            print(f"NBA live scoreboard failed: {exc}")

    for days_back in range(lookback_days + 1):
        game_date = current_date - timedelta(days=days_back)
        games, team_boxscores, player_boxscores = fetch_nba_daily_boxscores(game_date)
        if not games.empty and not team_boxscores.empty:
            return games, team_boxscores, player_boxscores

    latest_game_date = latest_cached_daily_games_date()
    if latest_game_date:
        return (
            get_csv("games", "daily_games", current_date=latest_game_date, allow_fallback=False),
            get_csv("boxscores", "daily_games", current_date=latest_game_date, allow_fallback=False),
            pd.DataFrame(),
        )

    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def refresh_daily_games_if_needed(game_date=None, force=False, background=True):
    """
    Refresh daily NBA games once per app process, optionally in the background.
    Returns True when a refresh was started or completed.
    """
    global _DAILY_REFRESH_IN_PROGRESS

    if not force and daily_games_cache_ready(game_date):
        return False

    with _DAILY_REFRESH_LOCK:
        if _DAILY_REFRESH_IN_PROGRESS:
            return False
        _DAILY_REFRESH_IN_PROGRESS = True

    def run_refresh():
        global _DAILY_REFRESH_IN_PROGRESS
        try:
            if game_date is None:
                get_basketball_reference_data()
            else:
                fetch_nba_daily_boxscores(game_date)
        except Exception as exc:
            print(f"Failed to refresh NBA daily games: {exc}")
        finally:
            with _DAILY_REFRESH_LOCK:
                _DAILY_REFRESH_IN_PROGRESS = False

    if background:
        thread = threading.Thread(target=run_refresh, daemon=True)
        thread.start()
    else:
        run_refresh()

    return True

def get_basketball_reference_data():
    try:
        # Setup headless Chrome
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')

        driver = webdriver.Chrome(options=options)
        driver.get("https://www.basketball-reference.com/boxscores/")
        html = driver.page_source
        driver.quit()

        # Extract all tables using pandas
        tables = pd.read_html(StringIO(html))

        # Use lists to collect all matching tables
        games_list = []
        boxscores_list = []
        games_df = pd.DataFrame()
        boxscores_df = pd.DataFrame()
        
        print(tables)
        for table in tables:
            if table.shape == (2, 3) and table.iloc[0, 2] == 'Final':
                # Format and append this game
                game = table.copy()
                game.columns = ['team', 'score', 'state']
                game['score'] = pd.to_numeric(game['score'], errors='coerce').fillna(0).astype(int)
                game['state'] = game['state'].fillna("")
                game['team_logo'] = game['team'].map(get_team_logo)
                games_df = pd.concat([games_df, game], ignore_index=True)
                games_list.extend(game.to_dict(orient='records'))
                
            elif table.shape[0] == 2 and table.shape[1] >= 5:  # Changed this line!
                # Format and append this boxscore (handles OT games too)
                boxscore = table.copy()
                
                # Dynamically get all quarter columns
                col_names = ['team'] + [f'Q{i}' if i <= 4 else table.columns[i] 
                                        for i in range(1, len(table.columns))]
                boxscore.columns = col_names
                
                # Convert all numeric columns
                for col in boxscore.columns[1:]:
                    boxscore[col] = pd.to_numeric(boxscore[col], errors='coerce').fillna(0).astype(int)
                    
                boxscores_df = pd.concat([boxscores_df, boxscore], ignore_index=True)
                boxscores_list.extend(boxscore.to_dict(orient='records'))

        if not games_df.empty and not boxscores_df.empty:
            current_date = date.today().isoformat()
            parent_folder = os.path.join('data', 'daily_games')
            os.makedirs(parent_folder, exist_ok=True)
            games_df.to_csv(
                os.path.join(parent_folder, f'games_{current_date}.csv'),
                encoding='utf-8-sig',
                index=False
            )
            boxscores_df.to_csv(
                os.path.join(parent_folder, f'boxscores_{current_date}.csv'),
                encoding='utf-8-sig',
                index=False
            )

        return games_list, boxscores_list

    except Exception as e:
        print(f"❌ Error scraping Basketball Reference: {e}")
        return [], []

def get_csv(df_name, folder, current_date=None, allow_fallback=True):
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
    if allow_fallback and not os.path.exists(file_path):
        prefix = f'{df_name.rsplit("_", 1)[0]}_'
        if os.path.isdir(parent_folder):
            files = [
                os.path.join(parent_folder, f)
                for f in os.listdir(parent_folder)
                if f.startswith(prefix) and f.endswith('.csv')
            ]
            if files:
                file_path = max(files, key=os.path.getmtime)
                print(f"Using latest available file: {file_path}")

    if os.path.exists(file_path):
        print("Loading data from saved CSVs")
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
        df = repair_dataframe_text(df)
        
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
        df = repair_dataframe_text(df)

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
    message = get_basketball_reference_data()
    print(message)
