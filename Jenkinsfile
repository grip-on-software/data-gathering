pipeline {
    agent { label 'docker' }

    environment {
        AGENT_TAG = env.BRANCH_NAME.replaceFirst('^master$', 'latest')
        AGENT_NAME = "${env.DOCKER_REGISTRY}/gros-data-gathering"
        AGENT_IMAGE = "${env.AGENT_NAME}:${env.AGENT_TAG}"
        SCANNER_HOME = tool name: 'SonarQube Scanner 3', type: 'hudson.plugins.sonar.SonarRunnerInstallation'
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
                    withCredentials([file(credentialsId: 'agent-environment', variable: 'AGENT_ENVIRONMENT')]) {
                        sh 'rm -f certs/wwwgros.crt'
                        sh 'cp $SERVER_CERTIFICATE certs/wwwgros.crt'
                        sh 'cp $AGENT_ENVIRONMENT env'
                        sh 'chmod 444 certs/wwwgros.crt'
                        sh 'echo $(grep __version__ gatherer/__init__.py | sed -E "s/__version__ = .([0-9.]+)./\\1/") > .version'
                        sh 'echo $(cat .version)-$BRANCH_NAME-$(git show-ref $BRANCH_NAME | cut -f1 -d\' \' | head -n 1) > VERSION'
                        sh 'docker build -t $AGENT_IMAGE .'
                    }
                }
            }
        }
        stage('Push') {
            steps {
                sh 'docker push $AGENT_IMAGE'
            }
        }
        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv('SonarQube') {
                    sh '${SCANNER_HOME}/bin/sonar-scanner -Dsonar.branch=$BRANCH_NAME'
                }
            }
        }
        stage('Push versioned') {
            when { branch 'master' }
            steps {
                sh 'docker tag $AGENT_IMAGE "$AGENT_NAME:$(cat .version)"'
                sh 'docker push "$AGENT_NAME:$(cat .version)"'
            }
        }
        stage('Push pypi') {
            when { branch 'master' }
            agent {
                docker {
                    image '$AGENT_IMAGE'
                    reuseNode true
                }
            }
            steps {
                sh 'python setup.py sdist'
                sh 'python setup.py bdist_wheel --universal'
                sh 'mkdir build/wheel'
                sh 'grep "#egg=" requirements.txt | xargs pip wheel -w build/wheel --no-deps'
                sh 'pip install --user twine'
                withCredentials([usernamePassword(credentialsId: 'pypi-credentials', passwordVariable: 'TWINE_PASSWORD', usernameVariable: 'TWINE_USERNAME'), string(credentialsId: 'pypi-repository', variable: 'TWINE_REPOSITORY_URL')]) {
                    sh '~/.local/bin/twine upload dist/* build/wheel/*'
                }
            }
        }
    }
}
