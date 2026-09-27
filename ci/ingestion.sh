#!/usr/bin/env bash
set -euo pipefail
set +x
NAME="pbd-ingestion-${BUILD_NUMBER:-manual}"
dc() { docker compose -p parcialbigdata --env-file .env.ci -f docker-compose.yml -f ci/compose.ingestion.yml "$@"; }
api_state() {
    local id
    id=$(docker ps -q --filter label=com.docker.compose.project=parcialbigdata --filter label=com.docker.compose.service=api)
    test -n "$id"
    docker inspect --format '{{.Id}} {{.Image}}' "$id"
}
tests() {
    local suite="$1" status=0
    docker rm -f "$NAME-test" >/dev/null 2>&1 || true
    if [[ "$suite" == unit ]]; then
        dc run --no-deps --name "$NAME-test" -e RUN_INGESTION_INTEGRATION=0 ingestion-tests python -m pytest tests_ingestion -q --junitxml=/tmp/results.xml || status=$?
    else
        dc run --no-deps --name "$NAME-test" ingestion-tests python -m pytest tests_ingestion/test_integration.py -q --junitxml=/tmp/results.xml || status=$?
    fi
    docker cp "$NAME-test:/tmp/results.xml" "reports/ingestion-${suite}.xml"
    docker rm "$NAME-test" >/dev/null
    return "$status"
}
case "${1:?Stage required}" in
    configure)
        umask 077
        printf '%s\n' "$COMPOSE_ENV_TEXT" > .env.ci
        mkdir -p reports .ci
        dc config --quiet
        api_state > reports/api-before.txt
        git rev-parse HEAD > reports/source-commit.txt
        ;;
    build)
        dc build dask-scheduler
        dc build ingestion ingestion-tests
        ;;
    unit)
        tests unit
        touch .ci/ingestion-unit.ok
        ;;
    integration)
        test -f .ci/ingestion-unit.ok
        dc up -d --no-build --wait mongodb dask-scheduler dask-worker-1 dask-worker-2
        tests integration
        touch .ci/ingestion-integration.ok
        ;;
    ingest)
        test -f .ci/ingestion-unit.ok
        test -f .ci/ingestion-integration.ok
        args=()
        [[ "${FORCE_ETL:-false}" == true ]] && args+=(--force-etl)
        (
            while :; do
                printf '{"sample_utc":"%s"}\n' "$(date -u +%FT%TZ)"
                ids=$(docker ps -q --filter label=com.docker.compose.project=parcialbigdata)
                if [[ -n "$ids" ]]; then docker stats --no-stream --format '{{json .}}' $ids; fi
                sleep 5
            done
        ) > reports/resources.jsonl &
        monitor=$!
        trap 'kill "$monitor" 2>/dev/null || true; wait "$monitor" 2>/dev/null || true' EXIT
        dc run --no-deps --name "$NAME-run" ingestion python -m ingestion.run "${args[@]}"
        docker cp "$NAME-run:/data/last-ingestion-report.json" reports/ingestion.json
        docker rm "$NAME-run" >/dev/null
        ;;
    cleanup)
        docker rm -f "$NAME-test" "$NAME-run" >/dev/null 2>&1 || true
        rm -f .env.ci
        if [[ -f reports/api-before.txt ]]; then
            api_state > reports/api-after.txt
            cmp reports/api-before.txt reports/api-after.txt
        fi
        ;;
    *) exit 2 ;;
esac
