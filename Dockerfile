FROM python:3.6-alpine

COPY requirements.txt /tmp/

RUN addgroup agent && adduser -s /bin/bash -D -G agent agent && \
	apk --update add gcc musl-dev libxml2-dev libxslt-dev bash git subversion openssh-client gettext && \
	pip install -r /tmp/requirements.txt && \
	apk del gcc musl-dev && rm -rf /var/cache/apk/* /tmp/

VOLUME /home/agent/.ssh
WORKDIR /home/agent

COPY *.py *.py.export *.py.update requirements.txt *.cfg.example topdesk.cfg jenkins-scraper.sh jira_fields.json /home/agent/
COPY certs/ /home/agent/certs/
COPY gatherer/ /home/agent/gatherer/

USER agent

# Update configuration based on docker compose environment variables.
# Then run a dummy command to keep the container running until stopped
CMD ["/bin/bash", "-c", "(find /home/agent -name '*.cfg.example' | while read file; do envsubst < $file > ${file%.*}; done); python generate_key.py $JIRA_KEY; python -c 'import signal;signal.pause()'"]
