# Audio Processor + Transcription Studio

Two free tools for sound techs who record live performances at churches, weddings, and events.

## The Problem

You had a singing service or program or wedding. The soundman has other duties at church so he gets there, turns the speaker system on, and the stream is started.

Now family or others want to listen and the file from Listen To Church has 30-60 minutes of either dead space or the sounds of people being ushered into place. The folks that get the audio file do not know where the actual event starts.

## The Solution: Two Tools

### Tool 1: Audio Processor
The **quick tool** for Sunday morning. Open the recording, find where the event starts, trim the dead time, clean up the audio, export as MP3. Done in 5 minutes, file goes out to the congregation.

### Tool 2: Transcription Studio
The **sit-down tool** for when you have time. Transcribe the audio (runs locally, no cloud, no cost), name the speakers, edit the transcript, then generate a shareable video with ambient backgrounds, speaker names, and synced text -- ready for YouTube or the church website.

---

# Tool 1: Audio Processor

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

The `imageio-ffmpeg` package bundles ffmpeg automatically -- no separate install needed.

### Run

```bash
python main.py
```

## How to Use the Audio Processor

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

This is the main reason this tool exists:

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

### Typical Audio Processor Workflow

1. Open the recording
2. Click **Find Start** to locate where the event begins
3. Delete the pre-show dead time
4. Listen through, select and delete any dead spots or mistakes
5. Select a noise-only section, capture the noise profile
6. Select all (Ctrl+A), apply noise reduction
7. Normalize the volume
8. Add a fade in at the start and fade out at the end
9. Save as MP3

### Audio Processor Keyboard Shortcuts

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

---

# Tool 2: Transcription Studio

A two-tab app for transcribing audio and generating shareable videos.

## Features

### Transcribe Tab
- **Whisper transcription** -- runs locally on your machine, no internet or API key needed
- **Word-level timestamps** -- every word is timed for precise video sync
- **Editable transcript** -- double-click any text to correct mistakes
- **Speaker names** -- double-click the Speaker column to name who's talking; the name carries forward until the next change
- **Segment controls** -- right-click to split, merge, delete segments or mark sections as singing
- **Click any segment** to hear it play back
- **Tab** replays the current segment, **Enter** jumps to the next one
- **Background triggers** -- right-click a segment to change the video background at that point (choose a procedural style or pick an image)
- **Save/load projects** -- saves as a JSON file next to the audio (same name), pick up where you left off

### Video Tab
- **5 procedural backgrounds** -- Warm Bokeh (ambient light orbs), Starfield, Gradient Sweep, Waves, Solid Dark
- **Custom backgrounds** -- pick one image (static) or multiple images (slideshow with crossfade)
- **4 text display styles:**
  - Sentence at a Time -- one sentence centered, fades between segments
  - Subtitle (Bottom) -- classic subtitle look with dark background box
  - Word-by-Word Highlight -- current word highlighted in yellow as it's spoken
  - Scroll Up -- teleprompter style, text scrolls upward
- **Speaker names** -- shown at top center when the voice changes, color-coded
- **Singing sections** -- displayed with music note decorations
- **Preview with audio** -- see and hear how the video will look before rendering
- **Snapshot** -- render a single frame to check the look
- **Render to MP4** -- H.264 + AAC, plays in Windows Media Player, ready for YouTube
- **Resolution picker** -- 720p, 1080p, or 4K

## Install Transcription Studio

```bash
cd transcription_studio
pip install -r requirements.txt
```

This installs `faster-whisper` for transcription. The Whisper model (~150MB for "base") downloads automatically on first use.

### Run

```bash
cd transcription_studio
python main.py
```

## How to Use the Transcription Studio

### Transcribing

1. Click **Open Audio** and select your cleaned MP3 (from the Audio Processor)
2. Choose a **model size** -- "tiny" is fastest, "base" is a good balance, "medium" is most accurate
3. Click **Transcribe** -- segments appear live as Whisper processes the audio
4. When done, review the transcript and fix any mistakes

### Editing the Transcript

- **Double-click the Text column** to fix words Whisper got wrong
- **Double-click the Speaker column** to name who's talking -- the name carries forward to all segments below until you change it again
- **Right-click a segment** for more options:
  - Set type to Speech, Singing, or Silence
  - Split a segment at the midpoint
  - Merge with the previous or next segment
  - Delete a segment
  - Set a background change at that point
- **Tab** = replay the current segment (useful while editing)
- **Enter** = move to the next segment and play it

### Setting Up Background Changes

If you're using custom images or want to switch styles during the video:

1. Right-click a segment where you want the background to change
2. Choose **Set Background Change Here**
3. Pick a procedural background (Warm Bokeh, Starfield, etc.) or **Choose Image...**
4. The BG column shows a marker where changes happen
5. That background stays until the next change point

### Generating the Video

1. Switch to the **Video tab**
2. Choose your **background** -- procedural, custom image, or the triggers you set in the transcript
3. Choose your **text style** -- Sentence at a Time, Subtitle, Word-by-Word, or Scroll Up
4. Choose your **resolution** -- 720p, 1080p, or 4K
5. Click **Snapshot** to preview a single frame
6. Click **Preview with Audio** to see and hear a live preview
7. Click **Render MP4** to create the final video file

The output MP4 plays in Windows Media Player and is ready to upload to YouTube, Facebook, or your church website.

### Typical Transcription Studio Workflow

1. Open the cleaned audio from the Audio Processor
2. Transcribe with Whisper (base model)
3. Listen through, fix any transcription errors
4. Name the speakers (Pastor, Reader, etc.)
5. Mark singing sections if Whisper got them garbled
6. Optionally set background change points
7. Switch to Video tab, pick style and background
8. Preview, then Render MP4
9. Upload to YouTube or share the file

### Transcription Studio Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+O | Open audio file |
| Ctrl+S | Save project |
| Space | Play / Pause (or toggle video preview) |
| Tab | Replay current segment |
| Enter | Next segment and play |

---

## Project Files

When you save a project, the files are kept together:

```
Your Recording.mp3          # Cleaned audio from Audio Processor
Your Recording.json         # Transcript, speakers, timing, background triggers
Your Recording.mp4          # Generated video (from Transcription Studio)
```

## Open Source Libraries

These tools are built with these open-source libraries:

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) -- GUI framework (GPL v3)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) -- Speech recognition (MIT)
- [NumPy](https://numpy.org/) -- Numerical computing (BSD)
- [SciPy](https://scipy.org/) -- Signal processing (BSD)
- [soundfile](https://python-soundfile.readthedocs.io/) / libsndfile -- Audio I/O (BSD / LGPL)
- [sounddevice](https://python-sounddevice.readthedocs.io/) / PortAudio -- Audio playback (MIT)
- [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) / FFmpeg -- Media encoding (BSD / LGPL)

## License

Free to use and distribute.
