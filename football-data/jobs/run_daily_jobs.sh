#!/bin/sh
set -e

# Ensure the environment variables from .env are available for cron jobs
set -a
. /.env
set +a

cd /job
python send_game_to_postgres.py
python ingest_matches.py
python build_features.py
