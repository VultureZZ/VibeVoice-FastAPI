# Syncing VibeVoice Module with Upstream

This guide explains how to sync the local `vibevoice/` module with the latest code from the [Microsoft VibeVoice repository](https://github.com/microsoft/VibeVoice).

## Current Status

The `vibevoice/` directory is currently stored as regular files in this repository, not as a git submodule.

## Sync Options

### Option 1: Convert to Git Submodule (Recommended)

This is the best approach for long-term maintenance. It keeps the upstream code separate and makes updates easier.

**Using the sync script:**
```bash
./sync_vibevoice.sh
# Select option 1
```

**Manual steps:**
```bash
# 1. Backup current vibevoice directory
cp -r vibevoice vibevoice_backup

# 2. Remove current directory
rm -rf vibevoice

# 3. Add as submodule
git submodule add https://github.com/microsoft/VibeVoice.git vibevoice

# 4. Initialize and update
git submodule update --init --recursive
```

**To update in the future:**
```bash
git submodule update --remote vibevoice
git add vibevoice
git commit -m "Update vibevoice submodule to latest version"
```

**After cloning this repo:**
```bash
git submodule update --init --recursive
```

### Option 2: Manual Sync (Copy Files)

Use this if you prefer to keep vibevoice as regular files but want to sync manually.

**Using the sync script:**
```bash
./sync_vibevoice.sh
# Select option 2
```

**Manual steps:**
```bash
# 1. Backup current directory
cp -r vibevoice vibevoice_backup

# 2. Clone upstream repository
git clone https://github.com/microsoft/VibeVoice.git .vibevoice_temp

# 3. Copy vibevoice directory
rm -rf vibevoice
cp -r .vibevoice_temp/vibevoice vibevoice

# 4. Cleanup
rm -rf .vibevoice_temp

# 5. Review changes and test
git diff vibevoice/

# 6. Commit if everything works
git add vibevoice/
git commit -m "Sync vibevoice module with upstream"
```

### Option 3: Check for Updates (Dry Run)

Check what has changed without making any modifications.

**Using the sync script:**
```bash
./sync_vibevoice.sh
# Select option 3
```

## Important Notes

1. **Backup First**: Always backup your current `vibevoice/` directory before syncing
2. **Test After Sync**: After syncing, test your FastAPI wrapper to ensure compatibility
3. **Breaking Changes**: The upstream repository may have breaking changes. Review the [VibeVoice changelog](https://github.com/microsoft/VibeVoice/commits/main) before syncing
4. **Custom Modifications**: If you've made custom modifications to the vibevoice module, you'll need to merge them manually or preserve them

## Checking for Breaking Changes

Before syncing, check the upstream repository for:
- Recent commits and their messages
- Changes to API signatures
- New dependencies
- Configuration file changes

```bash
# View recent commits
git clone --depth 10 https://github.com/microsoft/VibeVoice.git temp_check
cd temp_check
git log --oneline
cd ..
rm -rf temp_check
```

## Troubleshooting

### If sync breaks your FastAPI wrapper:

1. Restore from backup:
   ```bash
   rm -rf vibevoice
   cp -r vibevoice_backup_YYYYMMDD_HHMMSS vibevoice
   ```

2. Review the differences:
   ```bash
   diff -r vibevoice_backup vibevoice
   ```

3. Check the upstream repository's commit history for breaking changes

### If using submodules and having issues:

```bash
# Reinitialize submodules
git submodule deinit -f vibevoice
rm -rf .git/modules/vibevoice
git submodule update --init --recursive
```

## Recommended Workflow

1. **First time setup**: Convert to submodule (Option 1)
2. **Regular updates**: Use `git submodule update --remote vibevoice`
3. **Before major updates**: Check upstream changelog and test in a separate branch

## Quick Reference

```bash
# Check current vibevoice status
git status vibevoice/

# Update submodule (if using submodule approach)
git submodule update --remote vibevoice

# View submodule status
git submodule status

# Check what changed in upstream
cd vibevoice
git fetch
git log HEAD..origin/main
cd ..
```
