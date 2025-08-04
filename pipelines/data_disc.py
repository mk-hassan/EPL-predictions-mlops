"""
Solving data inconsistancy:
This script fetches EPL match data from football-data.co.uk for the seasons from 2000 to 2025s,
and identifies common columns across all seasons.
It uses the requests library to download the data and pandas to process it.
"""

from io import BytesIO
from time import sleep

import pandas as pd
import requests
from tqdm import tqdm

response = requests.get("https://www.football-data.co.uk/mmz4281/2425/E0.csv", timeout=10)
df = pd.read_csv(BytesIO(response.content))
common_columns = set([col.strip().lower() for col in df.columns])

for year in tqdm(range(2000, 2024)):
    try:
        season = str(year)[-2:] + str(year + 1)[-2:]
        current_season_url = f"https://www.football-data.co.uk/mmz4281/{season}/E0.csv"

        response = requests.get(current_season_url, timeout=10)
        df = pd.read_csv(BytesIO(response.content))
        common_columns.intersection_update([col.strip().lower() for col in df.columns])
    except Exception as e:
        print(f"error: {year}, {e}")

    sleep(5)


print(common_columns)
