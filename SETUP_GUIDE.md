# Beginner Setup Guide

This guide walks you through everything you need to install and run Audio Processor and Transcription Studio from scratch — even if you've never used Python or a command line before.

---

## Quick Install (Windows) — Recommended

If you're on Windows and just want to use the apps, skip everything below and grab the installer:

1. Go to the [Releases page](https://github.com/timlitw/audioprocessor/releases/latest)
2. Download **`AudioProcessor-Setup-vX.Y.Z.exe`** under **Assets**
3. Double-click the installer and follow the prompts
4. Launch **Audio Processor** or **Transcription Studio** from the Start Menu

That's it — no Python, no Git, no command line. The installer bundles everything both apps need.

The rest of this guide is for developers, macOS users, or anyone who wants to run the apps from source.

---

## What You'll Need

- A computer running **Windows 10/11** or **macOS**
- An internet connection
- About 15 minutes (plus download time)

---

## Step 1: Install Python

Audio Processor requires **Python 3.12 or newer**.

### Windows

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the big yellow **"Download Python 3.x.x"** button
3. Run the installer
4. **Important:** Check the box that says **"Add python.exe to PATH"** at the bottom of the first screen — this is easy to miss and things won't work without it
5. Click **"Install Now"**

To verify it worked, open **Command Prompt** (search for `cmd` in the Start menu) and type:

```
python --version
```

You should see something like `Python 3.12.x` or newer.

### macOS

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download the macOS installer
3. Run it and follow the prompts

To verify, open **Terminal** (search for it in Spotlight) and type:

```
python3 --version
```

> **Note for macOS users:** macOS comes with an older Python. Always use `python3` and `pip3` instead of `python` and `pip` in all the commands below.

---

## Step 2: Install Git

Git lets you download (clone) the project from GitHub.

### Windows

1. Go to [git-scm.com/downloads/win](https://git-scm.com/downloads/win)
2. Download and run the installer
3. Use the default settings — just keep clicking **Next** until it finishes

### macOS

Open Terminal and type:

```
git --version
```

If Git isn't installed, macOS will prompt you to install the Xcode Command Line Tools. Click **Install** and wait for it to finish.

---

## Step 3: Download the Project

Open **Command Prompt** (Windows) or **Terminal** (macOS) and run these commands one at a time:

```
git clone https://github.com/timlitw/audioprocessor.git
cd audioprocessor
```

This creates a folder called `audioprocessor` and moves you into it.

---

## Step 4: Install Dependencies for Audio Processor

Still in the `audioprocessor` folder, run:

**Windows:**
```
pip install -r requirements.txt
```

**macOS:**
```
pip3 install -r requirements.txt
```

This installs PyQt6 (the app window), NumPy, SciPy, and the other libraries the app needs. The `imageio-ffmpeg` package bundles ffmpeg automatically — no separate install needed.

---

## Step 5: Run Audio Processor

**Windows:**
```
python main.py
```

**macOS:**
```
python3 main.py
```

The Audio Processor window should open. You're ready to go!

---

## Step 6: Install and Run Transcription Studio (Optional)

Transcription Studio has additional dependencies for speech-to-text. From the project root folder:

**Windows:**
```
cd transcription_studio
pip install -r requirements.txt
```

**macOS:**
```
cd transcription_studio
pip3 install -r requirements.txt
```

This installs `faster-whisper` for local transcription. The first time you transcribe, the Whisper model will download automatically (~500 MB for small, ~1.5 GB for medium, ~3 GB for large-v3).

To run Transcription Studio:

**Windows:**
```
python main.py
```

**macOS:**
```
python3 main.py
```

> **Tip:** To go back to the Audio Processor later, navigate back to the project root with `cd ..` and run `python main.py` from there.

---

## Building Standalone Executables (Advanced)

If you want to create a `.exe` that runs without Python installed (useful for sharing with others), you'll need PyInstaller:

```
pip install pyinstaller
```

Then from the project root:

```
python build.py
```

This builds both apps. You can also build them individually:

```
python build.py audio          # Audio Processor only
python build.py transcription  # Transcription Studio only
```

The finished executables and zip files will be in the `dist/` folder.

---

## Troubleshooting

### "python is not recognized" (Windows)

Python wasn't added to your PATH during installation. The easiest fix:

1. Uninstall Python from **Settings > Apps**
2. Reinstall it and make sure to check **"Add python.exe to PATH"**

### "pip is not recognized" (Windows)

Try using `python -m pip` instead of `pip`:

```
python -m pip install -r requirements.txt
```

### Permission errors on macOS

If you get permission errors with `pip3`, try:

```
pip3 install --user -r requirements.txt
```

### The app window doesn't open or crashes immediately

Make sure you're using Python 3.12 or newer:

```
python --version
```

If you have an older version, download the latest from [python.org](https://www.python.org/downloads/).

### Transcription is slow

Whisper runs on your CPU by default. The **small** model is fastest, **medium** is a good balance, and **large-v3** is most accurate but slowest. If you have an NVIDIA GPU, `faster-whisper` can use it automatically for a significant speed boost — see the [faster-whisper docs](https://github.com/SYSTRAN/faster-whisper) for GPU setup.

---

## Next Steps

Once you're up and running, head back to the [main README](README.md) for detailed usage instructions, keyboard shortcuts, and workflow guides.
