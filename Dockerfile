FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TOWER_OPTIMIZER_DATA_DIR=/app/data \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

COPY requirements.txt pyproject.toml README.md LICENSE NOTICE.md app.py ./
COPY tower_optimizer ./tower_optimizer
COPY assets ./assets
COPY .streamlit ./.streamlit

RUN pip install --upgrade pip \
    && pip install .

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/data/profiles /app/data/custom_icons /app/data/game_updates

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"

ENTRYPOINT ["/entrypoint.sh"]
