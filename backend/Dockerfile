# API image. Build with the repo root as context:
#   docker build -f backend/Dockerfile .
# Keeps the repo layout (/srv/backend/app, /srv/data/processed) so the paths
# in backend/app/config.py resolve without overrides.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /srv

COPY requirements.txt .
# uvicorn is dev-only in requirements-dev.txt; same pin here.
RUN pip install -r requirements.txt uvicorn==0.34.0

COPY backend/app backend/app
COPY data/processed data/processed

RUN useradd --uid 10001 --no-create-home app
USER app

WORKDIR /srv/backend
EXPOSE 8000

# The slim image has no curl, so use Python for the health check.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
