import os
import joblib
import pandas as pd
from fastapi import FastAPI
from sqlalchemy import create_engine

app = FastAPI()

BASE_DIR = os.path.dirname(__file__)

model_path = os.path.join(BASE_DIR, "model.pkl")
encoder_path = os.path.join(BASE_DIR, "label_encoder.pkl")

# Charger modèle et encoder
model = joblib.load(model_path)
le = joblib.load(encoder_path)

# PostgreSQL connection
# ---------------------------
DB_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
engine = create_engine(DB_URL)


@app.get("/")
def home():
    return {"status": "API is running"}


# ---------------------------
# Get match from DB
# ---------------------------
@app.get("/match/{match_id}")
def get_match(match_id: int):
    query = f"SELECT * FROM matches WHERE id = {match_id}"
    df = pd.read_sql(query, engine)

    if df.empty:
        return {"error": "Match not found"}

    return df.to_dict(orient="records")


# ---------------------------
# Predict from DB match
# ---------------------------
def compute_form(team, current_date):
    query = f"""
    SELECT home_score, away_score, home_team, away_team
    FROM matches
    WHERE (home_team = '{team}' OR away_team = '{team}') AND date < '{current_date}'
    ORDER BY date DESC
    LIMIT 5
    """
    past_df = pd.read_sql(query, engine)
    
    goals_scored = 0
    goals_conceded = 0
    
    for _, row in past_df.iterrows():
        if row['home_team'] == team:
            goals_scored += row['home_score']
            goals_conceded += row['away_score']
        else:
            goals_scored += row['away_score']
            goals_conceded += row['home_score']
    
    return goals_scored, goals_conceded


@app.get("/predict_from_db/{match_id}")
def predict_from_db(match_id: int):
    query = f"SELECT * FROM matches WHERE id = {match_id}"
    df = pd.read_sql(query, engine)

    if df.empty:
        return {"error": "Match not found"}

    match = df.iloc[0]
    home_team = match['home_team']
    away_team = match['away_team']
    match_date = match['date']

    home_scored, home_conceded = compute_form(home_team, match_date)
    away_scored, away_conceded = compute_form(away_team, match_date)

    X = [[home_scored, home_conceded, away_scored, away_conceded]]

    pred = model.predict(X)
    result = le.inverse_transform(pred)[0]

    return {
        "match_id": match_id,
        "home_team": home_team,
        "away_team": away_team,
        "prediction": result
    }

    #  mêmes features que dans ton train_model.py
    features = df[[
        "home_win_pct",
        "away_win_pct",
        "draw_pct",
        "avg_goals_home",
        "avg_goals_away"
    ]]

#  Upcoming matches

@app.get("/predict_upcoming")
def predict_upcoming():

    query = """
        SELECT * FROM matches
        WHERE date > NOW()
    """

    df = pd.read_sql(query, engine)

    if df.empty:
        return {"message": "No upcoming matches found"}

    features = df[[
        "home_win_pct",
        "away_win_pct",
        "draw_pct",
        "avg_goals_home",
        "avg_goals_away"
    ]]

    preds = model.predict(features)
    probas = model.predict_proba(features).max(axis=1)

    df["prediction"] = encoder.inverse_transform(preds)
    df["confidence"] = probas

    return df[[
        "id",
        "home_team",
        "away_team",
        "prediction",
        "confidence"
    ]].to_dict(orient="records")
