#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Exit immediately if a command tries to use an unset variable
set -o nounset

function install-prereq {
    # Install Java
    cd --
    sudo apt-get update && \
    sudo apt-get install java-common vlan git zip curl python python-pip python3 pkg-config g++ zlib1g-dev unzip -y
    wget https://d3pxv6yz143wms.cloudfront.net/8.212.04.2/java-1.8.0-amazon-corretto-jdk_8.212.04-2_amd64.deb
    sudo dpkg -i java-1.8.0-amazon-corretto-jdk_8.212.04-2_amd64.deb
    rm java-1.8.0-amazon-corretto-jdk_8.212.04-2_amd64.deb

    # Install Maven
    sudo apt-get install maven -y

    # Install Bazel
    cd --
    wget https://github.com/bazelbuild/bazel/releases/download/0.23.2/bazel-0.23.2-installer-linux-x86_64.sh
    chmod +x bazel-0.23.2-installer-linux-x86_64.sh
    ./bazel-0.23.2-installer-linux-x86_64.sh --user
    rm bazel-0.23.2-installer-linux-x86_64.sh
    echo "export PATH=\"$PATH:$HOME/bin\"" >> ~/.sfile

    # Install Mininet
    sudo apt-get install mininet -y
}

function download-onos {
    # Download ONOS
    cd --
    git clone https://gerrit.onosproject.org/onos
    cd onos
    git checkout onos-1.15
    echo "export ONOS_ROOT=~/onos" >> ~/.sfile
    source ~/.sfile
}

function install-onos-ifwd {
    cd --
    cd distributed-network-federation-probe/ifwd
    mvn clean install
}

function download-onos-opa {
    cd --
    git clone https://github.com/eubr-atmosphere/distributed-network-federation-probe
    cd distributed-network-federation-probe
    export LC_ALL=C
    sudo pip install -r requirements.txt

    # Patching IMR to (auto)submit PointToPointIntent with suggested paths
    cd $ONOS_ROOT
    git apply ../onos-opa/misc/imr.patch
}

install-prereq
download-onos
download-onos-opa
install-onos-ifwd

echo  "source \${ONOS_ROOT}/tools/dev/bash_profile" >> ~/.sfile
cat ~/.sfile >> ~/.bashrc
rm ~/.sfile

echo "Ready!"
