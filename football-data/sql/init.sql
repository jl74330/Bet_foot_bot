CREATE TABLE IF NOT EXISTS matches (
    id BIGSERIAL PRIMARY KEY,

    football_data_id BIGINT UNIQUE,
    api_football_id BIGINT UNIQUE,

    league TEXT NOT NULL,
    season INTEGER NOT NULL,
    date TIMESTAMP NOT NULL,

    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,

    home_score INTEGER,
    away_score INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_different_teams
        CHECK (home_team <> away_team),

    CONSTRAINT chk_scores
        CHECK (
            (home_score IS NULL AND away_score IS NULL)
            OR
            (home_score >= 0 AND away_score >= 0)
        )
);


CREATE INDEX idx_matches_league_season
    ON matches (league, season);

CREATE INDEX idx_matches_date
    ON matches (date);

CREATE INDEX idx_matches_home_team_date
    ON matches (home_team, date);

CREATE INDEX idx_matches_away_team_date
    ON matches (away_team, date);


CREATE TABLE IF NOT EXISTS match_statistics (
    match_id BIGINT PRIMARY KEY,

    home_xg DOUBLE PRECISION,
    away_xg DOUBLE PRECISION,

    home_goals_prevented DOUBLE PRECISION,
    away_goals_prevented DOUBLE PRECISION,

    home_shots INTEGER,
    away_shots INTEGER,

    home_shots_on_target INTEGER,
    away_shots_on_target INTEGER,

    home_shots_off_target INTEGER,
    away_shots_off_target INTEGER,

    home_shots_blocked INTEGER,
    away_shots_blocked INTEGER,

    home_shots_insidebox INTEGER,
    away_shots_insidebox INTEGER,

    home_shots_outsidebox INTEGER,
    away_shots_outsidebox INTEGER,

    home_possession DOUBLE PRECISION,
    away_possession DOUBLE PRECISION,

    home_corners INTEGER,
    away_corners INTEGER,

    home_fouls INTEGER,
    away_fouls INTEGER,

    home_offsides INTEGER,
    away_offsides INTEGER,

    home_passes INTEGER,
    away_passes INTEGER,

    home_passes_accurate INTEGER,
    away_passes_accurate INTEGER,

    home_pass_accuracy DOUBLE PRECISION,
    away_pass_accuracy DOUBLE PRECISION,

    home_yellow_cards INTEGER,
    away_yellow_cards INTEGER,

    home_red_cards INTEGER,
    away_red_cards INTEGER,

    home_saves INTEGER,
    away_saves INTEGER,

    source TEXT NOT NULL DEFAULT 'api-football',

    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_match_statistics_match
        FOREIGN KEY (match_id)
        REFERENCES matches(id)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS features (
    match_id BIGINT PRIMARY KEY,

    feature_cutoff TIMESTAMP NOT NULL,

    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    league TEXT NOT NULL,
    season INTEGER NOT NULL,

    home_points_5 DOUBLE PRECISION,
    away_points_5 DOUBLE PRECISION,
    points_diff_5 DOUBLE PRECISION,

    home_wins_5 INTEGER,
    away_wins_5 INTEGER,

    home_goals_avg_5 DOUBLE PRECISION,
    away_goals_avg_5 DOUBLE PRECISION,

    home_conceded_avg_5 DOUBLE PRECISION,
    away_conceded_avg_5 DOUBLE PRECISION,

    home_goal_diff_avg_5 DOUBLE PRECISION,
    away_goal_diff_avg_5 DOUBLE PRECISION,

    home_xg_avg_5 DOUBLE PRECISION,
    away_xg_avg_5 DOUBLE PRECISION,

    home_xga_avg_5 DOUBLE PRECISION,
    away_xga_avg_5 DOUBLE PRECISION,

    xg_diff_5 DOUBLE PRECISION,
    xga_diff_5 DOUBLE PRECISION,

    home_shots_avg_5 DOUBLE PRECISION,
    away_shots_avg_5 DOUBLE PRECISION,
    shots_diff_5 DOUBLE PRECISION,

    home_sot_avg_5 DOUBLE PRECISION,
    away_sot_avg_5 DOUBLE PRECISION,
    sot_diff_5 DOUBLE PRECISION,

    home_possession_avg_5 DOUBLE PRECISION,
    away_possession_avg_5 DOUBLE PRECISION,
    possession_diff_5 DOUBLE PRECISION,

    home_corners_avg_5 DOUBLE PRECISION,
    away_corners_avg_5 DOUBLE PRECISION,
    corners_diff_5 DOUBLE PRECISION,

    home_home_win_rate DOUBLE PRECISION,
    away_away_win_rate DOUBLE PRECISION,

    home_home_points_avg DOUBLE PRECISION,
    away_away_points_avg DOUBLE PRECISION,

    home_league_position INTEGER,
    away_league_position INTEGER,
    league_position_diff INTEGER,

    home_rest_days DOUBLE PRECISION,
    away_rest_days DOUBLE PRECISION,
    rest_days_diff DOUBLE PRECISION,

    h2h_home_win_rate_5 DOUBLE PRECISION,
    h2h_avg_goals_5 DOUBLE PRECISION,

    result CHAR(1),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_features_match
        FOREIGN KEY (match_id)
        REFERENCES matches(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_result
        CHECK (
            result IS NULL
            OR result IN ('H', 'D', 'A')
        )
);


CREATE INDEX idx_features_league_season
    ON features (league, season);

CREATE INDEX idx_features_cutoff
    ON features (feature_cutoff);

CREATE INDEX idx_features_result
    ON features (result);