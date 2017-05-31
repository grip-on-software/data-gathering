"""
Script to export the export and update files to the controller server.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import subprocess
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = argparse.ArgumentParser(description='Export data and update files')
    parser.add_argument('project', help='project key to export')
    parser.add_argument('--path', default='~/.ssh/id_rsa',
                        help='local path of the private key')
    parser.add_argument('--agent', default=config.get('ssh', 'username'),
                        help='agent username for the ssh source')
    parser.add_argument('--server', default=config.get('ssh', 'host'),
                        help='host name of the ssh source')
    parser.add_argument('--update', nargs='+', default=[],
                        help='update tracker files to consider')
    parser.add_argument('--export', nargs='+', default=[],
                        help='data files to consider for export')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)

    return args

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    auth = args.agent + '@' + args.server
    path = '{}:~/{}'.format(auth, project.export_key)

    for filename in args.export + args.update:
        subprocess.call([
            'scp', '-i', args.path,
            '{}/{}'.format(project.export_key, filename),
            '{}/{}'.format(path, filename)
        ])

if __name__ == "__main__":
    main()
