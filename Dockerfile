FROM python:3.10.0-bullseye as base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1
RUN mkdir /app
WORKDIR /app

FROM base as builder
WORKDIR /code
RUN pip install poetry
RUN python -m venv /venv
RUN /venv/bin/python -m pip install --upgrade pip

COPY poetry.lock pyproject.toml /code/
RUN poetry export -f requirements.txt | /venv/bin/pip install -r /dev/stdin

COPY splunk_connect_for_snmp /code/splunk_connect_for_snmp

#RUN poetry install --no-dev -n --no-ansi
RUN poetry build && /venv/bin/pip install dist/*.whl


FROM base as final

COPY --from=builder /venv /venv
COPY entrypoint.sh ./
ENTRYPOINT ["./entrypoint.sh"]
