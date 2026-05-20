#!/usr/bin/env bash
# scripts/run_bench_local.sh — local developer loop for HPyX benchmarks.
#
# Subcommands:
#   bench [pytest args]     Run the full suite
#   record <test-id>        py-spy flame graph on one test
#   compare                 Compare vs stored baseline
#
# Requires: pixi, py-spy (for record).

set -euo pipefail

subcommand="${1:-}"
shift || true

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

case "$subcommand" in
    bench)
        exec pixi run -e benchmark-py313t pytest benchmarks/ \
            --benchmark-only \
            --benchmark-min-rounds=5 \
            --benchmark-warmup=on \
            --benchmark-autosave \
            "$@"
        ;;

    record)
        test_id="${1:-}"
        if [ -z "$test_id" ]; then
            echo "usage: run_bench_local.sh record <test-id>" >&2
            echo "example: run_bench_local.sh record benchmarks/test_bench_kernels.py::test_dot_hpyx" >&2
            exit 2
        fi
        output="flame-$(date +%Y%m%d-%H%M%S).svg"
        echo "Recording to $output ..."
        exec py-spy record --native --rate 500 -o "$output" -- \
            pixi run -e benchmark-py313t pytest "$test_id" -v --benchmark-only
        ;;

    compare)
        exec pixi run -e benchmark-py313t pytest-benchmark compare \
            --sort=name
        ;;

    *)
        echo "usage: run_bench_local.sh {bench|record|compare} [args]" >&2
        echo >&2
        echo "  bench [args]        Run full suite with repo defaults" >&2
        echo "  record <test-id>    py-spy native flame graph on one test" >&2
        echo "  compare             pytest-benchmark compare vs stored baseline" >&2
        exit 2
        ;;
esac
