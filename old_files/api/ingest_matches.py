import requests
import os
import time
import pandas  as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from datetime import datetime


load_dotenv('../.env')
load_dotenv('../request-API/keyapi.env')

# Variables
API_KEY = os.getenv("API_KEY")
BASE_URL = "https://api.football-data.org/v4/"

headers = {"X-Auth-Token": API_KEY}


DB_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
engine = create_engine(DB_URL)

REQUIRED_MATCH_COLUMNS = {
    "season": "INTEGER",
    "home_score": "INTEGER",
    "away_score": "INTEGER",
    "home_win_pct": "DOUBLE PRECISION",
    "away_win_pct": "DOUBLE PRECISION",
    "draw_pct": "DOUBLE PRECISION",
    "avg_goals_home": "DOUBLE PRECISION",
    "avg_goals_away": "DOUBLE PRECISION",
}

def ensure_matches_schema(engine):
    inspector = inspect(engine)
    if not inspector.has_table("matches"):
        return

    with engine.begin() as conn:
        existing_columns = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='matches'"
                )
            )
        }

        if "match_date" in existing_columns and "date" not in existing_columns:
            conn.execute(text("ALTER TABLE matches ADD COLUMN IF NOT EXISTS date TIMESTAMP"))
            conn.execute(text("UPDATE matches SET date = match_date"))

        for column_name, data_type in REQUIRED_MATCH_COLUMNS.items():
            if column_name not in existing_columns:
                conn.execute(
                    text(
                        f"ALTER TABLE matches ADD COLUMN IF NOT EXISTS {column_name} {data_type}"
                    )
                )

# Ligues
LEAGUES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
#    "FL2": "Ligue 2"

}

# -----------------------------
# FETCH MATCHES
# -----------------------------
def fetch_upcoming_matches(league_code):
    url = f"{BASE_URL}/competitions/{league_code}/matches?status=SCHEDULED"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["matches"]


# -----------------------------
# TRANSFORM TO DF
# -----------------------------
def matches_to_df(matches, league):
    rows = []

    for m in matches:
        rows.append({
            "date": m["utcDate"],
            "league": league,
            "home_team": m["homeTeam"]["name"],
            "away_team": m["awayTeam"]["name"],
            "season": 2026,
            "home_score": 0,
            "away_score": 0,
            "home_win_pct": 0.0,
            "away_win_pct": 0.0,
            "draw_pct": 0.0,
            "avg_goals_home": 0.0,
            "avg_goals_away": 0.0
        })

    return pd.DataFrame(rows)


# -----------------------------
# AVOID DUPLICATES
# -----------------------------
def remove_existing(df):
    try:
        with engine.connect() as conn:
            existing = pd.read_sql(
                text("SELECT date, home_team, away_team FROM matches"),
                conn
            )
    except Exception:
        # Table doesn't exist, so all matches are new
        return df

    merged = df.merge(
        existing,
        on=["date", "home_team", "away_team"],
        how="left",
        indicator=True
    )

    return merged[merged["_merge"] == "left_only"].drop(columns="_merge")


# -----------------------------
# MAIN
# -----------------------------
def main():
    print("Fetching upcoming matches...")

    all_df = []

    for league in LEAGUES:
        matches = fetch_upcoming_matches(league)
        df = matches_to_df(matches, league)
        all_df.append(df)

    full_df = pd.concat(all_df, ignore_index=True)

    print(f"Fetched {len(full_df)} matches")

    new_df = remove_existing(full_df)

    if new_df.empty:
        print("No new matches to insert")
        return

    ensure_matches_schema(engine)
#    new_df.to_sql("matches", engine, if_exists="replace", index=False)
    new_df.to_sql("matches", engine, if_exists="append", index=False)

    print(f"Inserted {len(new_df)} new matches")


if __name__ == "__main__":
    main()