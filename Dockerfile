FROM python:3.6-alpine

COPY requirements.txt /tmp/

RUN addgroup agent && adduser -s /bin/bash -D -G agent agent && \
	apk --update add gcc musl-dev libffi-dev libxml2-dev libxslt-dev bash git subversion openssh-client gettext && \
	pip install -r /tmp/requirements.txt && \
	apk del gcc musl-dev libffi-dev && rm -rf /var/cache/apk/* /tmp/

COPY VERSION *.py *.py.export *.py.update requirements.txt *.cfg.example *.sh jira_fields.json en[v] /home/agent/
COPY certs/ /home/agent/certs/
COPY gatherer/ /home/agent/gatherer/

RUN mkdir -p /home/agent/.ssh && \
	chown -R agent:agent /home/agent/.ssh && \
	chmod -R 700 /home/agent/.ssh && \
	mkdir -p /home/agent/export && \
	chown -R agent:agent /home/agent/export && \
	chmod -R 755 /home/agent/export && \
	chmod +x /home/agent/*.sh && \
	touch /home/agent/env && \
	chown agent:agent /home/agent/env

VOLUME /home/agent/export
VOLUME /home/agent/config
VOLUME /home/agent/.ssh
WORKDIR /home/agent

ENV GATHERER_SETTINGS_FILE="/home/agent/config/settings.cfg" \
    GATHERER_CREDENTIALS_FILE="/home/agent/config/credentials.cfg"

CMD ["/bin/bash", "docker-init.sh"]
