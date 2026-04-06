"""Build both apps with PyInstaller and create distribution zips."""

import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).parent

APPS = [
    ("audio_processor.spec", "AudioProcessor"),
    ("transcription_studio.spec", "TranscriptionStudio"),
]


def build_app(spec_name: str, app_name: str) -> Path:
    """Build a single app from its spec file. Returns the output folder path."""
    spec_path = PROJECT_DIR / spec_name
    dist_dir = PROJECT_DIR / "dist"
    work_dir = PROJECT_DIR / "build" / app_name

    print(f"\n{'='*60}")
    print(f"  Building {app_name}")
    print(f"{'='*60}\n")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(spec_path),
        "--distpath", str(dist_dir),
        "--workpath", str(work_dir),
        "--noconfirm",
    ]

    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))
    if result.returncode != 0:
        print(f"\nERROR: {app_name} build failed!")
        sys.exit(1)

    output_folder = dist_dir / app_name
    print(f"\nBuild complete: {output_folder}")
    return output_folder


def create_zip(folder: Path, app_name: str) -> Path:
    """Zip an app folder for distribution."""
    zip_path = folder.parent / f"{app_name}-win64.zip"
    print(f"Creating {zip_path.name}...")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in folder.rglob("*"):
            if f.is_file():
                arcname = f"{app_name}/{f.relative_to(folder)}"
                zf.write(f, arcname)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  -> {zip_path.name} ({size_mb:.1f} MB)")
    return zip_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build Audio Processor and Transcription Studio")
    parser.add_argument("app", nargs="?", choices=["audio", "transcription", "both"],
                        default="both", help="Which app to build (default: both)")
    parser.add_argument("--no-zip", action="store_true", help="Skip zip creation")
    args = parser.parse_args()

    apps_to_build = []
    if args.app in ("audio", "both"):
        apps_to_build.append(APPS[0])
    if args.app in ("transcription", "both"):
        apps_to_build.append(APPS[1])

    for spec_name, app_name in apps_to_build:
        folder = build_app(spec_name, app_name)
        if not args.no_zip:
            create_zip(folder, app_name)

    print(f"\n{'='*60}")
    print("  Done! Distribution files in dist/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
