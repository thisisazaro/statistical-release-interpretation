#!/bin/sh
# Verify the two release archives and the saved inference offline.
set -eu
cd "$(dirname "$0")"
python3 -B bls/extract.py --check
python3 -B g17/verify_sources.py
python3 -B reference.py --check
shasum -a 256 -c model/design.sha256
python3 -B experiment.py prepare
python3 -B score.py --check
