FROM python:3.7-alpine3.7

# Install dependencies
COPY requirements.txt setup.py /tmp/

RUN addgroup agent && adduser -s /bin/bash -D -G agent agent && \
	apk --update add gcc musl-dev libffi-dev libxml2-dev libxslt-dev libressl-dev bash git subversion openssh-client gettext && \
	cd /tmp/ && \
	PYGOBJECT_WITHOUT_PYCAIRO=1 pip install --no-build-isolation -r requirements.txt && \
	pip install -I 'python-gitlab>=1.10.0'

# Install gatherer
COPY gatherer/ /tmp/gatherer/

RUN cd /tmp && python setup.py install && \
	apk del gcc musl-dev libffi-dev libressl-dev && rm -rf /var/cache/apk/* /tmp /root/.cache

# Configure agent environment
COPY VERSION *.cfg.example jira_fields.json en[v] /home/agent/
COPY certs/ /home/agent/certs/
COPY scraper/ /home/agent/scraper/
COPY subversion-servers /home/agent/.subversion/servers

RUN mkdir -p /home/agent/.ssh && \
	chown -R agent:agent /home/agent/.ssh && \
	chmod -R 400 /home/agent/.ssh && \
	chmod 700 /home/agent/.ssh && \
	mkdir -p /home/agent/export && \
	chown -R agent:agent /home/agent/export && \
	chmod -R 755 /home/agent/export && \
	chmod +x /home/agent/scraper/agent/*.sh && \
	touch /home/agent/env && \
	chown agent:agent /home/agent/env && \
	mkdir /home/agent/config && \
	touch /home/agent/config/env && \
	chown -R agent:agent /home/agent/config && \
	chmod -R 755 /home/agent/config && \
	cp /home/agent/scraper/agent/env.sh /home/agent/env.sh

VOLUME /home/agent/export
VOLUME /home/agent/config
VOLUME /home/agent/.ssh
WORKDIR /home/agent

ENV GATHERER_SETTINGS_FILE="/home/agent/config/settings.cfg" \
    GATHERER_CREDENTIALS_FILE="/home/agent/config/credentials.cfg"

# Set up server
EXPOSE 7070

CMD ["/bin/bash", "/home/agent/scraper/agent/init.sh"]
