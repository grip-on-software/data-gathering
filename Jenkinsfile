pipeline {
    agent { label 'docker' }

    environment {
        AGENT_TAG = env.BRANCH_NAME.replaceFirst('^master$', 'latest')
        AGENT_IMAGE = "${env.DOCKER_REGISTRY}/gros-data-gathering:${env.AGENT_TAG}"
    }
    options {
        gitLabConnection('gitlab')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }
    triggers {
        gitlab(triggerOnPush: true, triggerOnMergeRequest: true, branchFilterType: 'All')
    }

    post {
        success {
            updateGitlabCommitStatus name: env.JOB_NAME, state: 'success'
        }
        failure {
            updateGitlabCommitStatus name: env.JOB_NAME, state: 'failed'
        }
    }

    stages {
        stage('Build') {
            steps {
                checkout scm
                updateGitlabCommitStatus name: env.JOB_NAME, state: 'running'
                withCredentials([file(credentialsId: 'upload-server-certificate', variable: 'SERVER_CERTIFICATE')]) {
                    sh 'rm -f certs/wwwgros.crt'
                    sh 'cp $SERVER_CERTIFICATE certs/wwwgros.crt'
                    sh 'chmod 444 certs/wwwgros.crt'
                    sh 'echo $(grep __version__ gatherer/__init__.py | sed -E "s/__version__ = .([0-9.]+)./\\1/")-$BRANCH_NAME-$(git show-ref $BRANCH_NAME | cut -f1 -d\' \' | head -n 1) > VERSION'
                    sh 'docker build -t $AGENT_IMAGE .'
                }
            }
        }
        stage('Test') {
            agent {
                docker {
                    image '$AGENT_IMAGE'
                    args '-u root -v $PWD/.pylintrc:/home/agent/.pylintrc -v $PWD/.isort.cfg:/home/agent/.isort.cfg'
                }
            }
            steps {
                sh 'apk --update add gcc musl-dev'
                sh 'pip install pylint regex'
                sh 'pylint --disable=duplicate-code --reports=n /home/agent/*.py /home/agent/gatherer/'
            }
        }
        stage('Push') {
            steps {
                sh 'docker push $AGENT_IMAGE'
            }
        }
    }
}
