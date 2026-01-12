# Fixing Submodule Conversion

The error occurred because `vibevoice/` is already tracked in git. Here's how to fix it:

## Quick Fix Steps

Run these commands in order:

```bash
# 1. Remove vibevoice from git index (but keep the files)
git rm -r --cached vibevoice

# 2. Remove the directory
rm -rf vibevoice

# 3. Add as submodule
git submodule add https://github.com/microsoft/VibeVoice.git vibevoice

# 4. Initialize the submodule
git submodule update --init --recursive

# 5. Review and commit
git status
git commit -m "Convert vibevoice to git submodule"
```

## Alternative: If you want to keep your current vibevoice

If you've made custom modifications and want to preserve them:

```bash
# 1. Check what's different
diff -r vibevoice_backup_20260112_102959 vibevoice

# 2. If you want to keep current version, restore from backup
rm -rf vibevoice
cp -r vibevoice_backup_20260112_102959 vibevoice

# 3. Then follow the steps above
```

## Verify It Worked

After conversion, verify the submodule:

```bash
# Check submodule status
git submodule status

# Should show something like:
#  abc1234... vibevoice (v1.0.0)
```

## Future Updates

Once it's a submodule, update with:

```bash
git submodule update --remote vibevoice
git add vibevoice
git commit -m "Update vibevoice submodule"
```
