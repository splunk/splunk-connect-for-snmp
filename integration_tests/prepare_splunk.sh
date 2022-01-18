create_splunk_indexes() {
  index_names=("netmetrics" "netops")
  index_types=("metric" "event")
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

create_splunk_indexes
create_splunk_hec
