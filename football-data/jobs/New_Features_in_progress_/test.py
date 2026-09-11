import os
import argparse
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))



# ============================================================
# CONFIGURATION
# ============================================================


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


# ============================================================
# UTILITAIRES
# ============================================================

def safe_mean(series):
    """Moyenne sans erreur si la série est vide."""
    if series is None or len(series) == 0:
        return np.nan

    series = pd.to_numeric(series, errors="coerce")

    if series.dropna().empty:
        return np.nan

    return series.mean()


def safe_divide(a, b):
    """Division sécurisée."""
    if b is None or b == 0 or pd.isna(b):
        return np.nan

    return a / b


# ============================================================
# CHARGEMENT DES MATCHS
# ============================================================

def load_matches():
    """
    Charge tous les matchs.

    IMPORTANT :
    - Les matchs FINISHED servent à construire l'historique.
    - Les matchs futurs servent à générer les features de prédiction.
    """

    query = text("""
        SELECT
            id AS db_match_id,
            football_data_id,
            competition_code,
            competition_name,
            season,
            matchday,
            utc_date,
            status,
            home_team_id,
            away_team_id,
            home_score,
            away_score
        FROM matches
        ORDER BY utc_date
    """)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    if df.empty:
        raise RuntimeError("Aucun match trouvé dans la table matches.")

    df["utc_date"] = pd.to_datetime(df["utc_date"], utc=True)

    return df


# ============================================================
# CHARGEMENT DES STATISTIQUES
# ============================================================

def load_statistics():
    """
    Charge les statistiques disponibles.

    match_statistics.match_id doit correspondre à matches.id.
    """

    query = text("""
        SELECT
            match_id AS db_match_id,

            home_xg,
            away_xg,

            home_shots,
            away_shots,

            home_shots_on_target,
            away_shots_on_target,

            home_possession,
            away_possession,

            home_corners,
            away_corners,

            home_fouls,
            away_fouls,

            home_yellow_cards,
            away_yellow_cards,

            home_red_cards,
            away_red_cards

        FROM match_statistics
    """)

    with engine.connect() as conn:
        stats = pd.read_sql(query, conn)

    if stats.empty:
        print("⚠️ Aucune statistique trouvée dans match_statistics.")
        return pd.DataFrame(columns=["db_match_id"])

    return stats


# ============================================================
# MATCHS TERMINÉS AVANT UNE DATE
# ============================================================

def get_previous_matches(
    matches,
    team_id,
    cutoff_date,
    competition_code=None,
    season=None
):
    """
    Retourne les matchs terminés avant cutoff_date.

    Aucun match après ou égal à cutoff_date n'est utilisé.
    Cela évite la fuite de données.
    """

    history = matches[
        (matches["status"] == "FINISHED") &
        (matches["utc_date"] < cutoff_date) &
        (
            (matches["home_team_id"] == team_id) |
            (matches["away_team_id"] == team_id)
        )
    ].copy()

    if competition_code is not None:
        history = history[
            history["competition_code"] == competition_code
        ]

    if season is not None:
        history = history[
            history["season"] == season
        ]

    history = history.sort_values("utc_date", ascending=False)

    return history


# ============================================================
# FORM DES 5 DERNIERS MATCHS
# ============================================================

