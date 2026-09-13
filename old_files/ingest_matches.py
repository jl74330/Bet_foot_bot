
import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# ============================================================
# CONFIGURATION
# ============================================================

# Récupère le dossier où se trouve le script actuel (ex: /job ou /app)
BASE_DIR = os.path.dirname(__file__)

# Chargement dynamique des deux fichiers d'environnement
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, "request-API", "keyapi.env"))

API_KEY = os.getenv("API_KEY")

BASE_URL = "https://api.football-data.org/v4"

CURRENT_SEASON = 2026

LEAGUES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
}

HEADERS = {
    "X-Auth-Token": API_KEY,
}


# ============================================================
# DATABASE
# ============================================================

DB_URL = (
    f"postgresql://"
    f"{os.getenv('POSTGRES_USER')}:"
    f"{os.getenv('POSTGRES_PASSWORD')}@"
    f"{os.getenv('POSTGRES_HOST')}:"
    f"{os.getenv('POSTGRES_PORT')}/"
    f"{os.getenv('POSTGRES_DB')}"
)

engine = create_engine(DB_URL)


# ============================================================
# API
# ============================================================

def fetch_matches(league_code):
    """
    Retrieve scheduled and finished matches for the current season.

    We use two API calls because football-data.org exposes
    match status as a filter.
    """

    statuses = [
        "SCHEDULED",
        "FINISHED",
    ]

    all_matches = []

    for status in statuses:
        url = (
            f"{BASE_URL}/competitions/"
            f"{league_code}/matches"
        )

        params = {
            "season": CURRENT_SEASON,
            "status": status,
        }

        print(
            f"Fetching {LEAGUES[league_code]} "
            f"({status})..."
        )

        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        matches = data.get("matches", [])

        print(f"  → {len(matches)} matches")

        all_matches.extend(matches)

    return all_matches


# ============================================================
# TRANSFORMATION
# ============================================================

def transform_match(match, league_code):
    """
    Transform football-data.org match format
    into the PostgreSQL matches format.
    """

    status = match.get("status")

    utc_date = match.get("utcDate")

    if not utc_date:
        raise ValueError(
            f"Missing utcDate for match {match.get('id')}"
        )

    # football-data.org returns ISO 8601 dates.
    match_date = datetime.fromisoformat(
        utc_date.replace("Z", "+00:00")
    ).replace(tzinfo=None)

    score = match.get("score", {})
    full_time = score.get("fullTime", {})

    home_score = full_time.get("home")
    away_score = full_time.get("away")

    # Scheduled matches must not be represented as 0-0.
    # NULL means that the match has not been played yet.
    if status != "FINISHED":
        home_score = None
        away_score = None

    return {
        "football_data_id": match["id"],
        "league": LEAGUES[league_code],
        "season": CURRENT_SEASON,
        "date": match_date,
        "home_team": match["homeTeam"]["name"],
        "away_team": match["awayTeam"]["name"],
        "home_score": home_score,
        "away_score": away_score,
    }


# ============================================================
# UPSERT
# ============================================================

UPSERT_SQL = text(
    """
    INSERT INTO matches (
        football_data_id,
        league,
        season,
        date,
        home_team,
        away_team,
        home_score,
        away_score,
        updated_at
    )
    VALUES (
        :football_data_id,
        :league,
        :season,
        :date,
        :home_team,
        :away_team,
        :home_score,
        :away_score,
        CURRENT_TIMESTAMP
    )

    ON CONFLICT (football_data_id)
    DO UPDATE SET
        league = EXCLUDED.league,
        season = EXCLUDED.season,
        date = EXCLUDED.date,
        home_team = EXCLUDED.home_team,
        away_team = EXCLUDED.away_team,
        home_score = EXCLUDED.home_score,
        away_score = EXCLUDED.away_score,
        updated_at = CURRENT_TIMESTAMP
    """
)


def save_matches(matches):
    """
    Insert new matches or update existing matches.
    """

    inserted_or_updated = 0

    with engine.begin() as connection:
        for match in matches:
            connection.execute(
                UPSERT_SQL,
                match,
            )

            inserted_or_updated += 1

    return inserted_or_updated


# ============================================================
# MAIN
# ============================================================

def main():

    if not API_KEY:
        raise RuntimeError(
            "API_KEY is not defined."
        )

    print("=" * 60)
    print("FOOTBALL DATA INGESTION")
    print("=" * 60)

    print(f"Season: {CURRENT_SEASON}")
    print(
        f"Leagues: {', '.join(LEAGUES.values())}"
    )
    print()

    total_matches = 0

    for league_code in LEAGUES:

        try:
            raw_matches = fetch_matches(
                league_code
            )

            transformed_matches = []

            for match in raw_matches:
                try:
                    transformed = transform_match(
                        match,
                        league_code,
                    )

                    transformed_matches.append(
                        transformed
                    )

                except (KeyError, ValueError) as error:
                    print(
                        f"WARNING: unable to transform "
                        f"match {match.get('id')}: {error}"
                    )

            # football-data.org can theoretically return
            # the same match in different status queries.
            unique_matches = {
                match["football_data_id"]: match
                for match in transformed_matches
            }

            transformed_matches = list(
                unique_matches.values()
            )

            count = save_matches(
                transformed_matches
            )

            total_matches += count

            print(
                f"{LEAGUES[league_code]}: "
                f"{count} matches inserted/updated"
            )
            print()

        except requests.RequestException as error:
            print(
                f"ERROR fetching "
                f"{LEAGUES[league_code]}: {error}"
            )

    print("=" * 60)
    print(
        f"TOTAL: {total_matches} matches "
        f"inserted/updated"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
```
