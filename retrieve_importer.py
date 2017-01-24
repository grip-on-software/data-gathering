import os
import requests
import shutil
from zipfile import ZipFile

def main():
    jenkins_url = 'http://www.JENKINS_SERVER.localhost:8080/view/GROS/job/build-importerjson/lastSuccessfulBuild/artifact/Code/importerjson/dist/*zip*/dist.zip'
    request = requests.get(jenkins_url, stream=True)
    with open('dist.zip', 'wb') as f:
        for chunk in request.iter_content(chunk_size=128):
            f.write(chunk)

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
