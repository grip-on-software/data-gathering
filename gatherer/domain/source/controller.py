"""
Agent controller source domain object.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
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
        base_url = self.url.rstrip('/')
        url = f'{base_url}/agent.py?project={project.key}&agent={agent_key}'
        logging.info('Updating key via controller API at %s', url)
        if dry_run:
            return

        data = {'public_key': public_key}
        request = Session(verify=self.certificate).post(url, data=data)

        if not Session.is_code(request, 'ok'):
            raise RuntimeError(f'HTTP error {request.status_code}: {request.text}')

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

        with open('secrets.json', 'w', encoding='utf-8') as secrets_file:
            json.dump(secrets, secrets_file)
