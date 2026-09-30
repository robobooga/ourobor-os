@entity package
@brief Validates the ouro/ directory structure and creates a distributable zip archive for skill installation.

## Overview

`scripts/package.py` is the release tooling for Ourobor OS. It validates that all required files and directories are present in `ouro/`, then creates `dist/ouro-skill.zip` for manual distribution.

@note This script lives in root-level `scripts/`, not `ouro/scripts/`. It operates on the Ourobor OS project itself and is not part of the distributed skill package.

## Functions

### `validate_ouro_structure(ouro_dir)`

Checks for required files and directories. Returns a list of missing items as strings. If the list is non-empty, `package()` aborts before creating the archive.

**Required files**: `README.md`, `AGENT_PROTOCOL.md`, `SKILL.md`, `scripts/bootstrap.py`, `scripts/capture.py`, `scripts/hooks.py`, `scripts/claim_scan.py`, `scripts/runlog.py`, `wiki/index.md`, `wiki/schema.md`, `wiki/capture-queue.md`

**Required directories**: `scripts/`, `wiki/`, `wiki/entities/`, `wiki/decisions/`, `wiki/patterns/`, `wiki/maps/`

### `package()`

1. Validates `ouro/` structure — aborts on failure.
2. Creates `dist/` directory if it doesn't exist.
3. Removes the previous archive if one exists.
4. Copies `ouro/` to a temporary directory, excluding `__pycache__`, `.pyc`, `.git`, `.DS_Store`.
5. Zips the temp directory to `dist/ouro-skill.zip`.
6. Reports the output path and file size.

@note The exclusion filter in `shutil.copytree` targets filenames, not extensions — `.pyc` files are excluded by exact match, which may miss compiled files with different names. This is a minor gap.

@warning Wiki subdirectories in `ouro/wiki/` must contain only `.gitkeep` files. The packager does not filter wiki content — any documentation written there will be shipped to users. See [ADR-001](../decisions/ADR-001-ouro-as-distributable-skeleton.md).

## CLI Usage

```bash
python scripts/package.py
# Output: dist/ouro-skill.zip
```
