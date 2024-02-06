FROM python:3.10.0-bullseye AS base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1
RUN mkdir /app
WORKDIR /app

FROM base AS builder
COPY --from=golang:alpine3.19 /usr/local/go/ /usr/local/go/
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOPATH="/usr/local/go"

RUN go install golang.org/x/tools/cmd/goimports@latest
RUN go install github.com/go-python/gopy@latest

RUN pip install --upgrade pip ;\
    pip install poetry 

COPY poetry.lock pyproject.toml /app/
COPY splunk_connect_for_snmp /app/splunk_connect_for_snmp
WORKDIR /app
RUN poetry config virtualenvs.in-project true ;\
    poetry install; \
    . /app/.venv/bin/activate ;\
    python3 -m pip install pybindgen; \
    cd /app/splunk_connect_for_snmp/gopoller;\
    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:. ;\
    gopy build -output=out -vm=python3 gopoller;\
    cd /app;\
    deactivate;\
    poetry build ;\
    . /app/.venv/bin/activate ;\
    pip install dist/*.whl

FROM base AS final

COPY --from=builder /app/.venv /app/.venv
COPY entrypoint.sh ./
ENTRYPOINT ["./entrypoint.sh"]
