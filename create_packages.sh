#!/bin/bash

export DOCKER_DEFAULT_PLATFORM=linux/amd64
combine_image_name(){
  #Function to combine registry, repository and tag
  # into one image, so that it can be pulled by docker

  image_registry=$1
  image_repository=$2
  image_tag=$3
  app_version=$4

  if [ -n "$image_registry" ];
  then
    result="$result""$image_registry/"
  fi

  if [ -n "$image_repository" ];
  then
    result="$result""$image_repository"
    if [ -n "$image_tag" ];
    then
      result="$result":"$image_tag"
    elif [ -n "$app_version" ];
    then
      result="$result":"$app_version"
    fi
    echo "$result"
  else
    echo ""
  fi
}

images_to_pack=""
pull_image(){
  #Function to pull image required for specified chart

  chart_dir="$1"
  if [ -d "$chart_dir" ] && { [ -a "$chart_dir/Chart.yaml" ] || [ -a "$chart_dir/Chart.yml" ]; } && { [ -a "$chart_dir/values.yaml" ] || [ -a "$chart_dir/values.yml" ]; }
  then
    if [ -a "$chart_dir/Chart.yaml" ]
    then
      chart_file="$chart_dir/Chart.yaml"
    else
      chart_file="$chart_dir/Chart.yml"
    fi

    if [ -a "$chart_dir/values.yaml" ]
    then
      values_file="$chart_dir/values.yaml"
    else
      values_file="$chart_dir/values.yml"
    fi

    #Get all the lines with information about docker image from values.yaml
    docker_info=$(sed -nE '/^image:/,/^[a-zA-Z#]/p' "$values_file")

    #Get appVersion from Chart.yaml in case there is no tag specified in values.yaml
    app_version=$(grep -Eo 'appVersion:\s\S+$' "$chart_file" | cut -d : -f2 | xargs)

    image_registry=$(grep -Eo 'registry:\s\S+$' <<< "$docker_info" | cut -d : -f2 | xargs)
    image_repository=$(grep -Eo 'repository:\s\S+$' <<< "$docker_info" | cut -d : -f2 | xargs)
    image_tag=$(grep -Eo 'tag:\s\S+$' <<< "$docker_info" | cut -d : -f2 | xargs)

    docker_pull_image=""
    docker_pull_image=$(combine_image_name "$image_registry" "$image_repository" "$image_tag" "$app_version")

    if [ -z "$docker_pull_image" ]
    then
      echo "No image to pull"
      exit 0
    fi

    echo "Pulling: $docker_pull_image"
    docker pull "$docker_pull_image"
    images_to_pack="$images_to_pack""$docker_pull_image "

    #For mongodb we need one more image from values.yaml
    if [[ "$chart_dir" == *"mongodb"* ]]
    then
      docker_pull_image=""
      metrics_info=$(sed -nE '/^metrics:/,/^[a-zA-Z#]/p' "$values_file")
      docker_info=$(sed -nE '/image:/,/[#]/p' <<< "$metrics_info")

      image_registry=$(grep -Eo 'registry:\s\S+$' <<< "$docker_info" | cut -d : -f2 | xargs)
      image_repository=$(grep -Eo 'repository:\s\S+$' <<< "$docker_info" | cut -d : -f2 | xargs)
      image_tag=$(grep -Eo 'tag:\s\S+$' <<< "$docker_info" | cut -d : -f2 | xargs)

      docker_pull_image=$(combine_image_name "$image_registry" "$image_repository" "$image_tag" "$app_version")

      printf "\n"
      if [ -z "$docker_pull_image" ]
      then
        echo "No image to pull"
        exit 0
      fi
      echo "Pulling: ""$docker_pull_image"
      docker pull "$docker_pull_image"
      images_to_pack="$images_to_pack""$docker_pull_image "
    fi
    printf "\n\n"
  else
    echo "Invalid directory"
    exit 0
  fi
}


helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add pysnmp-mibs https://pysnmp.github.io/mibs/charts
helm dependency build charts/splunk-connect-for-snmp
helm package charts/splunk-connect-for-snmp -d /tmp/package
cd /tmp/package || exit
SPLUNK_FILE=$(ls)
tar -xvf "$SPLUNK_FILE"

DIRS=$(ls)
SPLUNK_DIR=""
for d in $DIRS
do
  #Find a directory name to the unpacked splunk chart
  if [[ "$d" =~ splunk.* ]] && [[ ! "$d" =~ .+\.tgz$ ]] && [[ ! "$d" =~ .+\.tar$ ]]
  then
    SPLUNK_DIR="$d"
  fi
done
if [ -z "$SPLUNK_DIR" ]
then
  exit
fi
cd "$SPLUNK_DIR" || exit

rm -rf charts
mkdir charts
helm dep update
cd charts || exit

#Unpack charts and delete .tgz files
FILES=$(ls)
for f in $FILES
do
  tar -xvf "$f"
  rm "$f"
done

#Pull images from charts
DIRS=$(ls)
for d in $DIRS
do
  pull_image "$d"
done

mkdir /tmp/package/packages
docker save $images_to_pack > /tmp/package/packages/dependencies-images.tar
cd ../..
tar -czvf packages/splunk-connect-for-snmp-chart.tar splunk-connect-for-snmp