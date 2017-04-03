FROM python:3.6-alpine

COPY *.py *.py.export *.py.update requirements.txt *.cfg.example topdesk.cfg jenkins-scraper.sh jira_fields.json /home/agent/
COPY gatherer/ /home/agent/gatherer/

RUN addgroup agent && adduser -s /bin/bash -D -G agent agent
RUN apk --update add gcc musl-dev libxml2-dev libxslt-dev bash git subversion openssh-client sshfs openvpn gettext
RUN pip install -r /home/agent/requirements.txt
RUN apk del gcc musl-dev && rm -rf /var/cache/apk/* /tmp/

VOLUME /home/agent/.ssh
WORKDIR /home/agent

USER agent

# Update configuration based on docker compose environment variables.
# Then run a dummy command to keep the container running until stopped
CMD ["/bin/bash", "-c", "(find /home/agent -name '*.cfg.example' | while read file; do envsubst < $file > ${file%.*}; done); python -c 'import signal;signal.pause()'"]
