FROM python:3.8-alpine3.18

# Install dependencies
COPY Makefile requirements.txt requirements-agent.txt pyproject.toml /tmp/

RUN addgroup agent && adduser -s /bin/bash -D -G agent agent && \
	apk --update add gcc musl-dev libffi-dev libressl-dev bash git subversion openssh-client gettext cargo make cmake && \
	cd /tmp/ && make setup_agent

# Install gatherer
COPY gatherer/ /tmp/gatherer/

RUN cd /tmp/ && make install && \
	apk del gcc musl-dev libffi-dev libressl-dev cargo make cmake && \
	rm -rf /var/cache/apk/* /tmp /root/.cache /root/.cargo

# Configure agent environment
COPY *.cfg.example *_fields.json [V]ERSION /home/agent/
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
