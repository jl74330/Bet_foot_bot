FROM python:3.11-slim

WORKDIR /job

COPY jobs/ingest_matches.py /job
COPY jobs/build_features.py /job
COPY jobs/send_game_to_postgres.py /job
COPY request-API /job/request-API

RUN pip install requests pandas sqlalchemy psycopg2-binary python-dotenv

CMD ["python", "ingest_matches.py"]