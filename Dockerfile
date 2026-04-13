FROM python:3.10-alpine AS base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1
RUN apk add -U git sqlite-dev && apk upgrade zlib libcrypto3 libssl3 libuuid
RUN pip install --upgrade setuptools pip wheel
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
COPY docker_scripts/manage_secrets.py /app/secrets/
RUN chown 10001:10001 /app/secrets/
RUN chown 10001:10001 /tmp
COPY --from=builder /app/.venv /app/.venv
COPY entrypoint.sh /app/entrypoint.sh
COPY construct-connection-strings.sh /app/construct-connection-strings.sh
RUN chmod +x /app/construct-connection-strings.sh /app/entrypoint.sh
USER 10001:10001
ENTRYPOINT ["/app/entrypoint.sh"]
