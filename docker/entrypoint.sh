#!/bin/sh
# No arguments: run the whole pipeline. With arguments: run one CLI command (e.g. seed --customers 200).
set -e
if [ $# -gt 0 ]; then
  exec uv run --no-sync python -m pipeline.run "$@"
fi
uv run --no-sync python -m pipeline.run sync
uv run --no-sync python -m pipeline.run load
(cd dbt && uv run --no-sync dbt build)
uv run --no-sync python -m pipeline.run export