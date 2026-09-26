pipeline {
    agent { label 'local-docker' }
    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        skipStagesAfterUnstable()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }
    parameters {
        choice(name: 'SOURCE_MODE', choices: ['SCM', 'LOCAL'], description: 'LOCAL consumes an exported Git commit without publishing to GitHub.')
        string(name: 'LOCAL_COMMIT', defaultValue: '', description: 'Exact commit exported by scripts/jenkins_local.py.')
        choice(name: 'FAULT', choices: ['none', 'pytest', 'candidate-smoke', 'post-deploy'], description: 'Controlled failure validation; LOCAL mode only.')
    }
    environment {
        COMPOSE_ENV_TEXT = credentials('parcialbigdata-compose-env')
        CI_FAULT = "${params.FAULT}"
    }
    stages {
        stage('Checkout') {
            steps {
                script {
                    if (params.SOURCE_MODE != 'LOCAL' && params.FAULT != 'none') {
                        error('Fault injection is restricted to LOCAL validation.')
                    }
                    deleteDir()
                    if (params.SOURCE_MODE == 'LOCAL') {
                        if (!(params.LOCAL_COMMIT ==~ /[0-9a-f]{40}/)) {
                            error('An exact local commit is required.')
                        }
                        withEnv(["EXPECTED_COMMIT=${params.LOCAL_COMMIT}"]) {
                            sh 'git init -q .; git fetch --no-tags "/var/jenkins_home/local-sources/${EXPECTED_COMMIT}.bundle" HEAD; git checkout --detach FETCH_HEAD; test "$(git rev-parse HEAD)" = "$EXPECTED_COMMIT"'
                        }
                    } else {
                        checkout scm
                    }
                }
            }
        }
        stage('Validate configuration') {
            steps { sh 'bash ci/pipeline.sh validate' }
        }
        stage('Build images') {
            steps { sh 'bash ci/pipeline.sh build' }
        }
        stage('Pytest gate') {
            steps { sh 'bash ci/pipeline.sh test' }
            post { always { junit testResults: 'reports/pytest.xml', allowEmptyResults: false } }
        }
        stage('Infrastructure integration') {
            steps { sh 'bash ci/pipeline.sh infrastructure' }
        }
        stage('Candidate HTTP smoke') {
            steps { sh 'bash ci/pipeline.sh candidate' }
        }
        stage('Deploy and verify locally') {
            steps { sh 'bash ci/pipeline.sh deploy' }
        }
    }
    post {
        always {
            script {
                if (fileExists('ci/pipeline.sh')) {
                    sh 'bash ci/pipeline.sh cleanup'
                }
            }
            archiveArtifacts artifacts: 'reports/*', allowEmptyArchive: true, fingerprint: true
        }
        failure { echo 'Pipeline failed. No candidate promotion before passing tests; failed deployments trigger rollback.' }
    }
}
