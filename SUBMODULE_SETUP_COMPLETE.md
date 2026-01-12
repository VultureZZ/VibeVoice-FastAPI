# VibeVoice Submodule Setup - Complete ✅

The `vibevoice/` directory has been successfully converted to a git submodule pointing to the Microsoft VibeVoice repository.

## What Was Done

1. ✅ Removed old `vibevoice/` directory from git tracking
2. ✅ Added Microsoft VibeVoice repository as a git submodule
3. ✅ Configured sparse checkout to get only the `vibevoice/` subdirectory
4. ✅ Fixed directory structure (moved nested `vibevoice/vibevoice/` to `vibevoice/`)

## Current Status

- **Submodule**: `vibevoice/` is now a git submodule
- **Upstream**: Points to `https://github.com/microsoft/VibeVoice.git`
- **Structure**: Correct - Python modules are at `vibevoice/modular/`, `vibevoice/processor/`, etc.

## Next Steps

### 1. Commit the Changes

```bash
git add .gitmodules vibevoice
git commit -m "Convert vibevoice to git submodule from Microsoft VibeVoice"
```

### 2. Update the Submodule in the Future

When you want to sync with the latest upstream code:

```bash
# Update to latest
git submodule update --remote vibevoice

# Fix structure if needed (if nested structure appears)
./fix_vibevoice_structure.sh

# Commit the update
git add vibevoice
git commit -m "Update vibevoice submodule to latest version"
```

### 3. After Cloning This Repository

When someone clones this repository, they need to initialize submodules:

```bash
git clone <your-repo-url>
cd VibeVoice-FastAPI
git submodule update --init --recursive
./fix_vibevoice_structure.sh  # Fix structure if needed
```

## Helper Scripts

- **`fix_vibevoice_structure.sh`**: Fixes nested directory structure after submodule updates
- **`sync_vibevoice.sh`**: Original sync script (now submodule is set up, use git commands instead)

## Important Notes

1. **Directory Structure**: The Microsoft repo has `vibevoice/` as a subdirectory, so after updates you may need to run `./fix_vibevoice_structure.sh` to move files up one level.

2. **Sparse Checkout**: The submodule uses sparse checkout to only get the `vibevoice/` directory, but the structure may still be nested. The fix script handles this.

3. **Testing**: After updating the submodule, always test your FastAPI wrapper to ensure compatibility:
   ```bash
   python main.py --model 1.5b
   ```

## Verification

Check submodule status:
```bash
git submodule status
```

Should show:
```
6c7369b... vibevoice (heads/main)
```

## Troubleshooting

### If structure is nested after update:
```bash
./fix_vibevoice_structure.sh
```

### If submodule is not initialized:
```bash
git submodule update --init --recursive
```

### If you need to re-clone the submodule:
```bash
git submodule deinit -f vibevoice
rm -rf .git/modules/vibevoice
git submodule update --init --recursive
./fix_vibevoice_structure.sh
```
