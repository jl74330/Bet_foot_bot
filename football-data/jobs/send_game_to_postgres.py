import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

df = pd.read_csv("request-API/matches.csv")

# Add id column
df.reset_index(inplace=True)
df.rename(columns={'index': 'id'}, inplace=True)

# Add expected feature columns if they do not exist in the source data
for col in ["home_win_pct", "away_win_pct", "draw_pct", "avg_goals_home", "avg_goals_away"]:
    if col not in df.columns:
        df[col] = 0.0

DB_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER', 'foot')}:{os.getenv('POSTGRES_PASSWORD', 'footpass')}@"
    f"{os.getenv('POSTGRES_HOST', 'db')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'football')}"
)

engine = create_engine(DB_URL)

df.to_sql("matches", engine, if_exists="replace", index=False)

print("✅ Données envoyées dans PostgreSQL")