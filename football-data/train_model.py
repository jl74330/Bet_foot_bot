import pandas as pd
from sqlalchemy import create_engine
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

# Connexion DB
engine = create_engine(
    "postgresql+psycopg2://foot:footpass@localhost:5432/football"
)

# Lire features
df = pd.read_sql("SELECT * FROM features", engine)

# Features / Target
X = df[
    [
        "home_form_scored",
        "home_form_conceded",
        "away_form_scored",
        "away_form_conceded",
    ]
]

y = df["result"]

# Encoder target
le = LabelEncoder()
y_encoded = le.fit_transform(y)

# Split train / test
X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=42
)

# Modèle
model = RandomForestClassifier(n_estimators=200)
model.fit(X_train, y_train)

# Évaluation
preds = model.predict(X_test)
acc = accuracy_score(y_test, preds)
print(f"Accuracy: {acc}")

# Sauvegarde
joblib.dump(model, "model.pkl")
joblib.dump(le, "label_encoder.pkl")

print("✅ Modèle sauvegardé")