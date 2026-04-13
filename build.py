"""Build both apps with PyInstaller and create distribution zips."""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
ISCC = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")


def get_version() -> str:
    ns: dict = {}
    exec((PROJECT_DIR / "app" / "__init__.py").read_text(), ns)
    return ns["__version__"]


def build_installer(version: str) -> Path:
    print(f"\n{'='*60}\n  Building installer v{version}\n{'='*60}\n")
    if not ISCC.exists():
        print(f"ERROR: Inno Setup not found at {ISCC}")
        sys.exit(1)
    cmd = [str(ISCC), f"/DAppVersion={version}", "installer.iss"]
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))
    if result.returncode != 0:
        print("\nERROR: installer build failed!")
        sys.exit(1)
    out = PROJECT_DIR / "dist" / f"AudioProcessor-Setup-v{version}.exe"
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"\nInstaller: {out.name} ({size_mb:.1f} MB)")
    return out

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
        sys.executable, "-B", "-m", "PyInstaller",
        str(spec_path),
        "--distpath", str(dist_dir),
        "--workpath", str(work_dir),
        "--noconfirm",
    ]

    # PyInstaller's modulegraph crashes scanning freshly-written .pyc files on
    # Python 3.13. Suppress bytecode writing for the build subprocess.
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR), env=env)
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
    parser.add_argument("--installer", action="store_true", help="Build Inno Setup installer after PyInstaller (requires both apps)")
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

    if args.installer:
        if args.app != "both":
            print("\nERROR: --installer requires building both apps")
            sys.exit(1)
        build_installer(get_version())

    print(f"\n{'='*60}")
    print("  Done! Distribution files in dist/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
