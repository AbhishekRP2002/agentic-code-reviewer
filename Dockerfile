FROM python:3.11-bookworm AS builder


WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN pip install --no-cache-dir poetry

RUN poetry install --no-interaction --no-ansi --no-root
RUN poetry run python -m pip list


COPY . .

ENTRYPOINT ["poetry", "run", "python", "-m", "src.code_review"]
