"""Platform policies independent of the host OS; no network or model downloads."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shelter_humanizer.panels import wheel_units
from shelter_humanizer.paths import data_directory
from shelter_humanizer.preferences import Preferences
from shelter_humanizer.providers import ProviderConfig
from shelter_humanizer.ui_helpers import shortcut_action


class PlatformTests(unittest.TestCase):
    def test_aqua_command_in_both_layouts_and_option_control_exclusion(self):
        for english, russian, action in (
            ("a", "Cyrillic_ef", "all"),
            ("c", "с", "copy"),
            ("v", "м", "paste"),
            ("x", "ч", "cut"),
            ("z", "я", "undo"),
        ):
            for key in (english, english.upper(), russian):
                self.assertEqual(shortcut_action(0, key, 8, aqua=True), action)
                self.assertIsNone(shortcut_action(0, key, 4, aqua=True))
                self.assertIsNone(shortcut_action(0, key, 8 | 16, aqua=True))
        self.assertEqual(shortcut_action(0, "я", 9, aqua=True), "redo")
        self.assertEqual(shortcut_action(0, "Z", 9, aqua=True), "redo")

    def test_scroll_preserves_small_aqua_deltas_and_other_platform_steps(self):
        self.assertEqual(wheel_units(-1, aqua=True), 1)
        self.assertEqual(wheel_units(4, aqua=True), -4)
        self.assertEqual(wheel_units(-240), 6)
        self.assertEqual(wheel_units(120), -3)
        self.assertEqual(wheel_units(0, 4), -3)
        self.assertEqual(wheel_units(0, 5), 3)
        self.assertEqual(wheel_units(0), 0)

    def test_macos_data_is_outside_bundle_and_ignores_windows_environment(self):
        with patch("sys.platform", "darwin"), patch.dict("os.environ", {"LOCALAPPDATA": "/tmp/no"}):
            self.assertEqual(
                data_directory(), Path.home() / "Library/Application Support/ShelterHumanizer"
            )

    def test_connection_survives_instruction_changes_and_never_stores_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            preferences = Preferences(Path(directory) / "settings.json")
            config = ProviderConfig(
                url="http://localhost:11434/api/chat",
                model="local:q4",
                key="secret",
                cpu_only=True,
                adaptive_context=False,
            )
            preferences.save_connection(config)
            preferences.save("Пиши ясно.")
            preferences.save(None)
            self.assertEqual(
                preferences.load(),
                {
                    "external_ollama": {
                        "url": "http://localhost:11434",
                        "model": "local:q4",
                        "adaptive_context": False,
                    }
                },
            )
            self.assertNotIn("secret", preferences.path.read_text())
            self.assertNotIn("cpu_only", preferences.path.read_text())
            preferences.save_connection(None)
            self.assertFalse(preferences.path.exists())

    def test_invalid_saved_connection_is_not_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            preferences = Preferences(Path(directory) / "settings.json")
            for value in (
                {"url": "http://external.test", "model": "x"},
                {"url": "https://user:secret@example.org", "model": "x"},
                {"url": [], "model": "x"},
                {"url": "http://localhost:11434", "model": 3},
            ):
                preferences.path.write_text(json.dumps({"external_ollama": value}))
                self.assertEqual(preferences.load(), {})
