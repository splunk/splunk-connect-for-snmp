## Running unit tests

### Install poetry
curl -sSL https://install.python-poetry.org | python3 -

### Install dependencies
poetry install

### Run unit tests
poetry run pytest --cov=./splunk_connect_for_snmp --cov-report=xml --junitxml=test-results/junit.xml