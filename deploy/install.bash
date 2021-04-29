#!/bin/bash

BRANCH=${BRANCH:=install-from-url}
echo using $BRANCH
URL=https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/${BRANCH}/deploy/install_full.bash

function download {
  scratch="$(mktemp -d -t tmp.XXXXXXXXXX)" || exit
  script_file="$scratch/install_full.bash"

  echo "Downloading SC4SNMP Install Script: $URL"
  curl -s -# "$URL" > "$script_file" || exit
  chmod 775 "$script_file"

  echo "Running install script from: $script_file"
  bash "$script_file" "$@"
}

if { command true < /dev/tty; } > /dev/null 2>&1; then
  # Grab prompt input from the tty.
  download "$@" < /dev/tty
else
  download "$@"
fi

