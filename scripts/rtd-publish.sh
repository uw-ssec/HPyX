#!/bin/bash

set -e


jupyter --paths && \
python -m mkdocs build --clean --site-dir $READTHEDOCS_OUTPUT/html --config-file mkdocs.yml
