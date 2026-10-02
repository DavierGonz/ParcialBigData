#!/usr/bin/env bash
set -Eeuo pipefail
: "${BUILD_NUMBER:?Jenkins BUILD_NUMBER required}"
: "${JOB_BASE_NAME:?Jenkins JOB_BASE_NAME required}"
RUN_ID="pbd-${JOB_BASE_NAME}-${BUILD_NUMBER}"
[[ "$RUN_ID" =~ ^[a-z0-9][a-z0-9_.-]*$ ]] || { echo 'Invalid CI resource name'; exit 2; }
export CANDIDATE_IMAGE="parcialbigdata-api:${RUN_ID}"
export TEST_IMAGE="parcialbigdata-api-test:${RUN_ID}"
TEST_CONTAINER="${RUN_ID}-tests"
STABLE_IMAGE='parcialbigdata-api:deployed'
mkdir -p reports .ci
source_revision() {
    if [[ "${JOB_BASE_NAME}" == parcialbigdata-validation-local && -n "${CI_SOURCE_SNAPSHOT:-}" ]]; then
        printf '%s' "$CI_SOURCE_SNAPSHOT"
    else
        git rev-parse HEAD
    fi
}
compose() { docker compose --project-name parcialbigdata --env-file .env.ci "$@"; }
candidate() { docker compose --project-name "$RUN_ID" --env-file .env.ci --file ci/compose.candidate.yml "$@"; }
smoke_live() { compose exec -T api python /app/scripts/smoke_api.py "http://127.0.0.1:5000/$1" --attempts 1; }
rollback() {
    if [[ -f .ci/deployment.pending ]]; then
        echo 'Restoring the API state captured before this deployment'
        previous=$(cat .ci/previous-image)
        if [[ -n "$previous" ]]; then
            docker tag "$previous" "$STABLE_IMAGE" || return 1
            API_IMAGE="$STABLE_IMAGE" compose up -d --no-deps --no-build --force-recreate --wait --wait-timeout 90 api || return 1
            compose exec -T api python -c 'import json,urllib.request; r=urllib.request.urlopen("http://127.0.0.1:5000/health",timeout=5); assert r.status==200; assert json.load(r)=={"status":"ok","service":"us-accidents-api"}' || return 1
        else
            compose rm --stop --force api || return 1
        fi
        printf 'rollback completed\n' > reports/rollback.txt
        rm -f .ci/deployment.pending
    fi
}
case "${1:-}" in
    validate)
        umask 077
        printf '%s\n' "$COMPOSE_ENV_TEXT" > .env.ci
        compose config --quiet
        candidate config --quiet
        rm -f .ci/tests.passed .ci/infrastructure.passed .ci/analytics.passed .ci/api-integration.passed .ci/candidate.passed
        source_revision > reports/source-commit.txt
        ;;
    build)
        docker build --target test -f docker/api/Dockerfile -t "$TEST_IMAGE" .
        compose build mongodb spark-master dask-scheduler
        ;;
    test)
        test_paths=(tests)
        if [[ "${CI_FAULT:-none}" == pytest ]]; then test_paths+=(ci/faults/test_forced_failure.py); fi
        docker create --name "$TEST_CONTAINER" --network none --memory 256m "$TEST_IMAGE" python -m pytest -q -p no:cacheprovider --junitxml=/tmp/pytest.xml "${test_paths[@]}"
        status=0
        docker start --attach "$TEST_CONTAINER" || status=$?
        docker cp "$TEST_CONTAINER:/tmp/pytest.xml" reports/pytest.xml
        docker rm "$TEST_CONTAINER"
        if [[ "$status" == 0 ]]; then touch .ci/tests.passed; fi
        exit "$status"
        ;;
    infrastructure)
        compose up -d --no-build --wait --wait-timeout 240 mongodb spark-master spark-worker dask-scheduler dask-worker-1 dask-worker-2
        compose exec -T dask-scheduler python - < ci/check_services.py
        compose exec -T spark-master /opt/spark/bin/spark-submit /opt/smoke_spark.py
        touch .ci/infrastructure.passed
        ;;
    candidate)
        test -f .ci/analytics.passed
        test -f .ci/api-integration.passed
        docker build --target runtime --label "org.opencontainers.image.revision=$(source_revision)" -f docker/api/Dockerfile -t "$CANDIDATE_IMAGE" .
        candidate up -d --no-build --wait --wait-timeout 60
        path=health
        if [[ "${CI_FAULT:-none}" == candidate-smoke ]]; then path=forced-missing-endpoint; fi
        candidate exec -T api python /app/scripts/smoke_api.py "http://127.0.0.1:5000/$path" --attempts 1
        candidate exec -T api python /app/scripts/smoke_geo.py http://127.0.0.1:5000
        touch .ci/candidate.passed
        ;;
    deploy)
        for gate in tests infrastructure analytics api-integration candidate; do
            [[ -f ".ci/${gate}.passed" ]] || { echo "Missing successful ${gate} gate"; exit 1; }
        done
        previous_container=$(compose ps -q api)
        previous=''
        if [[ -n "$previous_container" ]]; then previous=$(docker inspect --format '{{.Image}}' "$previous_container"); fi
        printf '%s' "$previous" > .ci/previous-image
        touch .ci/deployment.pending
        trap 'status=$?; trap - ERR; rollback || echo "ROLLBACK FAILED: retain workspace and recover manually" >&2; exit "$status"' ERR
        docker tag "$CANDIDATE_IMAGE" "$STABLE_IMAGE"
        API_IMAGE="$STABLE_IMAGE" compose up -d --no-deps --no-build --force-recreate --wait --wait-timeout 90 api
        path=health
        if [[ "${CI_FAULT:-none}" == post-deploy ]]; then path=forced-missing-endpoint; fi
        smoke_live "$path"
        compose exec -T api python /app/scripts/smoke_geo.py http://127.0.0.1:5000
        docker image inspect --format '{{.Id}} revision={{index .Config.Labels "org.opencontainers.image.revision"}}' "$CANDIDATE_IMAGE" > reports/deployment.txt
        rm -f .ci/deployment.pending
        echo 'DEPLOYMENT VERIFIED'
        ;;
    cleanup)
        rollback
        candidate down --remove-orphans
        if docker container inspect "$TEST_CONTAINER" >/dev/null 2>&1; then docker rm --force "$TEST_CONTAINER"; fi
        if docker container inspect "${RUN_ID}-integration" >/dev/null 2>&1; then docker rm --force "${RUN_ID}-integration"; fi
        rm -f .env.ci
        ;;
    analytics)
        test -f .ci/tests.passed
        test -f .ci/infrastructure.passed
        status=0
        compose exec -T spark-master /opt/spark/bin/spark-submit /opt/processing/run_tests.py > reports/spark-tests.log 2>&1 || status=$?
        compose cp spark-master:/scratch/spark-tests.xml reports/spark-tests.xml
        [[ "$status" == 0 ]] || exit "$status"
        compose exec -T spark-master /opt/spark/bin/spark-submit /opt/processing/job.py > reports/spark-job.log 2>&1
        compose cp spark-master:/data/analytics-report.json reports/analytics.json
        touch .ci/analytics.passed
        ;;
    api-integration)
        test -f .ci/analytics.passed
        status=0
        compose -f docker-compose.yml -f ci/compose.integration.yml run --no-deps --name "${RUN_ID}-integration" api-integration || status=$?
        docker cp "${RUN_ID}-integration:/tmp/api-integration.xml" reports/api-integration.xml
        docker rm "${RUN_ID}-integration"
        [[ "$status" == 0 ]] || exit "$status"
        touch .ci/api-integration.passed
        ;;
    *) echo 'Unknown pipeline stage' >&2; exit 2 ;;
esac
