FROM python:2.7-alpine

COPY *.py *.py.export *.py.update requirements.txt *.cfg.example topdesk.cfg jenkins-scraper.sh jira_fields.json /home/agent/

RUN addgroup agent && adduser -s /bin/bash -D -G agent agent
RUN apk --update add gcc musl-dev libxml2-dev libxslt-dev bash git subversion openssh-client gettext
RUN ["/bin/bash", "-c", "(find /home/agent -name '*.cfg.example' | while read file; do envsubst < $file > ${file%.*}; done)"]
RUN pip install -r /home/agent/requirements.txt
RUN apk del gcc musl-dev gettext && rm -rf /var/cache/apk/* /tmp/

VOLUME /home/agent/.ssh
WORKDIR /home/agent

USER agent

# Dummy command to keep the container running until stopped
CMD ["python", "-c", "import signal;signal.pause()"]
