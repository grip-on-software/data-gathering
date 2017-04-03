FROM python:2.7-alpine

COPY *.py *.py.export *.py.update *.cfg requirements.txt jenkins-scraper.sh jira_fields.json dropins/ /home/agent/

RUN addgroup agent && adduser -s /bin/bash -D -G agent agent
RUN apk --update add gcc musl-dev libxml2-dev libxslt-dev bash git subversion openssh-client \
    && pip install -r /home/agent/requirements.txt \
    && apk del gcc musl-dev  \
    && rm -rf /var/cache/apk/* /tmp/


VOLUME /home/agent/.ssh

USER agent
