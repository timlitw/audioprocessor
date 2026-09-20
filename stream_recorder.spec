# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Stream Recorder."""

from PyInstaller.utils.hooks import collect_data_files

# ffmpeg binary
sr_datas = collect_data_files('imageio_ffmpeg')

# Windows has no system time zone database, so zoneinfo reads it from the
# tzdata package. Without this the church time zone pickers fail in the
# frozen app even though they work when run from source.
sr_datas += collect_data_files('tzdata')

a = Analysis(
    ['stream_recorder/main.py'],
    pathex=['stream_recorder'],
    binaries=[],
    datas=sr_datas,
    hiddenimports=['tzdata'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'PIL', 'IPython', 'notebook',
        'numpy', 'scipy', 'pandas', 'torch', 'faster_whisper', 'ctranslate2',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='StreamRecorder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='StreamRecorder',
)
