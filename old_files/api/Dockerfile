FROM python:3.11-slim

WORKDIR /football-data

COPY . .

ENV PYTHONPATH=/football-data

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    pandas \
    sqlalchemy \
    psycopg2-binary \
    scikit-learn \
    joblib

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]