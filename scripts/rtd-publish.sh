#!/bin/bash

set -e


jupyter --paths && \
mkdocs build --clean --site-dir $READTHEDOCS_OUTPUT/html --config-file mkdocs.yml
