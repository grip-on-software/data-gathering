"""
Script to obtain the base names of all metrics used in HQ.
"""

import argparse
import json
from gatherer.config import Configuration
from gatherer.log import Log_Setup
from gatherer.request import Session

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = 'Obtain quality metrics base names'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--url', default=config.get("metrics", "url"),
                        help='URL to retrieve HQ meta data from')
    parser.add_argument('--file', default='metrics_base_names.json',
                        help='Output file name')

    Log_Setup.add_argument(parser)
    Log_Setup.add_upload_arguments(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def main():
    """
    Main entry point.
    """

    args = parse_args()
    meta_data = Session().get(args.url).json()
    base_names = [metric["id"] for metric in meta_data["metrics"]]
    with open(args.file, 'w') as output_file:
        json.dump(base_names, output_file)

if __name__ == '__main__':
    main()
