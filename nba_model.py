# -*- coding: utf-8 -*-
"""
Created on Fri May  2 09:16:56 2025

@author: bakel
"""

import pandas as pd
import numpy as np
import os
from itertools import combinations

current_directory = os.getcwd()


def get_df(selected_file=None):
    cwd = os.getcwd()
    select_dir = os.path.join(cwd, f'{selected_file}')

    # Get list of files in the directory
    files = [os.path.join(select_dir, f) for f in os.listdir(select_dir) if os.path.isfile(os.path.join(select_dir, f))]

    if not files:
        raise FileNotFoundError(f"No files found in directory: {select_dir}")

    # Sort files by modification time, newest last
    files.sort(key=os.path.getmtime)

    # Select the most recent file
    last_file = files[-1]
    print(last_file)
    # Read the CSV file into a DataFrame
    df = pd.read_csv(last_file)
    return df

df_2025 = get_df('per_game')
df_2025.drop(['Awards'], axis = 1, inplace = True)
df_2025.drop(735, inplace = True)

df_filter = df_2025[~df_2025['Team'].isin(['2TM', '3TM'])]

results = []
# Group by team
for team, group in df_filter.groupby('Team'):
    players = list(group.itertuples(index=False))
    
    # Generate all pairwise combinations of teammates
    for p1, p2 in combinations(players, 2):
        shared_minutes = (p1.MP * p2.MP) / (48 * 48)
        results.append({
            'Team': team,
            'Player A': p1.Player,
            'Player B': p2.Player,
            'MP A': p1.MP,
            'MP B': p2.MP,
            'Estimated Shared Minutes': round(shared_minutes, 2)
        })

# Convert results to DataFrame
shared_df = pd.DataFrame(results)


# Step 1: Filter shared_df to include only one direction (e.g., Player A perspective)
shared_wide = shared_df[['Player A', 'Player B', 'Estimated Shared Minutes']].copy()

# Step 2: Pivot the table: each teammate becomes a column
shared_pivot = shared_wide.pivot(index='Player A', columns='Player B', values='Estimated Shared Minutes')

# Step 3: Rename columns to indicate they're shared minutes
shared_pivot.columns = [f'SharedWith_{col}' for col in shared_pivot.columns]

# Step 4: Merge into df_2025
df_augmented = pd.merge(df_2025, shared_pivot, how='left', left_on='Player', right_index=True)













