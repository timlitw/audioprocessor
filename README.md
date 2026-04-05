# Audio Processor

A simple, free audio editor built for sound techs who need to clean up live performance recordings.

## The Problem

You had a singing service or program or wedding. The soundman has other duties at church so he gets there, turns the speaker system on, and the stream is started.

Now family or others want to listen and the file from Listen To Church has 30-60 minutes of either dead space or the sounds of people being ushered into place. The folks that get the audio file do not know where the actual event starts.

This is a simple free audio processor that can:
- Trim the beginning and end
- **Automatically find where the performance starts** (the killer feature)
- Trim dead spaces and mistakes
- Find and take out background hum, AC noise, etc.
- Play through to find and make small cuts
- Make quiet sections (like vows or a baptism) louder so they are audible

## Features

- **Open any audio format** -- WAV, MP3, FLAC, OGG, AIFF, M4A, WMA, AAC
- **Waveform display** -- zoom, scroll, click to place cursor, drag to select
- **Playback** -- play from cursor, play just a selection, keyboard shortcuts
- **Find Performance Start** -- automatically detects where the real event begins after the pre-show dead time
- **Cut & trim** -- delete selections, keep only a selection, full undo/redo
- **Normalize volume** -- make quiet recordings louder (peak or RMS)
- **Fade in/out** -- smooth fades at the start and end
- **Noise reduction** -- remove background hiss, HVAC hum, ambient noise
- **Hum removal** -- 50/60 Hz electrical hum and harmonics
- **Export to MP3** -- choose quality from 128-320 kbps
- **Dark theme** -- easy on the eyes, Audition-style compact layout

## Quick Start

### Requirements

- Python 3.12 or newer
- Windows 10/11

### Install

```bash
git clone https://github.com/timlitw/audioprocessor.git
cd audioprocessor
pip install -r requirements.txt
```

That's it. The `imageio-ffmpeg` package bundles ffmpeg automatically -- no separate install needed.

### Run

```bash
python main.py
```

## How to Use

### Opening a File

- **File > Open** (or Ctrl+O) to browse for an audio file
- Or **drag and drop** a file onto the window
- Recent files are remembered under **File > Recent Files**

### Navigation

- **Scroll wheel** -- scroll through the waveform
- **Ctrl + scroll wheel** -- zoom in/out centered on your mouse
- **Zoom +/-/Fit buttons** in the toolbar or transport bar
- **Home/End keys** -- jump to start/end of the file

### Playback

- **Single click** on the waveform to place the cursor
- **Space** -- play from cursor position (or pause if playing)
- **Click and drag** to select a region, then **Space** to play just that section

### Editing

1. **Select a region** by clicking and dragging on the waveform
2. **Delete** (or Del key) -- removes the selected section
3. **Keep** -- keeps only the selected section, deletes everything else
4. **Ctrl+Z** -- undo, **Ctrl+Shift+Z** -- redo
5. Right-click the waveform for a context menu with these options

### Finding Where the Performance Starts

This is the main reason this app exists:

1. Open your recording
2. Click **"Find Start"** in the toolbar (or Effects > Find Performance Start)
3. The app analyzes the audio and finds where the actual event begins
4. It asks if you want to select the pre-show dead time for deletion
5. Click **Yes**, review the selection, then hit **Delete**

### Making Quiet Parts Louder (Normalize)

1. Select the quiet section (like the vows at a wedding)
2. **Effects > Normalize** (or click **Normalize** in the toolbar)
3. Choose **Peak** normalization and set target to **-1 dB**
4. Click Normalize

Or to normalize the entire recording, press **Ctrl+A** first to select all.

### Removing Background Noise

1. First, **select a section that is ONLY noise** (no talking or music -- the pre-show silence works great)
2. Click **Noise Reduce** in the toolbar (or Effects > Noise Reduction)
3. Click **"Capture Noise Profile from Selection"**
4. Now select the region you want to clean (or Ctrl+A for the whole file)
5. Open Noise Reduction again, adjust strength if needed, click **Apply**

For electrical hum (HVAC, buzzing), check **"Remove electrical hum"** and pick 60 Hz (US) or 50 Hz (EU).

### Adding Fades

- **Effects > Fade In** -- smoothly fades in the beginning (set duration in seconds)
- **Effects > Fade Out** -- smoothly fades out the ending

### Saving

- **File > Save as MP3** (Ctrl+S) -- pick quality from 128-320 kbps
- **File > Save as WAV** -- lossless, larger file

## Typical Workflow

1. Open the recording
2. Click **Find Start** to locate where the event begins
3. Delete the pre-show dead time
4. Listen through, select and delete any dead spots or mistakes
5. Select a noise-only section, capture the noise profile
6. Select all (Ctrl+A), apply noise reduction
7. Normalize the volume
8. Add a fade in at the start and fade out at the end
9. Save as MP3

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+O | Open file |
| Ctrl+S | Save as MP3 |
| Space | Play / Pause |
| Home | Go to start |
| End | Go to end |
| Del | Delete selection |
| Ctrl+A | Select all |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z | Redo |
| Ctrl+= | Zoom in |
| Ctrl+- | Zoom out |
| Ctrl+0 | Zoom to fit |

## Open Source Libraries

This app is built with these open-source libraries:

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) -- GUI framework (GPL v3)
- [NumPy](https://numpy.org/) -- Numerical computing (BSD)
- [SciPy](https://scipy.org/) -- Signal processing (BSD)
- [soundfile](https://python-soundfile.readthedocs.io/) / libsndfile -- Audio I/O (BSD / LGPL)
- [sounddevice](https://python-sounddevice.readthedocs.io/) / PortAudio -- Audio playback (MIT)
- [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) / FFmpeg -- Media encoding (BSD / LGPL)

## License

Free to use and distribute.
