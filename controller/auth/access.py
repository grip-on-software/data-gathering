"""
API to determine whether access should be granted to data for certain projects
to a user.
"""

from __future__ import print_function
try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import cgitb
import ipaddress
import json
import os

from gatherer.config import Configuration

def is_in_networks(address, nets):
    """
    Check if an IP address object `address` is part of any of the networks
    defined by their CIDR ranges in the comma-separated `nets` string.
    """

    networks = set(ipaddress.ip_network(net.strip()) for net in nets.split(','))
    return any(address in network for network in networks)

def get_accessible_projects():
    """
    Retrieve a list of projects that the user is allowed to access. The list
    contains the special value '*' if access to all projects is allowed or if
    the access is not configured.
    """

    config = Configuration.get_settings()

    if not config.has_option('access', '*'):
        return ['*']

    address = ipaddress.ip_address(os.getenv('REMOTE_ADDR'))
    forwarded = os.getenv('HTTP_X_FORWARDED_FOR')
    if forwarded is not None:
        nets = config.get('access', '_')
        for via_address in reversed(forwarded.split(', ')):
            via_address = ipaddress.ip_address(via_address)
            if not is_in_networks(via_address, nets):
                address = via_address
                break

    projects = []
    for group, nets in config.items('access'):
        if is_in_networks(address, nets):
            projects.append(group.upper())

    return projects

def setup_log():
    """
    Set up logging.
    """

    cgitb.enable()

def main():
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
