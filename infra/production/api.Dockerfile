FROM python:3.12-slim-trixie
WORKDIR /app
ENV PAO_ROOT=/app PYTHONPATH=/app/apps/api PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.lock pyproject.toml alembic.ini ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home pao
COPY apps/api apps/api
COPY packages packages
COPY infra/production/entrypoint.py infra/production/grants.sql infra/production/
RUN pip install --no-deps . && mkdir -p /app/.runtime && chown -R 10001:10001 /app/.runtime
USER 10001:10001
ENTRYPOINT ["python", "infra/production/entrypoint.py"]
CMD ["api"]
