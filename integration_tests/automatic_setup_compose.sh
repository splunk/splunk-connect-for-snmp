#!/bin/bash

# Color
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

function red {
    printf "${RED}$@${NC}\n"
}

function green {
    printf "${GREEN}$@${NC}\n"
}

function yellow {
    printf "${YELLOW}$@${NC}\n"
}

wait_for_splunk() {
  while [ "$(sudo docker ps | grep "splunk:latest" | grep healthy)" == "" ] ; do
    echo $(yellow "Waiting for Splunk initialization")
    sleep 1
  done
}

function define_python() {
  echo $(yellow "define python")
  if command -v python &> /dev/null; then
      PYTHON=python
  elif command -v python3 &> /dev/null; then
      PYTHON=python3
  else
    echo $(red "Cannot find python command")
    exit 1
  fi
}

deploy_poetry() {
  sudo apt -y install python3-venv
  curl -sSL https://install.python-poetry.org | $PYTHON -
  export PATH="/home/ubuntu/.local/bin:$PATH"
  poetry install
  poetry add --group dev splunk-sdk
  poetry add --group dev splunklib
  poetry add --group dev pysnmp
  poetry add --group dev pytest-asyncio
  poetry add --group dev pysnmpcrypto
}

wait_for_containers_to_be_up() {
  while true; do
    CONTAINERS_SC4SNMP=$(sudo docker ps | grep "sc4snmp\|worker-poller\|worker-sender\|worker-trap" | grep -v "Name" | wc -l)
    if [ "$CONTAINERS_SC4SNMP" -gt 0 ]; then
      CONTAINERS_UP=$(sudo docker ps | grep "sc4snmp\|worker-poller\|worker-sender\|worker-trap" | grep "Up" | wc -l)
      CONTAINERS_EXITED=$(sudo docker ps | grep "sc4snmp\|worker-poller\|worker-sender\|worker-trap" | grep "Exited" | wc -l)
      CONTAINERS_TOTAL=$CONTAINERS_SC4SNMP

      if [ "$CONTAINERS_UP" -eq "$CONTAINERS_TOTAL" ] || \
         { [ "$CONTAINERS_EXITED" -eq 1 ] && [ "$((CONTAINERS_UP + CONTAINERS_EXITED))" -eq "$CONTAINERS_TOTAL" ]; }; then
        echo $(green "All 'sc4snmp' containers are ready.")
        break
      fi

      echo $(yellow "Waiting for all 'sc4snmp' containers to be ready...")
    else
      echo $(yellow "No 'sc4snmp' containers found. Waiting for them to appear...")
    fi

    sleep 1
  done
}



sudo apt-get update -y
sudo apt-get install snmpd -y
sudo sed -i -E 's/agentaddress[[:space:]]+127.0.0.1,\[::1\]/#agentaddress  127.0.0.1,\[::1\]\nagentaddress udp:1161,udp6:[::1]:1161/g' /etc/snmp/snmpd.conf
echo "" | sudo tee -a /etc/snmp/snmpd.conf
echo "createUser r-wuser SHA admin1234 AES admin1234" | sudo tee -a /etc/snmp/snmpd.conf
echo "rwuser r-wuser priv" | sudo tee -a /etc/snmp/snmpd.conf
sudo systemctl restart snmpd

echo "Show working directory:"
pwd

echo $(green "Building Docker image")

sudo docker build -t snmp-local .

sudo docker pull splunk/splunk:latest
echo $(green "Running Splunk in Docker")
sudo docker run -d -p 8000:8000 -p 8088:8088 -p 8089:8089 -e SPLUNK_GENERAL_TERMS=--accept-sgt-current-at-splunk-com -e SPLUNK_START_ARGS='--accept-license' -e SPLUNK_PASSWORD='changeme2' splunk/splunk:latest

wait_for_splunk

cd integration_tests
chmod u+x ./prepare_splunk.sh
echo $(green "Preparing Splunk instance")
./prepare_splunk.sh

