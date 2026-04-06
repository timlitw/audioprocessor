# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Transcription Studio."""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Collect imageio_ffmpeg data (ffmpeg binary)
ts_datas = collect_data_files('imageio_ffmpeg')

# Collect faster_whisper assets (silero_vad_v6.onnx)
ts_datas += collect_data_files('faster_whisper')

# Collect ctranslate2 binaries manually (avoid collect_all which triggers bytecode scanning bug)
import ctranslate2 as _ct2
_ct2_dir = os.path.dirname(_ct2.__file__)
ts_binaries = []
for f in os.listdir(_ct2_dir):
    if f.endswith(('.dll', '.so', '.pyd')):
        ts_binaries.append((os.path.join(_ct2_dir, f), 'ctranslate2'))

a = Analysis(
    ['transcription_studio/main.py'],
    pathex=['transcription_studio'],
    binaries=ts_binaries,
    datas=ts_datas,
    hiddenimports=[
        'scipy.signal',
        'scipy.signal._signaltools',
        'scipy.signal._spectral_py',
        'scipy.fft._pocketfft',
        '_sounddevice_data',
        'soundfile',
        'faster_whisper',
        'ctranslate2',
        'ctranslate2._ext',
        'huggingface_hub',
        'tokenizers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL', 'IPython', 'notebook', 'torch'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TranscriptionStudio',
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
    name='TranscriptionStudio',
)
