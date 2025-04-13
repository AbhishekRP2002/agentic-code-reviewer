FROM python:3.11-bookworm AS builder


WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN pip install --no-cache-dir poetry

ENV POETRY_VIRTUALENVS_CREATE=false

RUN poetry install --no-interaction --no-ansi --no-root
RUN poetry run python -m pip list


COPY . .

ENTRYPOINT ["poetry", "run", "python", "-m", "src.code_review"]
