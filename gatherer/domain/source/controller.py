"""
Agent controller source domain object.
"""

import logging
import json
from ...config import Configuration
from ...request import Session
from .types import Source, Source_Types

@Source_Types.register('controller')
class Controller(Source):
    """
    Agent controller source.
    """

    def __init__(self, *args, **kwargs):
        if 'certificate' in kwargs:
            self._certificate = kwargs.pop('certificate')
        else:
            self._certificate = None

        super(Controller, self).__init__(*args, **kwargs)

    @property
    def environment(self):
        return self.url.rstrip('/')

    @property
    def certificate(self):
        """
        Retrieve the local path to the certificate to verify the source against.
        """

        return self._certificate

    def update_identity(self, project, public_key, dry_run=False):
        agent_key = Configuration.get_agent_key()
        url = '{}/agent.py?project={}&agent={}'.format(self.url.rstrip('/'),
                                                       project.key,
                                                       agent_key)
        logging.info('Updating key via controller API at %s', url)
        if dry_run:
            return

        data = {'public_key': public_key}
        request = Session(verify=self.certificate).post(url, data=data)

        if not Session.is_code(request, 'ok'):
            raise RuntimeError('HTTP error {}: {}'.format(request.status_code, request.text))

        # In return for our public key, we may receive some secrets (salts).
        # Export these to a file since the data is never received again.
        try:
            response = json.loads(request.text)
        except ValueError:
            logging.exception('Invalid JSON response from controller API: %s',
                              request.text)
            return

        self._export_secrets(response)

    @staticmethod
    def _export_secrets(secrets):
        """
        Write a JSON file with secrets according to a dictionary structure
        received from the controller API.
        """

        with open('secrets.json', 'w') as secrets_file:
            json.dump(secrets, secrets_file)
