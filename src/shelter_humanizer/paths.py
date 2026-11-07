"""Writable user data locations, independent of working directory and app bundle."""

import os
import sys
from pathlib import Path


def data_directory():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ShelterHumanizer"
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "ShelterHumanizer"
