"""
Perform pre-flight checks for the Docker agent scraper.
"""

from argparse import ArgumentParser, Namespace
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Union
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup
from gatherer.request import Session
from gatherer.utils import convert_local_datetime

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = ArgumentParser(description='Perform pre-flight checks')
    parser.add_argument('project', help='project key to check for')
    parser.add_argument('--secrets', default='secrets.json',
                        help='Path to the secrets file')
    parser.add_argument('--no-secrets', action='store_false', dest='secrets',
                        help='Do not require a secrets file')
    parser.add_argument('--ssh', default=config.get('ssh', 'host'),
                        help='Controller API host to check')
    parser.add_argument('--no-ssh', action='store_false', dest='ssh',
                        help='Do not check controller API host')
    parser.add_argument('--cert', default=config.get('ssh', 'cert'),
                        help='HTTPS certificate of controller API host')
    parser.add_argument('--skip', action='store_true', dest='skip',
                        default=False, help='Ignore the preflight checks')
    Log_Setup.add_argument(parser)

    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def write_configuration(project: Project, response: Dict[str, Any]) -> None:
    """
    Write an environment file based on the response from the controller.
    """

    if 'configuration' in response and 'contents' in response['configuration']:
        env_filename = project.export_key / 'preflight_env'
        with open(env_filename, 'w') as env_file:
            env_file.write(response['configuration']['contents'])

def check_secrets(path: Path) -> bool:
    """
    Check whether the secrets file contains all required options.
    """

    with path.open('r') as secrets_file:
        secrets: Dict[str, Dict[str, str]] = json.load(secrets_file)
        if 'salts' in secrets and \
            'salt' in secrets['salts'] and 'pepper' in secrets['salts']:
            return True

        logging.critical('Secrets file %s does not contain salts', path)
        return False

def check_controller(host: str, cert: str, project: Project) -> List[str]:
    """
    Check availability of the controller API host and services.
    """

    agent_key = Configuration.get_agent_key()
    url = f'https://{host}/auth/status.py?project={project.jira_key}&agent={agent_key}'
    session = Session(verify=cert)
    request = session.get(url)

    try:
        response: Dict[str, Dict[str, Union[bool, str]]] = \
            json.loads(request.text)
    except ValueError:
        logging.exception('Invalid JSON response from controller API: %s',
                          request.text)
        return ['controller-format']

    if Session.is_code(request, 'service_unavailable') and 'total' in response:
        problems = ['controller-service-unavailable']
        for key, value in response.items():
            if key != 'total' and not value['ok']:
                message = value.get('message', 'Not OK')
                problems.append("Status '{}': {}".format(key, message))

        logging.warning('Controller status: %s: %s',
                        response['total']['message'], ', '.join(problems))
        return problems

    if not Session.is_code(request, 'ok'):
        logging.critical('Unexpected HTTP error %d for controller status',
                         request.status_code, extra=response)
        return ['controller-http']

    write_configuration(project, response)

    return []

def perform_checks(args: Namespace, project: Project) -> List[str]:
    """
    Perform pre-flight checks for the agent.

    - Does the controller API indicate that all is OK?
    - Do we have a populated secrets file?

    Returns a list of checks that were not satisfied.
    """

    errors: List[str] = []
    if args.secrets:
        secrets = Path(args.secrets)
        if not secrets.exists():
            logging.critical('Secrets file %s is not available', secrets)
            errors.append('secrets-missing')
        elif not check_secrets(secrets):
            errors.append('secrets-format')

    if args.ssh:
        errors.extend(check_controller(args.ssh, args.cert, project))

    return errors

def main() -> int:
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    project.make_export_directory()
    errors = perform_checks(args, project)
    logging.info('Failed checks: %s', ', '.join(errors))
    if errors and not args.skip:
        return 1

    date_path = project.export_key / 'preflight_date.txt'
    with date_path.open('w') as date_file:
        date_file.write(convert_local_datetime(datetime.now()).isoformat())

    return 0

if __name__ == '__main__':
    sys.exit(main())
