import requests
import os
import time
import pandas  as pd

from dotenv import load_dotenv

load_dotenv('keyapi.env')

API_KEY = os.getenv("API_KEY")

headers = {
    "X-Auth-Token": API_KEY
}

# Ligues
leagues = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "FL2": "Ligue 2",
    "BL1": "Bundesliga",
    "DED": "Eredivisie",
    "PPL": "Primeira Liga",
    "CL": "Champions League",
    "ELC": "Championship League"

}

# Saisons (année de début)
seasons = [2020, 2021, 2022, 2023, 2024, 2025]

all_matches = []

for league_code, league_name in leagues.items():
    print(f"\n📊 Fetching {league_name}...")

    for season in seasons:
        print(f"  → Season {season}")

        url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?season={season}"

        response = requests.get(url, headers=headers)
        data = response.json()

        matches = data.get("matches", [])

        for match in matches:
            all_matches.append({
                "league": league_name,
                "season": season,
                "date": match["utcDate"],
                "home_team": match["homeTeam"]["name"],
                "away_team": match["awayTeam"]["name"],
                "home_score": match["score"]["fullTime"]["home"],
                "away_score": match["score"]["fullTime"]["away"]
            })

        time.sleep(1)  # éviter rate limit

print(f"\n✅ Total matches collected: {len(all_matches)}")

#Transfoprme en dataframe

df = pd.DataFrame(all_matches)

print(df.head())

# sauvegarde en csv
df.to_csv("matches.csv", index=False)