import datetime as _datetime
import json as _json
import logging as _logging
from pathlib import Path as _Path
from typing import Any as _Any

__all__ = [
    "JSONStore",
]


class JSONStore:
    """Persistent JSON storage with default fallback, backup handling, and atomic saves."""

    logger = _logging.getLogger(__name__)

    _copy = lambda _, o: _json.loads(_json.dumps(o))

    def __init__(
        self,
        path: str | _Path,
        default_data: dict[str, _Any] | None = None,
    ):
        """Creates or loads a JSON store at the provided path, preserving defaults."""
        self._path = _Path(path)
        self._default_data = (
            self._copy(default_data) if default_data is not None else {}
        )
        self.data: dict[str, _Any] = {}

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.load()

    def load(self) -> None:
        """Loads JSON data from disk, restoring defaults and backing up invalid files when needed."""
        if not self._path.exists():
            self._reset_to_default()
            self.save()
            return

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                loaded_data = _json.load(f)

            if not isinstance(loaded_data, dict):
                raise TypeError("JSON root must be an object/dictionary.")

            self.data = loaded_data

        except (_json.JSONDecodeError, OSError, TypeError) as e:
            old_path = str(self._path)
            timestamp = _datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self._path.with_suffix(f".bak.{timestamp}")

            try:
                self._path.replace(backup_path)
                self.logger.warning(
                    f"File '{old_path}' could not be loaded. Old data moved to '{backup_path}' and default loaded."
                )
            except OSError:
                self.logger.error(f"Could not backup corrupted file at {self._path}")

            self._reset_to_default()

    def save(self) -> None:
        """Atomically writes the current JSON data to disk via a temporary file."""
        temp_path = self._path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                _json.dump(self.data, f, indent=4)

            temp_path.replace(self._path)
        except (OSError, TypeError, ValueError) as e:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise RuntimeError(f"Atomic save failed for {self._path}") from e

    def _reset_to_default(self) -> None:
        """Resets the current store data to a deep copy of the default values."""
        self.data = _json.loads(_json.dumps(self._default_data))

    def __getitem__(self, key: str) -> _Any:
        """Retrieves a nested value using dot-separated keys, falling back to defaults."""
        parts = key.split(".")

        try:
            current = self.data
            for part in parts:
                current = current[part]
            return current
        except (KeyError, TypeError):
            pass

        try:
            current = self._default_data
            for part in parts:
                current = current[part]
            return self._copy(current)
        except (KeyError, TypeError):
            raise KeyError(f"Key '{key}' not found in data or defaults.")

    def __setitem__(self, key: str, value: _Any) -> None:
        """Sets a nested value using dot-separated keys, creating intermediate dictionaries as needed."""
        parts = key.split(".")
        current = self.data

        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    def __delitem__(self, key: str) -> None:
        """Deletes a nested key from the data store, raising if it does not exist."""
        parts = key.split(".")
        current = self.data

        try:
            for part in parts[:-1]:
                current = current[part]
            del current[parts[-1]]
        except (KeyError, TypeError):
            raise KeyError(f"Key '{key}' cannot be deleted because it does not exist.")

    def __contains__(self, key: str) -> bool:
        """Returns True when the given dot-separated key exists in current or default data."""
        try:
            self[key]
            return True
        except KeyError:
            return False
