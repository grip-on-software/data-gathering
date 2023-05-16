"""
API to determine whether access should be granted to data for certain projects
to a user.

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

import cgitb
import ipaddress
import json
import os
from typing import List, Union
from gatherer.config import Configuration

def is_in_networks(address: Union[ipaddress.IPv4Address, ipaddress.IPv6Address],
                   nets: str) -> bool:
    """
    Check if an IP address object `address` is part of any of the networks
    defined by their CIDR ranges in the comma-separated `nets` string.
    """

    networks = set(ipaddress.ip_network(net.strip()) for net in nets.split(','))
    return any(address in network for network in networks)

def get_accessible_projects() -> List[str]:
    """
    Retrieve a list of projects that the user is allowed to access. The list
    contains the special value '*' if access to all projects is allowed or if
    the access is not configured.
    """

    config = Configuration.get_settings()

    if not config.has_option('access', '*'):
        return ['*']

    address = ipaddress.ip_address(os.getenv('REMOTE_ADDR', '127.0.0.1'))
    forwarded = os.getenv('HTTP_X_FORWARDED_FOR')
    if forwarded is not None:
        nets = config.get('access', '_')
        for via_address in reversed(forwarded.split(', ')):
            via_ip = ipaddress.ip_address(via_address)
            if not is_in_networks(via_ip, nets):
                address = via_ip
                break

    projects = []
    for group, nets in config.items('access'):
        if is_in_networks(address, nets):
            projects.append(group.upper())

    return projects

def setup_log() -> None:
    """
    Set up logging.
    """

    cgitb.enable()

def main() -> None:
    """
    Main entry point.
    """

    setup_log()
    projects = get_accessible_projects()

    print('Content-type: application/json')
    print()
    print(json.dumps(projects))

if __name__ == "__main__":
    main()
