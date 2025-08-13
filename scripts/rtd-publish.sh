#!/bin/bash

set -e

mkdir -p $READTHEDOCS_OUTPUT/html/

jupyter --paths && \
python -m mkdocs build --clean --site-dir "$READTHEDOCS_OUTPUT/html" --config-file mkdocs.yml

# List the contents of the output directory for verification
echo "Contents of $READTHEDOCS_OUTPUT/html:"
ls -la "$READTHEDOCS_OUTPUT/html"
