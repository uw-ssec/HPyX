#!/bin/bash


set -e

# Set default for READTHEDOCS_OUTPUT if not set
READTHEDOCS_OUTPUT="${READTHEDOCS_OUTPUT:-.}"

mkdir -p $READTHEDOCS_OUTPUT/html/

jupyter --paths && \
python -m mkdocs build --clean --site-dir "$READTHEDOCS_OUTPUT/html" --config-file mkdocs.yml

# List the contents of the output directory for verification
echo "Contents of $READTHEDOCS_OUTPUT/html:"
ls -la "$READTHEDOCS_OUTPUT/html"
