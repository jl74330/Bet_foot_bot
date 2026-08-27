import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql+psycopg2://foot:footpass@127.0.0.1:5432/football"
)

query = "SELECT * FROM matches ORDER BY date"
df = pd.read_sql(query, engine)

print(df.head())

# Creer le resultat du match
def get_result(row):
    if row["home_score"] > row["away_score"]:
        return "H"
    elif row["home_score"] < row["away_score"]:
        return "A"
    return "D"

df["result"] = df.apply(get_result, axis=1)

# Forme des equipes
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")

def compute_form(team, current_date):
    past_matches = df[
        ((df["home_team"] == team) | (df["away_team"] == team)) &
        (df["date"] < current_date)
    ].tail(5)

    goals_scored = 0
    goals_conceded = 0

    for _, m in past_matches.iterrows():
        if m["home_team"] == team:
            goals_scored += m["home_score"]
            goals_conceded += m["away_score"]
        else:
            goals_scored += m["away_score"]
            goals_conceded += m["home_score"]

    return goals_scored, goals_conceded

# Contruire les features
features = []

for _, row in df.iterrows():
    home_scored, home_conceded = compute_form(row["home_team"], row["date"])
    away_scored, away_conceded = compute_form(row["away_team"], row["date"])

    features.append({
        "home_team": row["home_team"],
        "away_team": row["away_team"],
        "home_form_scored": home_scored,
        "home_form_conceded": home_conceded,
        "away_form_scored": away_scored,
        "away_form_conceded": away_conceded,
        "result": row["result"]
    })

features_df = pd.DataFrame(features)
print(features_df.head())

# Sauvegarder en base
features_df.to_sql("features", engine, if_exists="replace", index=False)
print("✅ Features sauvegardées en DB")