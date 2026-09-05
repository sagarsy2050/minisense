#!/bin/sh
# Entrypoint: generates the synthetic survey dataset on first run if it
# isn't already present (e.g. mounted in via a volume from a previous run
# or committed by the operator), then execs the real command.
set -e

SURVEY_PATH="${MINISENSE_SURVEY_PATH:-/app/data/survey_responses.json}"

if [ ! -f "$SURVEY_PATH" ]; then
    echo "No survey data found at $SURVEY_PATH — generating synthetic dataset..."
    python /app/data/generate_data.py --count 60000 --out "$SURVEY_PATH"
fi

exec "$@"
