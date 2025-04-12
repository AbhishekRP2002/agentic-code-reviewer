FROM python:3.11-bookworm AS builder


WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN pip install --no-cache-dir poetry

RUN poetry install --no-interaction --no-ansi --no-root

COPY . .

ENTRYPOINT ["python", "src/code_review.py"]