def get_team_form(
    matches,
    team_id,
    cutoff_date,
    competition_code,
    season
):
    """
    Calcule la forme sur les 5 derniers matchs.

    Retourne :
    - points
    - victoires
    - buts marqués
    - buts encaissés
    - différence de buts
    """

    history = get_previous_matches(
        matches,
        team_id,
        cutoff_date,
        competition_code,
        season
    ).head(FORM_MATCHES)

    if history.empty:
        return {
            "points": np.nan,
            "wins": np.nan,
            "goals_avg": np.nan,
            "conceded_avg": np.nan,
            "goal_diff_avg": np.nan
        }

    points = 0
    wins = 0
    goals_for = []
    goals_against = []

    for _, match in history.iterrows():

        if pd.isna(match["home_score"]) or pd.isna(match["away_score"]):
            continue

        home_score = match["home_score"]
        away_score = match["away_score"]

        if match["home_team_id"] == team_id:

            gf = home_score
            ga = away_score

            if home_score > away_score:
                points += 3
                wins += 1
            elif home_score == away_score:
                points += 1

        else:

            gf = away_score
            ga = home_score

            if away_score > home_score:
                points += 3
                wins += 1
            elif away_score == home_score:
                points += 1

        goals_for.append(gf)
        goals_against.append(ga)

    return {
        "points": points,
        "wins": wins,
        "goals_avg": safe_mean(goals_for),
        "conceded_avg": safe_mean(goals_against),
        "goal_diff_avg": safe_mean(
            [gf - ga for gf, ga in zip(goals_for, goals_against)]
        )
    }


# ============================================================
# FORCE DOMICILE / EXTÉRIEUR
# ============================================================

def get_home_away_strength(
    matches,
    team_id,
    cutoff_date,
    competition_code,
    season,
    mode
):
    """
    mode = home
        -> derniers matchs à domicile

    mode = away
        -> derniers matchs à l'extérieur
    """

    history = matches[
        (matches["status"] == "FINISHED") &
        (matches["utc_date"] < cutoff_date) &
        (matches["competition_code"] == competition_code) &
        (matches["season"] == season)
    ].copy()

    if mode == "home":

        history = history[
            history["home_team_id"] == team_id
        ]

    else:

        history = history[
            history["away_team_id"] == team_id
        ]

    history = history.sort_values(
        "utc_date",
        ascending=False
    ).head(HOME_AWAY_MATCHES)

    if history.empty:
        return {
            "win_rate": np.nan,
            "points_avg": np.nan
        }

    points = []
    wins = []

    for _, match in history.iterrows():

        if pd.isna(match["home_score"]) or pd.isna(match["away_score"]):
            continue

        home_score = match["home_score"]
        away_score = match["away_score"]

        if mode == "home":

            if home_score > away_score:
                points.append(3)
                wins.append(1)

            elif home_score == away_score:
                points.append(1)
                wins.append(0)

            else:
                points.append(0)
                wins.append(0)

        else:

            if away_score > home_score:
                points.append(3)
                wins.append(1)

            elif away_score == home_score:
                points.append(1)
                wins.append(0)

            else:
                points.append(0)
                wins.append(0)

    if not points:
        return {
            "win_rate": np.nan,
            "points_avg": np.nan
        }

    return {
        "win_rate": safe_mean(wins),
        "points_avg": safe_mean(points)
    }


# ============================================================
# REST DAYS
# ============================================================

def get_rest_days(
    matches,
    team_id,
    cutoff_date
):
    """
    Nombre de jours depuis le dernier match du club.

    On utilise tous les matchs FINISHED disponibles.
    """

    history = matches[
        (matches["status"] == "FINISHED") &
        (matches["utc_date"] < cutoff_date) &
        (
            (matches["home_team_id"] == team_id) |
            (matches["away_team_id"] == team_id)
        )
    ]

    if history.empty:
        return np.nan

    last_match = history["utc_date"].max()

    return (
        cutoff_date - last_match
    ).total_seconds() / 86400


# ============================================================
# STATISTIQUES MOYENNES SUR LES 5 DERNIERS MATCHS
# ============================================================

