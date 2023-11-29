#!/bin/bash

export DOCKER_DEFAULT_PLATFORM=linux/amd64
python_script=$1
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
pull_dependencies_images_sc4snmp(){
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

    app_version=$(python3 "$python_script" "$chart_file" "appVersion")
    image_registry=$(python3 "$python_script" "$values_file" "image.registry")
    image_repository=$(python3 "$python_script" "$values_file" "image.repository")
    image_tag=$(python3 "$python_script" "$values_file" "image.tag")

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
      image_registry=$(python3 "$python_script" "$values_file" "metrics.image.registry")
      image_repository=$(python3 "$python_script" "$values_file" "metrics.image.repository")
      image_tag=$(python3 "$python_script" "$values_file" "metrics.image.tag")

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

      docker_pull_image=""
      image_registry=$(python3 "$python_script" "$values_file" "volumePermissions.image.registry")
      image_repository=$(python3 "$python_script" "$values_file" "volumePermissions.image.repository")
      image_tag=$(python3 "$python_script" "$values_file" "volumePermissions.image.tag")

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

images_ui_to_pack=""
pull_ui_images() {
  chart_dir="$1"
  if [ -d "$chart_dir" ] && { [ -a "$chart_dir/values.yaml" ] || [ -a "$chart_dir/values.yml" ]; }
  then
    if [ -a "$chart_dir/values.yaml" ]
    then
      values_file="$chart_dir/values.yaml"
    else
      values_file="$chart_dir/values.yml"
    fi
    backend_image_repository=$(python3 "$python_script" "$values_file" "UI.backEnd.repository")
    backend_image_tag=$(python3 "$python_script" "$values_file" "UI.backEnd.tag")
    docker_pull_image=$(combine_image_name "" "$backend_image_repository" "$backend_image_tag" "")
    echo "docker pull $docker_pull_image" >> /tmp/package/packages/pull_gui_images.sh
    images_ui_to_pack="$images_ui_to_pack""$docker_pull_image "

    frontend_image_repository=$(python3 "$python_script" "$values_file" "UI.frontEnd.repository")
    frontend_image_tag=$(python3 "$python_script" "$values_file" "UI.frontEnd.tag")
    docker_pull_image=$(combine_image_name "" "$frontend_image_repository" "$frontend_image_tag" "")
    echo "docker pull $docker_pull_image" >> /tmp/package/packages/pull_gui_images.sh
    images_ui_to_pack="$images_ui_to_pack""$docker_pull_image "

    init_image_repository=$(python3 "$python_script" "$values_file" "UI.init.repository")
    docker_pull_image=$(combine_image_name "" "$init_image_repository" "" "")
    echo "docker pull $docker_pull_image" >> /tmp/package/packages/pull_gui_images.sh
    images_ui_to_pack="$images_ui_to_pack""$docker_pull_image "

    echo "docker save $images_ui_to_pack > sc4snmp-gui-images.tar" >> /tmp/package/packages/pull_gui_images.sh
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

mkdir /tmp/package/packages

# Export script to pull mibserver
MIBSERVER_VERSION=$(grep -A2 'mibserver' Chart.lock | grep version | cut -d : -f2 | xargs)
MIBSERVER_IMAGE="ghcr.io/pysnmp/mibs/container:$MIBSERVER_VERSION"
echo "docker pull $MIBSERVER_IMAGE" > pull_mibserver.sh
echo "docker save $MIBSERVER_IMAGE > mibserver.tar" >> pull_mibserver.sh
cp pull_mibserver.sh /tmp/package/packages

rm -rf charts
mkdir charts
helm dep update
cd charts || exit

#Unpack dependencies charts and delete .tgz files
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
  if [ "$d" != "mibserver" ]; then
    full_dir=$(pwd)"/$d"
    pull_dependencies_images_sc4snmp "$full_dir"
  fi
done

pull_ui_images "/tmp/package/$SPLUNK_DIR"
docker save $images_to_pack > /tmp/package/packages/dependencies-images.tar
cd ../..
tar -czvf packages/splunk-connect-for-snmp-chart.tar splunk-connect-for-snmp

# Download and pack image for sim
cd "$SPLUNK_DIR" || exit

# Check if there is a value for sim docker image in values.yaml
# If not, get default image from templates/sim/deployment.yaml

if [ -f "values.yaml" ]
then
  values_file="values.yaml"
else
  values_file="values.yml"
fi

docker_link=$(python3 "$python_script" "$(pwd)/$values_file" "sim.image")
docker_tag=$(python3 "$python_script" "$(pwd)/$values_file" "sim.tag")


if [ -z "$docker_link" ]
then
  cd templates/sim || exit
  if [ -f "deployment.yaml" ]
  then
    depl_file="deployment.yaml"
  else
    depl_file="deployment.yml"
  fi
  docker_info=$(grep image: "$depl_file")

  docker_link=$(cut -d : -f2 <<< "$docker_info" | grep -oE '".+"')
  docker_link="${docker_link#?}"
  docker_link="${docker_link%?}"

  docker_tag=$(cut -d : -f3 <<< "$docker_info" | grep -oE '".+"')
  docker_tag="${docker_tag#?}"
  docker_tag="${docker_tag%?}"
fi

if [ -z "$docker_tag" ]
then
  docker_image_pull="$docker_link"
else
  docker_image_pull="$docker_link:$docker_tag"
fi

docker pull "$docker_image_pull"
docker save $docker_image_pull > /tmp/package/packages/sim_image.tar

# Download and package otel charts
cd /tmp/package/packages/ || exit
LOCATION=$(curl -s https://api.github.com/repos/signalfx/splunk-otel-collector-chart/releases/latest | grep "zipball_url" | awk '{ print $2 }' | sed 's/,$//' | sed 's/"//g' )
curl -L -o otel-repo.zip $LOCATION
unzip otel-repo.zip
rm otel-repo.zip
OTEL_DIR=$(pwd)"/"$(ls | grep -E "signalfx-splunk.+")
CHART_DIR="$OTEL_DIR/helm-charts/splunk-otel-collector"
OTEL_IMAGE_TAG=$(python3 "$python_script" "$CHART_DIR/Chart.yaml" "appVersion")
otel_image=quay.io/signalfx/splunk-otel-collector:"$OTEL_IMAGE_TAG"
cd "$CHART_DIR" || exit
helm dep update
cd charts || exit

#Unpack dependencies charts and delete .tgz files
FILES=$(ls)
for f in $FILES
do
  tar -xvf "$f"
  rm "$f"
done

docker pull "$otel_image"
docker save "$otel_image" > /tmp/package/packages/otel_image.tar
cd "$OTEL_DIR" || exit
helm package "$CHART_DIR" -d /tmp/package/packages/
cd .. || exit
rm -rf "$OTEL_DIR"
