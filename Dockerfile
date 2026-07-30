FROM python:3.12.8-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
RUN addgroup --system wristalpha && adduser --system --ingroup wristalpha wristalpha

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

COPY alembic.ini ./
COPY migrations ./migrations
COPY config ./config
COPY docs ./docs

RUN mkdir -p /app/data/cache /app/data/imports && chown -R wristalpha:wristalpha /app
USER wristalpha

EXPOSE 8000
CMD ["uvicorn", "wristalpha.api:app", "--host", "0.0.0.0", "--port", "8000"]
