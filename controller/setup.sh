#!/bin/bash -e

cp controller/{pyro-ns,gros-controller,gros-gatherer,gros-exporter}.service /etc/systemd/system/
ln -s controller/export.sh /usr/local/bin/controller-export.sh
ln -s controller/upload.sh /usr/local/bin/upload.sh
ln -s controller/virtualenv.sh /usr/local/bin/virtualenv.sh
ln -s controller/controller_daemon.py /usr/local/bin/controller-daemon.py
ln -s controller/exporter_daemon.py /usr/local/bin/exporter-daemon.py
ln -s controller/gatherer_daemon.py /usr/local/bin/gatherer-daemon.py
systemctl enable {pyro-ns,gros-controller,gros-gatherer,gros-exporter}
systemctl start {pyro-ns,gros-controller,gros-gatherer,gros-exporter}
