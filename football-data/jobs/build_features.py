import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Get database configuration
db_user = os.getenv('POSTGRES_USER')
db_password = os.getenv('POSTGRES_PASSWORD')
db_host = os.getenv('POSTGRES_HOST')
db_port = os.getenv('POSTGRES_PORT')
db_name = os.getenv('POSTGRES_DB')

if not all([db_user, db_password, db_host, db_port, db_name]):
    raise ValueError("Missing required database environment variables")

DB_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
engine = create_engine(DB_URL)


def compute_team_stats(team_name):
    query = f"""
        SELECT *
        FROM matches
        WHERE (home_team = '{team_name}' OR away_team = '{team_name}')
        AND date::timestamp < NOW()
    """
    df = pd.read_sql(query, engine)

    if df.empty:
        return 0, 0

    goals_scored = []
    wins = 0

    for _, row in df.iterrows():
        if row["home_team"] == team_name:
            goals_scored.append(row.get("home_score", 0))
            if row.get("home_score", 0) > row.get("away_score", 0):
                wins += 1
        else:
            goals_scored.append(row.get("away_score", 0))
            if row.get("away_score", 0) > row.get("home_score", 0):
                wins += 1

    avg_goals = sum(goals_scored) / len(goals_scored) if goals_scored else 0
    win_pct = wins / len(goals_scored) if goals_scored else 0

    return avg_goals, win_pct


def main():
    print("Building features for upcoming matches...")

    upcoming = pd.read_sql("""
        SELECT id, home_team, away_team, date
        FROM matches
        WHERE date::timestamp > NOW()
    """, engine)

    print(f"Found {len(upcoming)} upcoming matches")

    for _, row in upcoming.iterrows():
        home_avg, home_win = compute_team_stats(row["home_team"])
        away_avg, away_win = compute_team_stats(row["away_team"])

        draw_pct = 1 - (home_win + away_win) / 2

        print(f"Match {row['id']}: {row['home_team']} vs {row['away_team']}")
        print(f"  Home: win={home_win:.2%}, avg_goals={home_avg:.2f}")
        print(f"  Away: win={away_win:.2%}, avg_goals={away_avg:.2f}")
        print(f"  Draw: {draw_pct:.2%}")
        print()


if __name__ == "__main__":
    main()