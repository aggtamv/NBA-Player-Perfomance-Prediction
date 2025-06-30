import requests
import pandas as pd
from io import StringIO
import os
import time


def player_stats():
    try:
        type_list = ['totals', 'per_game', 'per_minute', 'per_poss', 'advanced', 'play-by-play', 'shooting', 'adj_shooting']
        for i in range(2000, 2025, 1):
            for stats_type in type_list:
                year = i
                url = f'https://www.basketball-reference.com/leagues/NBA_{year}_{stats_type}.html'  # Change to the specific URL you're targeting
                response = requests.get(url)
                
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

                nba_data.to_csv(file_path, index=False) #Save without the index column
                print(f"✅ Data successfully saved to '{file_path}'")
                # Optionally, store data into an external database, or return data for display
                print(f'Success scraping year {year}')

                # Wait 10 seconds between requests so wont get limit
                time.sleep(10)
        
        return "✅ Finished scraping all data."
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# To execute locally
if __name__ == "__main__":
    message = player_stats()
    print(message)