def get_team_statistics(
    matches,
    stats,
    team_id,
    cutoff_date,
    competition_code,
    season
):
    """
    Calcule les statistiques moyennes des 5 derniers matchs.

    xG
    xGA
    shots
    shots on target
    possession
    """

    history = get_previous_matches(
        matches,
        team_id,
        cutoff_date,
        competition_code,
        season
    ).head(FORM_MATCHES)

    if history.empty or stats.empty:
        return {
            "xg_avg": np.nan,
            "xga_avg": np.nan,
            "shots_avg": np.nan,
            "sot_avg": np.nan,
            "possession_avg": np.nan
        }

    history = history.merge(
        stats,
        on="db_match_id",
        how="left"
    )

    xg = []
    xga = []
    shots = []
    sot = []
    possession = []

    for _, match in history.iterrows():

        if match["home_team_id"] == team_id:

            xg.append(match["home_xg"])
            xga.append(match["away_xg"])

            shots.append(match["home_shots"])
            sot.append(match["home_shots_on_target"])

            possession.append(match["home_possession"])

        else:

            xg.append(match["away_xg"])
            xga.append(match["home_xg"])

            shots.append(match["away_shots"])
            sot.append(match["away_shots_on_target"])

            possession.append(match["away_possession"])

    return {
        "xg_avg": safe_mean(xg),
        "xga_avg": safe_mean(xga),
        "shots_avg": safe_mean(shots),
        "sot_avg": safe_mean(sot),
        "possession_avg": safe_mean(possession)
    }


# ============================================================
# H2H
# ============================================================

def get_h2h(
    matches,
    home_team_id,
    away_team_id,
    cutoff_date,
    competition_code
):
    """
    Derniers H2H entre les deux équipes.

    Le taux de victoire est calculé du point de vue
    de l'équipe qui joue actuellement à domicile.
    """

    h2h = matches[
        (matches["status"] == "FINISHED") &
        (matches["utc_date"] < cutoff_date) &
        (matches["competition_code"] == competition_code) &
        (
            (
                (matches["home_team_id"] == home_team_id) &
                (matches["away_team_id"] == away_team_id)
            )
            |
            (
                (matches["home_team_id"] == away_team_id) &
                (matches["away_team_id"] == home_team_id)
            )
        )
    ].copy()

    h2h = h2h.sort_values(
        "utc_date",
        ascending=False
    ).head(H2H_MATCHES)

    if h2h.empty:
        return {
            "home_win_rate": np.nan,
            "avg_goals": np.nan
        }

    home_wins = []
    total_goals = []

    for _, match in h2h.iterrows():

        if pd.isna(match["home_score"]) or pd.isna(match["away_score"]):
            continue

        total_goals.append(
            match["home_score"] + match["away_score"]
        )

        if match["home_team_id"] == home_team_id:

            if match["home_score"] > match["away_score"]:
                home_wins.append(1)
            else:
                home_wins.append(0)

        else:

            if match["away_score"] > match["home_score"]:
                home_wins.append(1)
            else:
                home_wins.append(0)

    return {
        "home_win_rate": safe_mean(home_wins),
        "avg_goals": safe_mean(total_goals)
    }


# ============================================================
# CLASSEMENT AVANT LE MATCH
# ============================================================

def get_league_positions(
    matches,
    cutoff_date,
    competition_code,
    season
):
    """
    Construit le classement de la compétition
    à la date précédant le match.

    Points :
        victoire = 3
        nul      = 1
        défaite  = 0

    Tri :
        points
        goal difference
        goals scored
    """

    history = matches[
        (matches["status"] == "FINISHED") &
        (matches["utc_date"] < cutoff_date) &
        (matches["competition_code"] == competition_code) &
        (matches["season"] == season)
    ]

    if history.empty:
        return {}

    teams = set(
        history["home_team_id"].dropna().tolist()
        +
        history["away_team_id"].dropna().tolist()
    )

    table = {
        team_id: {
            "points": 0,
            "goals_for": 0,
            "goals_against": 0
        }
        for team_id in teams
    }

    for _, match in history.iterrows():

        if pd.isna(match["home_score"]) or pd.isna(match["away_score"]):
            continue

        home = match["home_team_id"]
        away = match["away_team_id"]

        home_score = int(match["home_score"])
        away_score = int(match["away_score"])

        table[home]["goals_for"] += home_score
        table[home]["goals_against"] += away_score

        table[away]["goals_for"] += away_score
        table[away]["goals_against"] += home_score

        if home_score > away_score:

            table[home]["points"] += 3

        elif home_score < away_score:

            table[away]["points"] += 3

        else:

            table[home]["points"] += 1
            table[away]["points"] += 1

    ranking = []

    for team_id, data in table.items():

        goal_difference = (
            data["goals_for"] -
            data["goals_against"]
        )

        ranking.append({
            "team_id": team_id,
            "points": data["points"],
            "goal_difference": goal_difference,
            "goals_for": data["goals_for"]
        })

    ranking.sort(
        key=lambda x: (
            x["points"],
            x["goal_difference"],
            x["goals_for"]
        ),
        reverse=True
    )

    positions = {}

    for position, team in enumerate(ranking, start=1):
        positions[team["team_id"]] = position

    return positions


