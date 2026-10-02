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
        choice(name: 'FAULT', choices: ['none', 'pytest', 'candidate-smoke', 'post-deploy'], description: 'Controlled failure validation; Validation jobs only.')
    }
    triggers { githubPush() }
    environment {
        COMPOSE_ENV_TEXT = credentials('parcialbigdata-compose-env')
        CI_FAULT = "${params.FAULT}"
    }
    stages {
        stage('Checkout') {
            steps {
                script {
                    if (!env.JOB_BASE_NAME.startsWith('parcialbigdata-validation') && params.FAULT != 'none') {
                        error('Fault injection is restricted to authenticated validation jobs.')
                    }
                    if (fileExists('.ci/deployment.pending')) {
                        error('A prior deployment still requires recovery. Preserve this workspace and resolve it before another build.')
                    }
                    deleteDir()
                    checkout scm
                    env.CHECKOUT_READY = 'true'
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
        stage('Spark tests and analytics') {
            steps { sh 'bash ci/pipeline.sh analytics' }
            post { always { junit testResults: 'reports/spark-tests.xml', allowEmptyResults: false } }
        }
        stage('Geospatial API integration') {
            steps { sh 'bash ci/pipeline.sh api-integration' }
            post { always { junit testResults: 'reports/api-integration.xml', allowEmptyResults: false } }
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
                if (env.CHECKOUT_READY == 'true' && fileExists('ci/pipeline.sh')) {
                    sh 'bash ci/pipeline.sh cleanup'
                }
            }
            archiveArtifacts artifacts: 'reports/*', allowEmptyArchive: true, fingerprint: true
        }
        failure { echo 'Pipeline failed. No candidate promotion before passing tests; failed deployments trigger rollback.' }
    }
}
