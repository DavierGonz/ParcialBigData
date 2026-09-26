// Phase 1 scaffold. Do not run until the repository and Jenkins job exist.
pipeline {
    agent { label 'local-docker' }
    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }
    stages {
        stage('Checkout') {
            steps { checkout scm }
        }
        stage('Build test image') {
            steps {
                sh 'docker build --target test -f docker/api/Dockerfile -t parcialbigdata-api-test:$BUILD_NUMBER .'
            }
        }
        stage('Pytest gate') {
            steps {
                // Nonzero exit aborts the pipeline. Never catch/ignore this error.
                sh 'docker run --rm --memory=256m parcialbigdata-api-test:$BUILD_NUMBER'
            }
        }
        stage('Build runtime image') {
            steps {
                sh 'docker build --target runtime -f docker/api/Dockerfile -t parcialbigdata-api:candidate-$BUILD_NUMBER .'
            }
        }
        stage('Phase 1 boundary') {
            steps {
                echo 'Tests passed. Automatic deployment and GitHub webhook are not enabled in phase 1.'
            }
        }
    }
    post {
        failure { echo 'Pipeline failed: deployment is blocked.' }
    }
}
