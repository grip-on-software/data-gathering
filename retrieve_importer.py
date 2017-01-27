"""
Script for downloading the Java database importer from a URL and extracting it
such that the Jenkins scraper can run all programs.
"""

import ConfigParser
import os
import shutil
from zipfile import ZipFile
# Not-standard imports
import requests

def main():
    """
    Main entry point.
    """

    config = ConfigParser.RawConfigParser()
    config.read("settings.cfg")

    jenkins_url = config.get('importer', 'url')

    request = requests.get(jenkins_url, stream=True)
    with open('dist.zip', 'wb') as output_file:
        for chunk in request.iter_content(chunk_size=128):
            output_file.write(chunk)

    with ZipFile('dist.zip', 'r') as dist_zip:
        dist_zip.extractall()

    if os.path.exists('lib'):
        shutil.rmtree('lib')

    shutil.move('dist/importerjson.jar', 'importerjson.jar')
    shutil.move('dist/data_gitdev_to_dev.json', 'data_gitdev_to_dev.json')
    shutil.move('dist/lib/', '.')
    shutil.rmtree('dist')
    os.remove('dist.zip')

if __name__ == "__main__":
    main()