echo $(green "Setting up docker compose configuration")
cp ../docker_compose/* .
# Define the filenames for the variables
SCHEDULER_CONFIG_FILE="scheduler-config.yaml"
TRAPS_CONFIG_FILE="traps-config.yaml"
INVENTORY_FILE="inventory-tests.csv"
COREFILE="Corefile"

# Get the absolute paths of the files
SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH=$(realpath "$SCHEDULER_CONFIG_FILE")
TRAPS_CONFIG_FILE_ABSOLUTE_PATH=$(realpath "$TRAPS_CONFIG_FILE")
INVENTORY_FILE_ABSOLUTE_PATH=$(realpath "$INVENTORY_FILE")
COREFILE_ABS_PATH=$(realpath "$COREFILE")
SPLUNK_HEC_HOST=$(hostname -I | cut -d " " -f1)
SPLUNK_HEC_TOKEN=$(cat hec_token)

# Temporary file to store the updated .env content
TEMP_ENV_FILE=".env.tmp"

# Update or add the variables in the .env file
awk -v scheduler_path="$SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH" \
    -v traps_path="$TRAPS_CONFIG_FILE_ABSOLUTE_PATH" \
    -v inventory_path="$INVENTORY_FILE_ABSOLUTE_PATH" \
    -v corefile_path="$COREFILE_ABS_PATH" \
    -v splunk_hec_host="$SPLUNK_HEC_HOST" \
    -v splunk_hec_token="$SPLUNK_HEC_TOKEN" \
    '
    BEGIN {
        updated["SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH"] = 0;
        updated["TRAPS_CONFIG_FILE_ABSOLUTE_PATH"] = 0;
        updated["INVENTORY_FILE_ABSOLUTE_PATH"] = 0;
        updated["COREFILE_ABS_PATH"] = 0;
        updated["SPLUNK_HEC_HOST"] = 0;
        updated["SPLUNK_HEC_TOKEN"] = 0;
    }
    {
        if ($1 == "SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH=") {
            print "SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH=" scheduler_path;
            updated["SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH"] = 1;
        } else if ($1 == "TRAPS_CONFIG_FILE_ABSOLUTE_PATH=") {
            print "TRAPS_CONFIG_FILE_ABSOLUTE_PATH=" traps_path;
            updated["TRAPS_CONFIG_FILE_ABSOLUTE_PATH"] = 1;
        } else if ($1 == "INVENTORY_FILE_ABSOLUTE_PATH=") {
            print "INVENTORY_FILE_ABSOLUTE_PATH=" inventory_path;
            updated["INVENTORY_FILE_ABSOLUTE_PATH"] = 1;
        } else if ($1 == "COREFILE_ABS_PATH=") {
            print "COREFILE_ABS_PATH=" corefile_path;
            updated["COREFILE_ABS_PATH"] = 1;
        } else if ($1 == "SPLUNK_HEC_HOST=") {
            print "SPLUNK_HEC_HOST=" splunk_hec_host;
            updated["SPLUNK_HEC_HOST"] = 1;
        } else if ($1 == "SPLUNK_HEC_TOKEN=") {
            print "SPLUNK_HEC_TOKEN=" splunk_hec_token;
            updated["SPLUNK_HEC_TOKEN"] = 1;
        } else {
            print $0;
        }
    }
    END {
        if (updated["SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH"] == 0) {
            print "SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH=" scheduler_path;
        }
        if (updated["TRAPS_CONFIG_FILE_ABSOLUTE_PATH"] == 0) {
            print "TRAPS_CONFIG_FILE_ABSOLUTE_PATH=" traps_path;
        }
        if (updated["INVENTORY_FILE_ABSOLUTE_PATH"] == 0) {
            print "INVENTORY_FILE_ABSOLUTE_PATH=" inventory_path;
        }
        if (updated["COREFILE_ABS_PATH"] == 0) {
            print "COREFILE_ABS_PATH=" corefile_path;
        }
        if (updated["SPLUNK_HEC_HOST"] == 0) {
            print "SPLUNK_HEC_HOST=" splunk_hec_host;
        }
        if (updated["SPLUNK_HEC_TOKEN"] == 0) {
            print "SPLUNK_HEC_TOKEN=" splunk_hec_token;
        }
    }
    ' .env > "$TEMP_ENV_FILE"

# Replace the old .env file with the updated one
mv "$TEMP_ENV_FILE" .env

# Create snmpv3 secret
python3 -m pip install ruamel.yaml
python3 $(realpath "manage_secrets.py") --path_to_compose $(pwd) \
--secret_name sv3poller \
--userName r-wuser \
--privProtocol AES \
--privKey admin1234 \
--authProtocol SHA \
--authKey admin1234 \
--contextEngineId 8000000903000A397056B8AC \
--traps false

sed -i "s/###LOAD_BALANCER_ID###/$(hostname -I | cut -d " " -f1)/" inventory-tests.csv
echo $(green "Running SNMP simulators in Docker")
sudo docker run -d -p 161:161/udp tandrup/snmpsim
sudo docker run -d -p 1162:161/udp tandrup/snmpsim
sudo docker run -d -p 1163:161/udp tandrup/snmpsim
sudo docker run -d -p 1164:161/udp tandrup/snmpsim
sudo docker run -d -p 1165:161/udp tandrup/snmpsim
sudo docker run -d -p 1166:161/udp -v $(pwd)/snmpsim/data:/usr/local/snmpsim/data -e EXTRA_FLAGS="--variation-modules-dir=/usr/local/snmpsim/variation --data-dir=/usr/local/snmpsim/data" tandrup/snmpsim

echo $(green "Running up Docker Compose environment")
sudo docker compose up -d
wait_for_containers_to_be_up

sudo docker ps
sudo docker exec sc4snmp-inventory printenv

if [[ $1 == 'integration' ]]; then
  define_python
  deploy_poetry
fi
