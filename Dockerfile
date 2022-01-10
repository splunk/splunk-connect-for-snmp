FROM python:3.10.0-bullseye as base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1
RUN mkdir /app
WORKDIR /app

FROM base as builder
RUN pip install --upgrade pip ;\
    pip install poetry 

COPY poetry.lock pyproject.toml /app/
COPY splunk_connect_for_snmp /app/splunk_connect_for_snmp
WORKDIR /app
RUN poetry config virtualenvs.in-project true ;\
    poetry build ;\
    . /app/.venv/bin/activate ;\
    pip install dist/*.whl




FROM base as final

COPY --from=builder /app/.venv /app/.venv
COPY entrypoint.sh ./
ENTRYPOINT ["./entrypoint.sh"]
