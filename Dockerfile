FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY README.md ./
COPY dbt ./dbt
COPY docker/entrypoint.sh ./entrypoint.sh
RUN uv sync --frozen --no-dev

ENTRYPOINT ["./entrypoint.sh"]