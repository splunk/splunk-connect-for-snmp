FROM python:3.12-alpine AS base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1
RUN apk add -U git sqlite-dev
RUN pip install --upgrade setuptools pip
RUN mkdir /app
WORKDIR /app

FROM base AS builder
RUN pip install --upgrade pip ;\
    pip install poetry 

COPY poetry.lock pyproject.toml /app/
COPY splunk_connect_for_snmp /app/splunk_connect_for_snmp
WORKDIR /app
RUN poetry config virtualenvs.in-project true ;\
    poetry build ;\
    . /app/.venv/bin/activate ;\
    pip install dist/*.whl

FROM base AS final

RUN mkdir /.pysnmp && chown 10001:10001 /.pysnmp
RUN chown 10001:10001 /tmp
USER 10001:10001
COPY --from=builder /app/.venv /app/.venv
COPY entrypoint.sh ./
ENTRYPOINT ["./entrypoint.sh"]
