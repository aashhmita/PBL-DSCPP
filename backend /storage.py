"""Tiny JSON persistence helper (standard library only)."""

import json
import os
import tempfile


def load_json(path):
    """Return the parsed JSON, or None if the file does not exist. Raises ValueError if corrupt."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)          # json.JSONDecodeError is a ValueError


def save_json(path, data):
    """Write atomically: write a temp file, then replace. A crash can never leave half a file."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
