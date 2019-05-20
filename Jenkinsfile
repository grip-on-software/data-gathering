pipeline {
    agent { label 'docker' }

    environment {
        AGENT_TAG = env.BRANCH_NAME.replaceFirst('^master$', 'latest')
        AGENT_NAME = "${env.DOCKER_REGISTRY}/gros-data-gathering"
        AGENT_IMAGE = "${env.AGENT_NAME}:${env.AGENT_TAG}"
        GITLAB_TOKEN = credentials('data-gathering-gitlab-token')
        SCANNER_HOME = tool name: 'SonarQube Scanner 3', type: 'hudson.plugins.sonar.SonarRunnerInstallation'
    }
    options {
        gitLabConnection('gitlab')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }
    triggers {
        gitlab(triggerOnPush: true, triggerOnMergeRequest: true, branchFilterType: 'All', secretToken: env.GITLAB_TOKEN)
        cron('H H * * H/3')
    }

    post {
        failure {
            updateGitlabCommitStatus name: env.JOB_NAME, state: 'failed'
        }
        aborted {
            updateGitlabCommitStatus name: env.JOB_NAME, state: 'canceled'
        }
    }

    stages {
        stage('Start') {
            when {
                expression {
                    currentBuild.rawBuild.getCause(hudson.triggers.TimerTrigger$TimerTriggerCause) == null
                }
            }
            steps {
                updateGitlabCommitStatus name: env.JOB_NAME, state: 'running'
            }
        }
        stage('Build') {
            steps {
                checkout scm
                withCredentials([file(credentialsId: 'upload-server-certificate', variable: 'SERVER_CERTIFICATE')]) {
                    withCredentials([file(credentialsId: 'agent-environment', variable: 'AGENT_ENVIRONMENT')]) {
                        sh 'rm -f certs/wwwgros.crt'
                        sh 'cp $SERVER_CERTIFICATE certs/wwwgros.crt'
                        sh 'cp $AGENT_ENVIRONMENT env'
                        sh 'chmod 444 certs/wwwgros.crt'
                        sh 'echo $(grep __version__ gatherer/__init__.py | sed -E "s/__version__ = .([0-9\\.]+)./\\1/") > .version'
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
            when {
                anyOf {
                    expression {
                        currentBuild.rawBuild.getCause(hudson.triggers.SCMTrigger$SCMTriggerCause) == null
                    }
                    not { branch 'master' }
                }
            }
            steps {
                withSonarQubeEnv('SonarQube') {
                    withPythonEnv('System-CPython-3') {
                        pysh 'python -m pip install pylint'
                        pysh 'python -m pip install -r requirements-jenkins.txt'
                        pysh 'sed -i "1s|.*|#!/usr/bin/env python|" `which pylint`'
                        pysh '${SCANNER_HOME}/bin/sonar-scanner -Dsonar.branch=$BRANCH_NAME -Dsonar.python.pylint=`which pylint`'
                    }
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
        stage('Build pypi') {
            agent {
                docker {
                    image '$AGENT_IMAGE'
                    reuseNode true
                }
            }
            steps {
                sh 'python setup.py sdist'
                sh 'python setup.py bdist_wheel'
                sh 'mkdir -p build/wheel'
                sh 'grep "#egg=" requirements.txt | xargs pip wheel -w build/wheel --no-deps'
            }
        }
        stage('Push pypi') {
            when { branch 'master' }
            steps {
                withPythonEnv('System-CPython-3') {
                    pysh 'python -m pip install twine'
                    withCredentials([usernamePassword(credentialsId: 'pypi-credentials', passwordVariable: 'TWINE_PASSWORD', usernameVariable: 'TWINE_USERNAME'), string(credentialsId: 'pypi-repository', variable: 'TWINE_REPOSITORY_URL'), file(credentialsId: 'pypi-certificate', variable: 'TWINE_CERT')]) {
                        pysh 'python -m twine upload dist/* build/wheel/*'
                    }
                }
            }
        }
        stage('Status') {
            when {
                expression {
                    currentBuild.rawBuild.getCause(hudson.triggers.TimerTrigger$TimerTriggerCause) == null
                }
            }
            steps {
                updateGitlabCommitStatus name: env.JOB_NAME, state: 'success'
            }
        }
    }
}
