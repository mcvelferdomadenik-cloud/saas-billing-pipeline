FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.11 /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY README.md ./
COPY dbt ./dbt
COPY docker/entrypoint.sh ./entrypoint.sh
RUN uv sync --frozen --no-dev
RUN cd dbt && uv run --no-sync dbt deps && uv run --no-sync dbt parse

ENTRYPOINT ["./entrypoint.sh"]