# ============================================================
# CONSTRUCTION D'UNE LIGNE DE FEATURES
# ============================================================

def build_feature_row(
    match,
    matches,
    stats
):
    """
    Construit les features d'un match.

    Toutes les données utilisées sont antérieures
    au coup d'envoi du match.
    """

    cutoff = match["utc_date"]

    home_team = match["home_team_id"]
    away_team = match["away_team_id"]

    competition = match["competition_code"]
    season = match["season"]

    # --------------------------------------------------------
    # FORM
    # --------------------------------------------------------

    home_form = get_team_form(
        matches,
        home_team,
        cutoff,
        competition,
        season
    )

    away_form = get_team_form(
        matches,
        away_team,
        cutoff,
        competition,
        season
    )

    # --------------------------------------------------------
    # STATISTIQUES
    # --------------------------------------------------------

    home_stats = get_team_statistics(
        matches,
        stats,
        home_team,
        cutoff,
        competition,
        season
    )

    away_stats = get_team_statistics(
        matches,
        stats,
        away_team,
        cutoff,
        competition,
        season
    )

    # --------------------------------------------------------
    # DOMICILE / EXTERIEUR
    # --------------------------------------------------------

    home_strength = get_home_away_strength(
        matches,
        home_team,
        cutoff,
        competition,
        season,
        "home"
    )

    away_strength = get_home_away_strength(
        matches,
        away_team,
        cutoff,
        competition,
        season,
        "away"
    )

    # --------------------------------------------------------
    # REPOS
    # --------------------------------------------------------

    home_rest = get_rest_days(
        matches,
        home_team,
        cutoff
    )

    away_rest = get_rest_days(
        matches,
        away_team,
        cutoff
    )

    # --------------------------------------------------------
    # CLASSEMENT
    # --------------------------------------------------------

    positions = get_league_positions(
        matches,
        cutoff,
        competition,
        season
    )

    home_position = positions.get(home_team, np.nan)
    away_position = positions.get(away_team, np.nan)

    # --------------------------------------------------------
    # H2H
    # --------------------------------------------------------

    h2h = get_h2h(
        matches,
        home_team,
        away_team,
        cutoff,
        competition
    )

    # --------------------------------------------------------
    # TARGET
    # --------------------------------------------------------

    target = None

    if (
        match["status"] == "FINISHED"
        and
        not pd.isna(match["home_score"])
        and
        not pd.isna(match["away_score"])
    ):

        if match["home_score"] > match["away_score"]:
            target = "H"

        elif match["home_score"] < match["away_score"]:
            target = "A"

        else:
            target = "D"

    # --------------------------------------------------------
    # FEATURES
    # --------------------------------------------------------

    row = {

        # Identifiants
        "match_id": match["db_match_id"],
        "football_data_id": match["football_data_id"],
        "competition_code": competition,
        "season": season,
        "matchday": match["matchday"],
        "home_team_id": home_team,
        "away_team_id": away_team,

        # IMPORTANT : date de coupure
        "feature_cutoff": cutoff,

        # ----------------------------------------------------
        # FORM 5
        # ----------------------------------------------------

        "home_points_5": home_form["points"],
        "away_points_5": away_form["points"],

        "points_diff_5": (
            home_form["points"] -
            away_form["points"]
            if not pd.isna(home_form["points"])
            and not pd.isna(away_form["points"])
            else np.nan
        ),

        "home_wins_5": home_form["wins"],
        "away_wins_5": away_form["wins"],

        # ----------------------------------------------------
        # BUTS
        # ----------------------------------------------------

        "home_goals_avg_5": home_form["goals_avg"],
        "away_goals_avg_5": away_form["goals_avg"],

        "home_conceded_avg_5": home_form["conceded_avg"],
        "away_conceded_avg_5": away_form["conceded_avg"],

        "home_goal_diff_avg_5": home_form["goal_diff_avg"],
        "away_goal_diff_avg_5": away_form["goal_diff_avg"],

        # ----------------------------------------------------
        # XG
        # ----------------------------------------------------

        "home_xg_avg_5": home_stats["xg_avg"],
        "away_xg_avg_5": away_stats["xg_avg"],

        "home_xga_avg_5": home_stats["xga_avg"],
        "away_xga_avg_5": away_stats["xga_avg"],

        "xg_diff_5": (
            home_stats["xg_avg"] -
            away_stats["xg_avg"]
            if not pd.isna(home_stats["xg_avg"])
            and not pd.isna(away_stats["xg_avg"])
            else np.nan
        ),

        "xga_diff_5": (
            home_stats["xga_avg"] -
            away_stats["xga_avg"]
            if not pd.isna(home_stats["xga_avg"])
            and not pd.isna(away_stats["xga_avg"])
            else np.nan
        ),

        # ----------------------------------------------------
        # SHOTS
        # ----------------------------------------------------

        "home_shots_avg_5": home_stats["shots_avg"],
        "away_shots_avg_5": away_stats["shots_avg"],

        "shots_diff_5": (
            home_stats["shots_avg"] -
            away_stats["shots_avg"]
            if not pd.isna(home_stats["shots_avg"])
            and not pd.isna(away_stats["shots_avg"])
            else np.nan
        ),

        # ----------------------------------------------------
        # SHOTS ON TARGET
        # ----------------------------------------------------

        "home_sot_avg_5": home_stats["sot_avg"],
        "away_sot_avg_5": away_stats["sot_avg"],

        "sot_diff_5": (
            home_stats["sot_avg"] -
            away_stats["sot_avg"]
            if not pd.isna(home_stats["sot_avg"])
            and not pd.isna(away_stats["sot_avg"])
            else np.nan
        ),

        # ----------------------------------------------------
        # POSSESSION
        # ----------------------------------------------------

        "home_possession_avg_5": home_stats["possession_avg"],
        "away_possession_avg_5": away_stats["possession_avg"],

        "possession_diff_5": (
            home_stats["possession_avg"] -
            away_stats["possession_avg"]
            if not pd.isna(home_stats["possession_avg"])
            and not pd.isna(away_stats["possession_avg"])
            else np.nan
        ),

        # ----------------------------------------------------
        # HOME / AWAY STRENGTH
        # ----------------------------------------------------

        "home_home_win_rate":
            home_strength["win_rate"],

        "away_away_win_rate":
            away_strength["win_rate"],

        "home_home_points_avg":
            home_strength["points_avg"],

        "away_away_points_avg":
            away_strength["points_avg"],

        # ----------------------------------------------------
        # CLASSEMENT
        # ----------------------------------------------------

        "home_league_position": home_position,
        "away_league_position": away_position,

        "league_position_diff": (
            home_position - away_position
            if not pd.isna(home_position)
            and not pd.isna(away_position)
            else np.nan
        ),

        # ----------------------------------------------------
        # REST
        # ----------------------------------------------------

        "home_rest_days": home_rest,
        "away_rest_days": away_rest,

        "rest_days_diff": (
            home_rest - away_rest
            if not pd.isna(home_rest)
            and not pd.isna(away_rest)
            else np.nan
        ),

        # ----------------------------------------------------
        # H2H
        # ----------------------------------------------------

        "h2h_home_win_rate_5":
            h2h["home_win_rate"],

        "h2h_avg_goals_5":
            h2h["avg_goals"],

        # ----------------------------------------------------
        # TARGET
        # ----------------------------------------------------

        "target": target
    }

    return row


