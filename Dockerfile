FROM python:3.6-alpine

COPY requirements.txt /tmp/

RUN addgroup agent && adduser -s /bin/bash -D -G agent agent && \
	apk --update add gcc musl-dev libxml2-dev libxslt-dev bash git subversion openssh-client gettext && \
	pip install -r /tmp/requirements.txt && \
	apk del gcc musl-dev && rm -rf /var/cache/apk/* /tmp/

COPY *.py *.py.export *.py.update requirements.txt *.cfg.example topdesk.cfg *.sh jira_fields.json /home/agent/
COPY certs/ /home/agent/certs/
COPY gatherer/ /home/agent/gatherer/

RUN mkdir -p /home/agent/.ssh && \
	chown -R agent:agent /home/agent/.ssh && \
	chmod -R 700 /home/agent/.ssh && \
	chmod +x /home/agent/*.sh

WORKDIR /home/agent

CMD ["/bin/bash", "docker-init.sh"]
