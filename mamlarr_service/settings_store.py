from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class SettingsStore:
    """Persists mutable settings to disk so UI changes survive restarts."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return {}

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Overwrite store with the provided dictionary."""
        # convert Path objects to str for JSON compatibility
        serializable = {
            key: (str(value) if isinstance(value, Path) else value)
            for key, value in data.items()
        }
        self.path.write_text(json.dumps(serializable, indent=2, sort_keys=True))
        return data

    def update(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Merge changes into stored settings."""
        current = self.load()
        current.update(
            {
                key: (str(value) if isinstance(value, Path) else value)
                for key, value in changes.items()
            }
        )
        self.save(current)
        return current
