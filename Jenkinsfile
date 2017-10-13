pipeline {
    agent { label 'docker' }

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
                updateGitlabCommitStatus name: env.JOB_NAME, state: 'running'
                withCredentials([file(credentialsId: 'upload-server-certificate', variable: 'SERVER_CERTIFICATE')]) {
                    sh 'rm -f certs/wwwgros.crt'
                    sh 'cp $SERVER_CERTIFICATE certs/wwwgros.crt'
                    sh 'chmod 444 certs/wwwgros.crt'
                    sh 'docker build -t $DOCKER_REGISTRY/gros-data-gathering .'
                }
            }
        }
        stage('Push') {
            when { branch 'master' }
            steps {
                sh 'docker push $DOCKER_REGISTRY/gros-data-gathering:latest'
            }
        }
        stage('Test') {
            agent {
                docker {
                    image '$DOCKER_REGISTRY/gros-data-gathering'
                    args '-u root -v $PWD/.pylintrc:/home/agent/.pylintrc -v $PWD/.isort.cfg:/home/agent/.isort.cfg'
                }
            }
            steps {
                sh 'apk --update add gcc musl-dev'
                sh 'pip install pylint regex'
                sh 'pylint --disable=duplicate-code --reports=n /home/agent/*.py /home/agent/gatherer/'
            }
        }
    }
}
