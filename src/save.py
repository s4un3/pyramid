from pathlib import Path
import json
from warnings import warn
import dill
from typing import Any


class _ManagedData:
    def __init__(self, default: dict[str, Any] | None = None):
        self.__dict__["_data"] = default

    def __getattr__(self, name: str, /) -> Any:
        try:
            return self._data[name]
        except KeyError as e:
            raise AttributeError(
                f"'_ManagedData' object has no attribute '{name}'"
            ) from e

    def __setattr__(self, name: str, value: Any, /) -> None:
        if name == "_data":
            self.__dict__["_data"] = value
        else:
            self._data[name] = value

    def __delattr__(self, name: str) -> None:
        try:
            del self._data[name]
        except KeyError as e:
            raise AttributeError(
                f"'_ManagedData' object has no attribute '{name}'"
            ) from e

    def __contains__(self, name: str) -> bool:
        return name in self._data

    def __repr__(self) -> str:
        return f"_ManagedData({self._data})"


class FileSave:
    _extensions = {
        ".json": "json",
        ".pkl": "pickle",
        ".pickle": "pickle",
    }

    def __init__(self, path: Path, default: dict[str, Any] | None = None):
        self._path = Path(path)
        self._ext = self._path.suffix.lower()

        if self._ext not in self._extensions:
            raise ValueError(
                f"Unsupported file extension '{self._ext}'. Supported extensions are: {', '.join(self._extensions.keys())}"
            )

        self._path.parent.mkdir(parents=True, exist_ok=True)

        self.data = _ManagedData(default)
        self._default = {} if default is None else default.copy()
        self.load()

    def save(self) -> None:
        """Saves the internal data dictionary to the specified path."""
        match self._extensions[self._ext]:
            case "json":
                with open(self._path, "w", encoding="utf-8") as f:
                    json.dump(self.data._data, f, indent=4)
            case "pickle":
                with open(self._path, "wb") as f:
                    dill.dump(self.data._data, f)

    def load(self) -> None:
        """Loads data from the file back into the internal data dictionary."""
        if not self._path.exists():
            self.save()
            return

        loaded_data: dict[str, Any] | None = None
        try:
            match self._extensions[self._ext]:
                case "json":
                    with open(self._path, "r", encoding="utf-8") as f:
                        loaded_data = json.load(f)
                case "pickle":
                    with open(self._path, "rb") as f:
                        loaded_data = dill.load(f)
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            dill.UnpicklingError,
            EOFError,
            ImportError,
            AttributeError,
        ) as e:
            warn(
                f"Could not decode file '{self._path}'. It may have been corrupted. Using default value. Exception: {e}"
            )
            if self._default is None:
                raise ValueError(
                    f"Had to use default value for object but no default was provided."
                ) from e
            loaded_data = self._default

        if loaded_data is None:
            return

        self.data._data = loaded_data
