FROM python:3.11-slim

WORKDIR /app

# Copy API code
COPY api/ /app/

# Copy ML artifacts from project root
COPY model.pkl /app/model.pkl
COPY label_encoder.pkl /app/label_encoder.pkl

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    pandas \
    sqlalchemy \
    psycopg2-binary \
    scikit-learn \
    joblib

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]