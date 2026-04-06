# Changelog

## [0.3.0] - 2026-04-06

### Added — Lyrics Matching System
- **Lyrics library:** Scans `.md`/`.txt` files from configurable lyrics directory (default: `~/OneDrive/Music/lyrics`)
- **Auto-detect during transcription:** Automatically identifies known songs and replaces Whisper's garbled words with correct lyrics, preserving word-level timestamps
- **Sequential song tracking:** Once a song is detected, follows along line-by-line through the performance, handling verse/chorus order
- **Chorus loopback:** Repeated choruses are matched correctly regardless of how many times they're sung
- **Manual "Match Lyrics":** Right-click any segment to force a lyrics lookup with confirmation dialog
- **Sequential approval flow:** After approving a match, automatically proposes the next line with Yes/No/Cancel and "Approve all remaining" checkbox
- **"Save as Song...":** Select segments, right-click to save corrected lyrics to the library for future auto-matching; auto-groups into sections based on timing gaps
- **"Group Song Lines":** Merges consecutive matched lyrics into 2-3 line chunks (like church projector slides), respecting verse/chorus section boundaries
- **Post-transcription cleanup:** After transcription, automatically re-matches fragmented segments and groups lyrics into display-friendly chunks
- **Word alignment:** Maps Whisper's timestamps onto correct lyrics words using sequence alignment, ensuring video text sync even when word counts differ

### Changed
- **Whisper models:** Removed tiny/base models, added large-v3 (best quality); default changed to medium
- **Whisper settings:** Added `condition_on_previous_text=False` and `no_speech_threshold=0.6` to prevent looping on music
- **Multi-select in transcript table:** Changed from single to extended selection for selecting song segments
- **Inline editing:** Edit field now has visible blue border, larger font, and row expands when editing for better visibility
- **Review workflow:** After editing a segment while paused, playback auto-resumes from that segment

### Added — PyInstaller Distribution
- **Build system:** `build.py` script with `audio_processor.spec` and `transcription_studio.spec`
- **Two separate distributions:** AudioProcessor (~112 MB zip) and TranscriptionStudio (~208 MB zip)
- **onedir mode:** Fast startup, distributed as zip folders (extract and run)

### Fixed
- Video preview now includes singing-type segments (was skipping them)
- Cross-project import hack replaced with clean local copy of `file_io.py` in transcription_studio

---

## [0.2.0] - 2026-04-05

### Added — Transcription Studio (Tool 2)
- **New app:** Transcription Studio with two tabs (Transcribe + Video)
- **Whisper transcription:** Local speech-to-text using faster-whisper, no cloud API needed
- **Word-level timestamps:** Every word timed for precise video sync
- **Model selector:** Choose tiny/base/small/medium Whisper models
- **Live transcription:** Segments appear in real-time as Whisper processes
- **Editable transcript table:** Double-click text to correct mistakes
- **Sticky speaker names:** Double-click Speaker column to name who's talking; carries forward until next change
- **Segment editing:** Right-click to split, merge, delete, or change type (speech/singing/silence)
- **Segment playback:** Click any row to hear it, Tab replays current, Enter jumps to next
- **Save/load projects:** JSON file saved alongside audio with matching filename
- **Background change triggers:** Right-click a segment to switch the video background at that point (procedural or custom image)
- **5 procedural backgrounds:** Warm Bokeh (animated light orbs), Starfield (twinkling), Gradient Sweep (color shifts), Waves (ocean animation), Solid Dark
- **Custom image backgrounds:** Single static image or multiple images as slideshow with crossfade
- **4 text display styles:** Sentence at a Time, Subtitle (Bottom), Word-by-Word Highlight, Scroll Up
- **Speaker names in video:** Shown at top center the entire time that speaker is active, color-coded
- **Singing display:** Music note decorations for singing segments
- **Auto-scaling text:** Font size adjusts to fit long segments without cutoff
- **Text outline rendering:** Clean readability over any background
- **Video preview with audio:** See and hear the video before rendering
- **Snapshot preview:** Render a single frame to check the look
- **Render to MP4:** H.264 + AAC in MP4 container, resolution picker (720p/1080p/4K)
- **Universal playback:** Output plays in Windows Media Player, VLC, YouTube, Telegram, WhatsApp, Android
- **Fast-start encoding:** `-movflags +faststart` for web streaming

### Fixed
- MP4 encoding now uses `yuv420p` pixel format for universal compatibility (fixes 0x80004005 error in WMP)
- Text no longer cut off at bottom of video frames
- Text artifacts from bokeh orbs rendering over text eliminated
- Speaker name no longer clips at top of frame
- Speaker name stays visible entire time (was only showing for 3 seconds)
- Re-transcription now clears previous segments instead of appending

---

## [0.1.0] - 2026-04-04

### Added — Audio Processor (Tool 1)
- Initial release — all core features working
- **File I/O:** Open WAV, MP3, FLAC, OGG, AIFF, M4A, WMA, AAC files
- **Waveform display:** Multi-resolution peak cache, dark theme (green on dark gray), time ruler
- **Zoom & scroll:** Ctrl+scroll to zoom on cursor, zoom buttons, Fit, Zoom to Selection
- **Playback:** Play/pause (Space), stop, auto-scroll playhead, play from cursor or selection
- **Cursor & selection:** Single click places cursor, click-drag selects region
- **Editing:** Delete selection, Keep selection, Select All with full undo/redo (Ctrl+Z / Ctrl+Shift+Z)
- **Find Performance Start:** Automatic detection of where the actual event begins after pre-show dead time
- **Normalize:** Peak or RMS normalization with configurable target level
- **Fade in/out:** Configurable duration fades
- **Noise reduction:** Spectral subtraction (capture noise profile from quiet section, then apply) with strength/floor controls
- **Hum removal:** 50/60 Hz electrical hum notch filter with harmonics
- **Export:** MP3 (128-320 kbps quality picker) and WAV
- **Settings persistence:** Recent files list, last directory remembered between sessions
- **Drag and drop:** Drop audio files onto the window to open
- **About dialog:** Open-source library disclosure
- **Keyboard shortcuts:** Space (play/pause), Home/End (navigate), Del (delete selection), Ctrl+O/S/Z/Shift+Z/A
- **Bundled ffmpeg** via imageio-ffmpeg — no system install required
