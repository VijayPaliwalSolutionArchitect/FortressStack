# FortressStack Gateway (backend) image
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY config ./config

EXPOSE 4001

# Seeded config is baked in; override via FORTRESS_* env vars in production.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4001"]