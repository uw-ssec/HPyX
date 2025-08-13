#!/bin/bash

set -e

mkdir -p $READTHEDOCS_OUTPUT/html/

jupyter --paths && \
python -m mkdocs build --clean --site-dir $READTHEDOCS_OUTPUT/html --config-file mkdocs.yml
