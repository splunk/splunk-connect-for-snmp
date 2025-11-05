create_splunk_indexes() {
  index_names=("netmetrics" "em_metrics" "netops" "em_logs")
  index_types=("metric" "metric" "event" "event")
  for index in "${!index_names[@]}" ; do
    if ! curl -k -u admin:"changeme2" "https://localhost:8089/services/data/indexes" \
      -d datatype="${index_types[${index}]}" -d name="${index_names[${index}]}" ; then
      echo "Error when creating ${index_names[${index}]} of type ${index_types[${index}]}"
    fi
  done
}

create_splunk_hec() {
  if ! curl -k -u admin:changeme2 https://localhost:8089/servicesNS/admin/splunk_httpinput/data/inputs/http -d name=some_name | grep "token" | cut -c 29-64 > hec_token ; then
    echo "Error when creating ${index_names[${index}]} of type ${index_types[${index}]}"
  fi
}

change_min_free_space() {
  DOCKER_ID=$(sudo docker ps | grep 'splunk/splunk:latest' | awk '{ print $1 }')
  sudo docker exec --user splunk "$DOCKER_ID" bash -c "echo -e '\n[diskUsage]\nminFreeSpace = 2000' >> /opt/splunk/etc/system/local/server.conf"
  curl -k -u admin:changeme2 https://localhost:8089/services/server/control/restart -X POST
  sleep 60
}

change_min_free_space
create_splunk_indexes
create_splunk_hec