# ============================================================
# BUILD FEATURES
# ============================================================

def build_features(
    matches,
    stats,
    competition=None,
    season=None,
    upcoming_only=False
):
    """
    Construit les features.

    upcoming_only=False :
        construit les features pour les matchs historiques
        ET les matchs à venir.

    upcoming_only=True :
        construit uniquement les features des matchs futurs.
    """

    data = matches.copy()

    if competition:
        data = data[
            data["competition_code"] == competition
        ]

    if season:
        data = data[
            data["season"] == season
        ]

    if upcoming_only:
        data = data[
            data["status"] != "FINISHED"
        ]

    data = data.sort_values("utc_date")

    print(f"📊 Matchs à traiter : {len(data)}")

    features = []

    for index, match in data.iterrows():

        try:

            row = build_feature_row(
                match,
                matches,
                stats
            )

            features.append(row)

        except Exception as e:

            print(
                f"❌ Erreur match "
                f"{match.get('football_data_id', index)} : {e}"
            )

    if not features:
        return pd.DataFrame()

    return pd.DataFrame(features)


# ============================================================
# SAUVEGARDE POSTGRESQL
# ============================================================

def save_features(features_df):
    """
    Insert / update dans match_features.

    Nécessite que la table match_features existe.
    """

    if features_df.empty:
        print("⚠️ Aucune feature à sauvegarder.")
        return

    columns = list(features_df.columns)

    # Colonnes SQL
    column_sql = ", ".join(columns)

    # Valeurs SQL
    value_sql = ", ".join(
        f":{column}"
        for column in columns
    )

    update_columns = [
        column
        for column in columns
        if column != "match_id"
    ]

    update_sql = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in update_columns
    )

    sql = text(f"""
        INSERT INTO match_features (
            {column_sql}
        )
        VALUES (
            {value_sql}
        )
        ON CONFLICT (match_id)
        DO UPDATE SET
            {update_sql}
    """)

    # Conversion NaN -> None
    records = features_df.replace(
        {np.nan: None}
    ).to_dict(orient="records")

    with engine.begin() as conn:

        for record in records:
            conn.execute(sql, record)

    print(
        f"✅ {len(records)} lignes sauvegardées "
        f"dans match_features"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Build football match features"
    )

    parser.add_argument(
        "--competition",
        default=None,
        help="Competition code, exemple: FL1"
    )

    parser.add_argument(
        "--season",
        type=int,
        default=None,
        help="Saison, exemple: 2026"
    )

    parser.add_argument(
        "--upcoming",
        action="store_true",
        help="Construire uniquement les matchs à venir"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("⚽ FOOTBALL FEATURE ENGINEERING")
    print("=" * 60)

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    print("\n📥 Chargement des matchs...")

    matches = load_matches()

    print(
        f"   {len(matches)} matchs chargés"
    )

    print("\n📥 Chargement des statistiques...")

    stats = load_statistics()

    print(
        f"   {len(stats)} statistiques chargées"
    )

    # --------------------------------------------------------
    # BUILD
    # --------------------------------------------------------

    print("\n🔧 Construction des features...")

    features_df = build_features(
        matches=matches,
        stats=stats,
        competition=args.competition,
        season=args.season,
        upcoming_only=args.upcoming
    )

    if features_df.empty:

        print("❌ Aucune feature générée.")
        return

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print("\n📋 Exemple :")

    display_columns = [
        "match_id",
        "competition_code",
        "season",
        "matchday",
        "home_team_id",
        "away_team_id",
        "home_points_5",
        "away_points_5",
        "home_goals_avg_5",
        "away_goals_avg_5",
        "home_xg_avg_5",
        "away_xg_avg_5",
        "home_league_position",
        "away_league_position",
        "target"
    ]

    available_columns = [
        col
        for col in display_columns
        if col in features_df.columns
    ]

    print(
        features_df[available_columns].head(10).to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    print("\n💾 Sauvegarde...")

    save_features(features_df)

    print("\n" + "=" * 60)
    print("✅ TERMINÉ")
    print("=" * 60)


if __name__ == "__main__":
    main()