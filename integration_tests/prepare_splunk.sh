create_splunk_indexes() {
  splunk_ip=$1
  splunk_password=$2
  index_names=("netmetrics" "netops")
  index_types=("metric" "event")
  for index in "${!index_names[@]}" ; do
    if ! curl -k -u admin:"changeme" "https://localhost:8089/services/data/indexes" \
      -d datatype="${index_types[${index}]}" -d name="${index_names[${index}]}" ; then
      echo "Error when creating ${index_names[${index}]} of type ${index_types[${index}]}"
    fi
  done
}



create_splunk_indexes