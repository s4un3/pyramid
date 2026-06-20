import datetime
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class JSONStore:
    _copy = lambda _, o: json.loads(json.dumps(o))

    def __init__(
        self,
        path: str | Path,
        default_data: dict[str, Any] | None = None,
    ):
        self._path = Path(path)
        self._default_data = (
            self._copy(default_data) if default_data is not None else {}
        )
        self.data: dict[str, Any] = {}

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.load()

    def load(self) -> None:
        if not self._path.exists():
            self._reset_to_default()
            self.save()
            return

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)

            if not isinstance(loaded_data, dict):
                raise TypeError("JSON root must be an object/dictionary.")

            self.data = loaded_data

        except (json.JSONDecodeError, OSError, TypeError) as e:
            old_path = str(self._path)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self._path.with_suffix(f".bak.{timestamp}")

            try:
                self._path.replace(backup_path)
                logger.warning(
                    f"File '{old_path}' could not be loaded. Old data moved to '{backup_path}' and default loaded."
                )
            except OSError:
                logger.error(f"Could not backup corrupted file at {self._path}")

            self._reset_to_default()

    def save(self) -> None:
        temp_path = self._path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)

            temp_path.replace(self._path)
        except (OSError, TypeError, ValueError) as e:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise RuntimeError(f"Atomic save failed for {self._path}") from e

    def get(self, key: str, fallback: Any = None) -> Any:
        """
        Reads a key with support for inline default values.
        Checks current data, then default, then the fallback argument.
        """
        if key in self.data:
            return self.data[key]
        return self._default_data.get(key, fallback)

    def _reset_to_default(self) -> None:
        self.data = json.loads(json.dumps(self._default_data))
