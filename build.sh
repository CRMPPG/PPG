#!/bin/bash
# Build a standalone PPG executable (no Python needed to run it)
#
# Usage:
#   ./build.sh
#
# Output:
#   dist/ppg (Linux/Mac) or dist/ppg.exe (Windows)
#
# Prerequisites:
#   pip install pyinstaller

set -e

echo "Building PPG standalone executable..."

pyinstaller \
    --onefile \
    --name ppg \
    --add-data "data:data" \
    --exclude-module cryptography \
    --hidden-import ppg \
    --hidden-import ppg.cli \
    --hidden-import ppg.pipeline \
    --hidden-import ppg.scrapers \
    --hidden-import ppg.scrapers.clark_county_recorder \
    --hidden-import ppg.scrapers.csv_import \
    --hidden-import ppg.scrapers.generic_assessor \
    --hidden-import ppg.scrapers.recorder_base \
    --hidden-import ppg.scrapers.base \
    --hidden-import ppg.analysis \
    --hidden-import ppg.analysis.distress_scorer \
    --hidden-import ppg.analysis.comparator \
    --hidden-import ppg.analysis.document_merger \
    --hidden-import ppg.models \
    --hidden-import ppg.models.database \
    --hidden-import ppg.utils \
    --hidden-import ppg.utils.http \
    ppg/cli.py

echo ""
echo "Done! Executable is at: dist/ppg"
echo "Run it with: ./dist/ppg recorder data/mls_listings.csv --export results.csv"
