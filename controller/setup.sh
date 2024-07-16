#!/bin/bash -e

# Script to set up the controller directories, users, daemons and services.
#
# Copyright 2017-2020 ICTU
# Copyright 2017-2022 Leiden University
# Copyright 2017-2024 Leon Helwerda
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

if [ -z $SUDO_USER ]; then
	echo "Usage: sudo ./controller/setup.sh" >&2
	echo "Set up the controller directories, users, daemons and services" >&2
	exit 1
fi

REPO_PATH=/srv/data-gathering
if [ ! -d "$REPO_PATH" ] || [ "$PWD" != "$REPO_PATH" ]; then
	echo "Usage: sudo ./controller/setup.sh" >&2
	echo "Data gathering repository must be cloned to $REPO_PATH" >&2
	exit 1
fi

# Copy services
cp controller/{pyro-ns,gros-controller,gros-gatherer,gros-exporter}.service /etc/systemd/system/
# Set up symlinks for controller scripts and daemons
ln -s controller/export.sh /usr/local/bin/controller-export.sh
ln -s controller/upload.sh /usr/local/bin/upload.sh
ln -s controller/virtualenv.sh /usr/local/bin/virtualenv.sh
ln -s controller/controller_daemon.py /usr/local/bin/controller-daemon.py
ln -s controller/exporter_daemon.py /usr/local/bin/exporter-daemon.py
ln -s controller/gatherer_daemon.py /usr/local/bin/gatherer-daemon.py
# Set up services
systemctl enable {pyro-ns,gros-controller,gros-gatherer,gros-exporter}
systemctl start {pyro-ns,gros-controller,gros-gatherer,gros-exporter}
# Create users and groups
useradd -M -d / -s /sbin/nologin pyro-ns
useradd -M -d / -s /sbin/nologin controller
useradd -M -N -d / -s /sbin/nologin -g controller exporter
useradd -M -N -d / -s /sbin/nologin -g controller gatherer
cp controller/sudoers /etc/sudoers.d/99_gros_controller
# Set up directories
mkdir /agents
chown root:controller /agents
mkdir /etc/ssh/control
chown root:controller /etc/ssh/control
mkdir /controller
chown controller:controller /controller
# Install dependencies in virtual environment
/usr/local/bin/virtualenv.sh /usr/local/envs/controller -m pip install requirements-daemon.txt
/usr/local/bin/virtualenv.sh /usr/local/envs/controller -m pip install .
chown controller:controller -R /usr/local/envs/controller
