"""
Agent controller source domain object.
"""

import logging
import json
from typing import Any, Dict, Hashable, Optional, Union
from ...config import Configuration
from ...request import Session
from .types import Source, Source_Types, Project

@Source_Types.register('controller')
class Controller(Source):
    """
    Agent controller source.
    """

    def __init__(self, source_type: str, name: str = '', url: str = '',
                 follow_host_change: bool = True,
                 certificate: Union[str, bool] = True) -> None:
        super().__init__(source_type, name=name, url=url,
                         follow_host_change=follow_host_change)
        self._certificate = certificate

    @property
    def environment(self) -> Optional[Hashable]:
        return self.plain_url.rstrip('/')

    @property
    def certificate(self) -> Union[str, bool]:
        """
        Retrieve the local path to the certificate to verify the source against.

        If no certificate was passed, then certificate verification is enabled
        with the default certificate bundle.
        """

        return self._certificate

    def update_identity(self, project: Project, public_key: str,
                        dry_run: bool = False) -> None:
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
            response = request.json()
        except ValueError:
            logging.exception('Invalid JSON response from controller API: %s',
                              request.text)
            return

        self._export_secrets(response)

    @staticmethod
    def _export_secrets(secrets: Dict[str, Any]) -> None:
        """
        Write a JSON file with secrets according to a dictionary structure
        received from the controller API.
        """

        with open('secrets.json', 'w') as secrets_file:
            json.dump(secrets, secrets_file)
