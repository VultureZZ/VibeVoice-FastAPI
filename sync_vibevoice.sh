#!/bin/bash
# Script to sync vibevoice module with Microsoft VibeVoice repository
# This script provides multiple sync options

set -e

VIBEVOICE_DIR="vibevoice"
UPSTREAM_REPO="https://github.com/microsoft/VibeVoice.git"
TEMP_DIR=".vibevoice_sync_temp"

echo "VibeVoice Module Sync Script"
echo "============================"
echo ""

# Check if vibevoice directory exists
if [ ! -d "$VIBEVOICE_DIR" ]; then
    echo "Error: $VIBEVOICE_DIR directory not found!"
    exit 1
fi

# Function to backup current vibevoice
backup_vibevoice() {
    echo "Creating backup of current vibevoice directory..."
    BACKUP_DIR="vibevoice_backup_$(date +%Y%m%d_%H%M%S)"
    cp -r "$VIBEVOICE_DIR" "$BACKUP_DIR"
    echo "Backup created: $BACKUP_DIR"
}

# Option 1: Convert to submodule (recommended)
convert_to_submodule() {
    echo ""
    echo "Option 1: Converting vibevoice to git submodule"
    echo "This is the recommended approach for long-term maintenance."
    echo ""
    read -p "This will remove the current vibevoice directory from git. Continue? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi

    backup_vibevoice

    # Remove from git index (but keep files temporarily)
    echo "Removing vibevoice from git index..."
    git rm -r --cached "$VIBEVOICE_DIR" 2>/dev/null || echo "Note: vibevoice not in git index"

    # Remove current vibevoice directory
    rm -rf "$VIBEVOICE_DIR"

    # Add as submodule
    echo "Adding vibevoice as git submodule..."
    git submodule add "$UPSTREAM_REPO" "$VIBEVOICE_DIR"

    echo ""
    echo "Submodule added successfully!"
    echo "To update in the future, run: git submodule update --remote vibevoice"
    echo "To initialize after cloning: git submodule update --init --recursive"
    echo ""
    echo "Next steps:"
    echo "1. Review the changes: git status"
    echo "2. Test your FastAPI wrapper to ensure compatibility"
    echo "3. Commit the submodule: git commit -m 'Convert vibevoice to git submodule'"
}

# Option 2: Manual sync (copy files)
manual_sync() {
    echo ""
    echo "Option 2: Manual sync (copy files from upstream)"
    echo "This will clone the upstream repo and copy the vibevoice directory."
    echo ""
    read -p "Continue? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi

    backup_vibevoice

    # Clone upstream repo to temp directory
    echo "Cloning upstream repository..."
    rm -rf "$TEMP_DIR"
    git clone "$UPSTREAM_REPO" "$TEMP_DIR"

    # Copy vibevoice directory
    echo "Copying vibevoice directory..."
    rm -rf "$VIBEVOICE_DIR"
    cp -r "$TEMP_DIR/vibevoice" "$VIBEVOICE_DIR"

    # Cleanup
    rm -rf "$TEMP_DIR"

    echo ""
    echo "Sync completed! Please review changes and test your FastAPI wrapper."
    echo "If there are breaking changes, restore from backup: $BACKUP_DIR"
}

# Option 3: Check for updates only
check_updates() {
    echo ""
    echo "Option 3: Check for updates (dry run)"
    echo "This will show what has changed in the upstream repository."
    echo ""

    # Clone to temp directory
    echo "Fetching latest from upstream..."
    rm -rf "$TEMP_DIR"
    git clone --depth 1 "$UPSTREAM_REPO" "$TEMP_DIR"

    echo ""
    echo "Comparing files..."
    echo "Files in upstream but different/missing locally:"
    diff -rq "$VIBEVOICE_DIR" "$TEMP_DIR/vibevoice" | grep "Only in" || echo "No unique files found"

    echo ""
    echo "Files that differ:"
    diff -rq "$VIBEVOICE_DIR" "$TEMP_DIR/vibevoice" | grep "differ" || echo "No differences found"

    # Cleanup
    rm -rf "$TEMP_DIR"

    echo ""
    echo "Check complete. Review the differences above."
}

# Main menu
echo "Select sync method:"
echo "1) Convert to git submodule (recommended)"
echo "2) Manual sync (copy files)"
echo "3) Check for updates only (dry run)"
echo "4) Exit"
echo ""
read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        convert_to_submodule
        ;;
    2)
        manual_sync
        ;;
    3)
        check_updates
        ;;
    4)
        echo "Exiting."
        exit 0
        ;;
    *)
        echo "Invalid choice."
        exit 1
        ;;
esac
