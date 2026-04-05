"""Undo/redo manager using command pattern with delta and full snapshots."""

import zlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np


@dataclass
class UndoEntry:
    """One undoable operation."""
    description: str
    # For delta ops: store the affected region
    region_start: int = 0
    region_data: bytes = b""  # zlib-compressed numpy bytes
    region_shape: tuple = ()
    region_dtype: str = "float32"
    # For full ops: compressed full audio
    is_full: bool = False
    sample_rate: int = 44100
    # Disk spill path (for large entries)
    disk_path: str | None = None

    @property
    def memory_size(self) -> int:
        return len(self.region_data)


class UndoManager:
    """Manages undo/redo stacks with memory budget."""

    def __init__(self, max_depth: int = 50, memory_budget_mb: int = 2048):
        self._undo_stack: list[UndoEntry] = []
        self._redo_stack: list[UndoEntry] = []
        self._max_depth = max_depth
        self._memory_budget = memory_budget_mb * 1024 * 1024
        self._temp_dir = Path(tempfile.gettempdir()) / "audio_processor_undo"

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def undo_description(self) -> str:
        if self._undo_stack:
            return self._undo_stack[-1].description
        return ""

    @property
    def redo_description(self) -> str:
        if self._redo_stack:
            return self._redo_stack[-1].description
        return ""

    def push_full(self, description: str, audio_data: np.ndarray, sample_rate: int):
        """Save a full snapshot before a global operation (normalize, noise reduce)."""
        compressed = zlib.compress(audio_data.tobytes(), level=1)
        entry = UndoEntry(
            description=description,
            region_data=compressed,
            region_shape=audio_data.shape,
            region_dtype=str(audio_data.dtype),
            is_full=True,
            sample_rate=sample_rate,
        )
        self._push(entry)

    def push_delete(self, description: str, start: int, deleted_data: np.ndarray, sample_rate: int):
        """Save the deleted region before a delete/trim operation."""
        compressed = zlib.compress(deleted_data.tobytes(), level=1)
        entry = UndoEntry(
            description=description,
            region_start=start,
            region_data=compressed,
            region_shape=deleted_data.shape,
            region_dtype=str(deleted_data.dtype),
            is_full=False,
            sample_rate=sample_rate,
        )
        self._push(entry)

    def push_region(self, description: str, start: int, original_data: np.ndarray, sample_rate: int):
        """Save a region before an in-place operation (fade, etc.)."""
        compressed = zlib.compress(original_data.tobytes(), level=1)
        entry = UndoEntry(
            description=description,
            region_start=start,
            region_data=compressed,
            region_shape=original_data.shape,
            region_dtype=str(original_data.dtype),
            is_full=False,
            sample_rate=sample_rate,
        )
        self._push(entry)

    def _push(self, entry: UndoEntry):
        self._redo_stack.clear()
        self._undo_stack.append(entry)

        # Enforce max depth
        while len(self._undo_stack) > self._max_depth:
            old = self._undo_stack.pop(0)
            self._cleanup_entry(old)

        # Enforce memory budget
        self._enforce_memory_budget()

    def undo(self, current_audio: np.ndarray) -> np.ndarray | None:
        """Undo the last operation. Returns the restored audio array."""
        if not self._undo_stack:
            return None

        entry = self._undo_stack.pop()
        data = self._decompress(entry)

        if entry.is_full:
            # Save current state for redo
            redo_compressed = zlib.compress(current_audio.tobytes(), level=1)
            redo_entry = UndoEntry(
                description=entry.description,
                region_data=redo_compressed,
                region_shape=current_audio.shape,
                region_dtype=str(current_audio.dtype),
                is_full=True,
                sample_rate=entry.sample_rate,
            )
            self._redo_stack.append(redo_entry)
            return data.reshape(entry.region_shape)
        else:
            # Delta undo: this was a delete operation, re-insert the deleted data
            restored_chunk = data.reshape(entry.region_shape)
            pos = entry.region_start

            # Save current state for redo (the data that's currently at this position)
            # For a delete-undo (re-insert), the redo needs to know to delete again
            redo_entry = UndoEntry(
                description=entry.description,
                region_start=pos,
                region_data=entry.region_data,
                region_shape=entry.region_shape,
                region_dtype=entry.region_dtype,
                is_full=False,
                sample_rate=entry.sample_rate,
            )
            self._redo_stack.append(redo_entry)

            # Re-insert the deleted data
            result = np.concatenate([
                current_audio[:pos],
                restored_chunk,
                current_audio[pos:]
            ], axis=0)
            return result

    def redo(self, current_audio: np.ndarray) -> np.ndarray | None:
        """Redo the last undone operation."""
        if not self._redo_stack:
            return None

        entry = self._redo_stack.pop()
        data = self._decompress(entry)

        if entry.is_full:
            # Save current for undo
            undo_compressed = zlib.compress(current_audio.tobytes(), level=1)
            undo_entry = UndoEntry(
                description=entry.description,
                region_data=undo_compressed,
                region_shape=current_audio.shape,
                region_dtype=str(current_audio.dtype),
                is_full=True,
                sample_rate=entry.sample_rate,
            )
            self._undo_stack.append(undo_entry)
            return data.reshape(entry.region_shape)
        else:
            # Delta redo: delete the region again
            restored_chunk = data.reshape(entry.region_shape)
            pos = entry.region_start
            chunk_len = len(restored_chunk)

            # Save for undo
            undo_entry = UndoEntry(
                description=entry.description,
                region_start=pos,
                region_data=entry.region_data,
                region_shape=entry.region_shape,
                region_dtype=entry.region_dtype,
                is_full=False,
                sample_rate=entry.sample_rate,
            )
            self._undo_stack.append(undo_entry)

            # Delete the region
            result = np.concatenate([
                current_audio[:pos],
                current_audio[pos + chunk_len:]
            ], axis=0)
            return result

    def _decompress(self, entry: UndoEntry) -> np.ndarray:
        raw = zlib.decompress(entry.region_data)
        return np.frombuffer(raw, dtype=entry.region_dtype).copy()

    def _enforce_memory_budget(self):
        total = sum(e.memory_size for e in self._undo_stack)
        while total > self._memory_budget and len(self._undo_stack) > 1:
            old = self._undo_stack.pop(0)
            total -= old.memory_size
            self._cleanup_entry(old)

    def _cleanup_entry(self, entry: UndoEntry):
        if entry.disk_path:
            try:
                Path(entry.disk_path).unlink(missing_ok=True)
            except Exception:
                pass

    def clear(self):
        """Clear all undo/redo history."""
        for entry in self._undo_stack + self._redo_stack:
            self._cleanup_entry(entry)
        self._undo_stack.clear()
        self._redo_stack.clear()
