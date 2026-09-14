#!/usr/bin/env python3

"""
Ingest football fixtures/results from football-data.org into PostgreSQL.

Examples:
    python ingest_matches.py --season 2022
    python ingest_matches.py --season 2023
    python ingest_matches.py --season 2024
    python ingest_matches.py --season 2026

The season is selected with --season and is never hard-coded.

Scheduled matches are stored with NULL scores.
Finished matches are inserted/updated with their real scores.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# ---------------------------------------------------------------------------
# Paths / environment
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "request-API" / "keyapi.env")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://api.football-data.org/v4"

LEAGUES = {
    "FL1": "Ligue 1",
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "PPL": "Primeira Liga",
}

DEFAULT_SEASON = int(os.getenv("FOOTBALL_SEASON", "2023"))

REQUEST_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("API_RETRY_DELAY", "5"))

API_KEY = os.getenv("API_KEY")

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Ingest football matches from football-data.org."
    )

    parser.add_argument(
        "--season",
        type=int,
        default=DEFAULT_SEASON,
        help=f"Season to ingest, for example 2022 or 2026 "
             f"(default: {DEFAULT_SEASON}).",
    )

    return parser.parse_args()


def validate_environment():
    required = {
        "API_KEY": API_KEY,
        "POSTGRES_USER": POSTGRES_USER,
        "POSTGRES_PASSWORD": POSTGRES_PASSWORD,
        "POSTGRES_DB": POSTGRES_DB,
    }

    missing = [name for name, value in required.items() if not value]

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )


def build_engine():
    db_url = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

    return create_engine(
        db_url,
        pool_pre_ping=True,
    )


def parse_utc_datetime(value: str) -> datetime:
    """
    Convert API ISO-8601 UTC datetime to a naive UTC datetime.

    PostgreSQL matches.date is TIMESTAMP WITHOUT TIME ZONE.
    """
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)

    return parsed


def request_api(session, url, params):
    """GET API data with retry handling."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")

                if retry_after and retry_after.isdigit():
                    delay = int(retry_after)
                else:
                    delay = RETRY_DELAY

                print(
                    f"Rate limit reached. Waiting {delay}s "
                    f"(attempt {attempt}/{MAX_RETRIES})..."
                )

                time.sleep(delay)
                continue

            response.raise_for_status()
            return response.json()

        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"API request failed after {MAX_RETRIES} attempts: {exc}"
                ) from exc

            print(
                f"API request failed: {exc}. "
                f"Retrying in {RETRY_DELAY}s "
                f"(attempt {attempt}/{MAX_RETRIES})..."
            )

            time.sleep(RETRY_DELAY)

    raise RuntimeError("Unexpected API request failure.")


def fetch_matches(session, competition_code, season, status):
    """Fetch matches for a competition, season and status."""
    url = f"{BASE_URL}/competitions/{competition_code}/matches"

    params = {
        "season": season,
        "status": status,
    }

    data = request_api(session, url, params)

    return data.get("matches", [])


def match_to_row(match, league_name, season):
    """Convert an API match into the PostgreSQL matches format."""
    status = match.get("status")

    full_time = match.get("score", {}).get("fullTime", {})

    home_score = full_time.get("home")
    away_score = full_time.get("away")

    # Scheduled fixtures must not be represented as 0-0.
    if status not in {
        "FINISHED",
        "IN_PLAY",
        "PAUSED",
        "SUSPENDED",
    }:
        home_score = None
        away_score = None

    return {
        "football_data_id": match["id"],
        "league": league_name,
        "season": season,
        "date": parse_utc_datetime(match["utcDate"]),
        "home_team": match["homeTeam"]["name"],
        "away_team": match["awayTeam"]["name"],
        "home_score": home_score,
        "away_score": away_score,
    }


def upsert_matches(engine, rows):
    """
    Insert new matches or update existing matches.

    football_data_id is the unique source identifier, so running the
    ingestion repeatedly is safe.
    """
    if not rows:
        return 0

    sql = text(
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

    with engine.begin() as connection:
        connection.execute(sql, rows)

    return len(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    season = args.season

    validate_environment()
    engine = build_engine()

    session = requests.Session()
    session.headers.update(
        {
            "X-Auth-Token": API_KEY,
            "Accept": "application/json",
        }
    )

    total_fetched = 0
    total_upserted = 0

    print("=" * 60)
    print("Football matches ingestion")
    print("=" * 60)
    print(f"Season   : {season}")
    print(f"Leagues  : {', '.join(LEAGUES.values())}")
    print(
        f"Database : "
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    print()

    for competition_code, league_name in LEAGUES.items():
        print(f"[{competition_code}] {league_name}")

        league_rows = []

        for status in ("SCHEDULED", "FINISHED"):
            try:
                matches = fetch_matches(
                    session=session,
                    competition_code=competition_code,
                    season=season,
                    status=status,
                )

                print(f"  {status:<10}: {len(matches)} matches")

                rows = [
                    match_to_row(
                        match,
                        league_name,
                        season,
                    )
                    for match in matches
                ]

                league_rows.extend(rows)
                total_fetched += len(rows)

            except Exception as exc:
                print(
                    f"  ERROR while fetching {status}: {exc}",
                    file=sys.stderr,
                )

        if league_rows:
            # Protect against a match appearing in both API responses.
            unique_rows = {
                row["football_data_id"]: row
                for row in league_rows
            }

            upserted = upsert_matches(
                engine,
                list(unique_rows.values()),
            )

            total_upserted += upserted

            print(f"  Upserted   : {upserted}")

        print()

    print("=" * 60)
    print("Ingestion completed")
    print(f"Season   : {season}")
    print(f"Fetched  : {total_fetched}")
    print(f"Upserted : {total_upserted}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
