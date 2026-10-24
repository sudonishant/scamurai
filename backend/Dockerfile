FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo zlib1g fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 scamurai \
    && useradd --system --uid 10001 --gid scamurai --home-dir /app scamurai

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=scamurai:scamurai . .
RUN mkdir -p /var/storage && chown -R scamurai:scamurai /var/storage
USER scamurai

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
