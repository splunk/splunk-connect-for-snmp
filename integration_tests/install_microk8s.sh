#!/bin/bash

setup_kube_roles() {
  sudo usermod -a -G microk8s "$USER"
  sudo chown -f -R "$USER" ~/.kube
  echo "In order to properly configure Kubernetes, we need to logout the current shell. You might need to enter you password."
  su - "$USER"
}

install_dependencies_on_ubuntu() {
  sudo snap install microk8s --classic
  sudo snap install docker
  sudo apt-get install snmp -y
  sudo apt-get install python3-dev -y
}

install_dependencies_on_centos() {
  sudo yum -y install epel-release
  sudo yum -y install snapd
  sudo systemctl enable snapd
  sudo systemctl start snapd
  sudo ln -s /var/lib/snapd/snap /snap
  sudo snap install microk8s --classic
  sudo snap install docker
  sudo yum install net-snmp net-snmp-utils -y
  sudo yum install python3-devel -y
}

install_dependencies() {
  os_release=/etc/os-release
  if [ ! -f "$os_release" ] ; then
    echo "$os_release does not exist"
    exit 4
  fi

  os_version=$(grep "^ID=" "$os_release" | sed -e "s/\"//g" | cut -d= -f2)
  if [ "$os_version" == "ubuntu" ] ; then
    install_dependencies_on_ubuntu
  elif [ "$os_version" == "centos" ] ; then
    install_dependencies_on_centos
  else
    echo "Unsupported operating system: $os_version"
    exit 4
  fi

  if [ -z "${ANSIBLE_RUN}" ]; then
    setup_kube_roles
  fi
}

install_dependencies
