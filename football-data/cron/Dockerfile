FROM python:3.11-slim

WORKDIR /job

COPY .env /
COPY request-API /request-API
COPY jobs/ingest_matches.py /job
COPY jobs/build_features.py /job
COPY jobs/send_game_to_postgres.py /job
COPY jobs/run_daily_jobs.sh /job/run_daily_jobs.sh
COPY jobs/football-jobs.cron /etc/cron.d/football-jobs

RUN apt-get update && apt-get install -y cron \
    && pip install requests pandas sqlalchemy psycopg2-binary python-dotenv \
    && rm -rf /var/lib/apt/lists/* \
    && chmod +x /job/run_daily_jobs.sh \
    && chmod 0644 /etc/cron.d/football-jobs \
    && crontab /etc/cron.d/football-jobs

CMD ["cron", "-f"]