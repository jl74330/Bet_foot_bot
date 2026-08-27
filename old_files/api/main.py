import os
import joblib
import pandas as pd
from fastapi import FastAPI
from sqlalchemy import create_engine

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

model_path = os.path.join(BASE_DIR, "model.pkl")
encoder_path = os.path.join(BASE_DIR, "label_encoder.pkl")

# Charger modèle et encoder
model = joblib.load(model_path)
le = joblib.load(encoder_path)

engine = create_engine(
    "postgresql+psycopg2://foot:footpass@localhost:5432/football"
)

def get_team_form(team):
    query = f"""
    SELECT home_form_scored, home_form_conceded
    FROM features
    WHERE home_team = '{team}'
    ORDER BY date DESC
    LIMIT 1
    """
    df = pd.read_sql(query, engine)
    return df.iloc[0]

@app.get("/")
def home():
    return {"message": "Football AI API is running"}

@app.post("/predict")
def predict(home_team: str, away_team: str):
    home_form = get_team_form(home_team)
    away_form = get_team_form(away_team)

    X = [[
        home_form["home_form_scored"],
        home_form["home_form_conceded"],
        away_form["home_form_scored"],
        away_form["home_form_conceded"],
    ]]

    pred = model.predict(X)
    result = le.inverse_transform(pred)[0]

    return {
        "home_team": home_team,
        "away_team": away_team,
        "prediction": result
    }

#  Upcoming matches

@app.get("/predict_upcoming")
def predict_upcoming():

    query = """
        SELECT * FROM matches
        WHERE match_date > NOW()
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