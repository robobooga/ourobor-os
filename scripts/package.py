import os
import shutil
import re
from pathlib import Path

def validate_ouro_structure(ouro_dir):
    """Validates that the ouro directory has the required structure."""
    required_files = [
        'README.md',
        'AGENT_PROTOCOL.md',
        'SKILL.md',
        'scripts/bootstrap.py',
        'scripts/capture.py',
        'scripts/hooks.py',
        'wiki/index.md',
        'wiki/schema.md',
        'wiki/capture-queue.md',
    ]

    required_dirs = [
        'scripts',
        'wiki',
        'wiki/entities',
        'wiki/decisions',
        'wiki/patterns',
        'wiki/maps',
    ]

    missing = []

    for file_path in required_files:
        if not (ouro_dir / file_path).exists():
            missing.append(f"File: {file_path}")

    for dir_path in required_dirs:
        if not (ouro_dir / dir_path).is_dir():
            missing.append(f"Directory: {dir_path}")

    return missing

def package():
    print("Packaging Ourobor OS for distribution...")

    # Paths
    root = Path(__file__).resolve().parent.parent
    ouro_dir = root / 'ouro'
    dist_dir = root / 'dist'
    dist_zip = dist_dir / 'ouro-skill.zip'

    # 1. Validate ouro directory exists
    if not ouro_dir.exists():
        print(f"ERROR: ouro directory not found at {ouro_dir}")
        return

    print(f"  [OK] Found ouro directory at {ouro_dir.relative_to(root)}")

    # 2. Validate directory structure
    print("  - Validating directory structure...")
    missing = validate_ouro_structure(ouro_dir)

    if missing:
        print("ERROR: ouro directory is missing required files/directories:")
        for item in missing:
            print(f"     - {item}")
        return

    print("  [OK] Directory structure validated")

    # 3. Create dist directory
    dist_dir.mkdir(exist_ok=True)
    print(f"  [OK] Created dist directory at {dist_dir.relative_to(root)}")

    # 4. Remove old zip if exists
    if dist_zip.exists():
        dist_zip.unlink()
        print(f"  - Removed old archive")

    # 5. Create distribution zip
    print(f"  - Creating distribution archive...")

    # Create a temporary staging directory to exclude unwanted files
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_ouro = Path(temp_dir) / 'ouro'

        # Copy ouro to temp, excluding __pycache__ and other dev artifacts
        def ignore_patterns(dir, files):
            return [f for f in files if f in {'__pycache__', '.pyc', '.git', '.DS_Store'}]

        shutil.copytree(ouro_dir, temp_ouro, ignore=ignore_patterns)

        # Create archive from temp directory
        shutil.make_archive(
            str(dist_zip.with_suffix('')),  # base_name (without .zip extension)
            'zip',                           # format
            temp_dir,                        # root_dir
            'ouro'                           # base_dir (the ouro folder itself)
        )

    print(f"  [OK] Created {dist_zip.relative_to(root)}")

    # 6. Display package info
    size_mb = dist_zip.stat().st_size / (1024 * 1024)
    print(f"\nPackaging complete!")
    print(f"   Package: {dist_zip.relative_to(root)}")
    print(f"   Size: {size_mb:.2f} MB")
    print(f"\n   Ready for distribution or direct download.")

if __name__ == "__main__":
    package()
