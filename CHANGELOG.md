# Changelog

## [0.1.0] - 2026-04-04

### Added
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
