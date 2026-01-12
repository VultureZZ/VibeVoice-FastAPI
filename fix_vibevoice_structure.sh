#!/bin/bash
# Fix vibevoice submodule structure after updates
# This moves the nested vibevoice/vibevoice/ to vibevoice/

set -e

VIBEVOICE_DIR="vibevoice"

if [ ! -d "$VIBEVOICE_DIR" ]; then
    echo "Error: $VIBEVOICE_DIR directory not found!"
    exit 1
fi

# Check if nested structure exists
if [ -d "$VIBEVOICE_DIR/vibevoice" ]; then
    echo "Fixing nested vibevoice structure..."

    # Move contents up one level
    mv "$VIBEVOICE_DIR/vibevoice"/* "$VIBEVOICE_DIR/" 2>/dev/null || true
    mv "$VIBEVOICE_DIR/vibevoice"/.* "$VIBEVOICE_DIR/" 2>/dev/null || true

    # Remove empty nested directory
    rmdir "$VIBEVOICE_DIR/vibevoice" 2>/dev/null || true

    echo "Structure fixed!"
else
    echo "Structure is already correct."
fi
