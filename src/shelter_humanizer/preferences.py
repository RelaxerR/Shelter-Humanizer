"""Opt-in local editor preferences; never store document texts or API keys."""

import json
from pathlib import Path

from .files import write_text
from .paths import data_directory
from .providers import ProviderConfig

MAX_INSTRUCTION = 12000


def validate_instruction(value):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_INSTRUCTION:
        raise ValueError(f"Инструкция должна содержать от 1 до {MAX_INSTRUCTION} символов.")
    if "\x00" in value:
        raise ValueError("В инструкции есть недопустимый нулевой символ.")
    return value


class Preferences:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_directory() / "editor-preferences.json"

    def load(self):
        try:
            if self.path.stat().st_size > 100000:
                return {}
            data = json.loads(self.path.read_text(encoding="utf-8"))
            result = {}
            value = data.get("instruction")
            if value:
                result["instruction"] = validate_instruction(value)
            external = data.get("external_ollama")
            if isinstance(external, dict):
                try:
                    result["external_ollama"] = self.validate_connection(external)
                except (ValueError, TypeError):
                    pass
            return result
        except (OSError, ValueError, AttributeError):
            return {}

    @staticmethod
    def validate_connection(value):
        config = ProviderConfig(
            url=value.get("url", ""),
            model=value.get("model", ""),
            adaptive_context=value.get("adaptive_context", True),
        )
        if not isinstance(config.url, str) or not isinstance(config.model, str):
            raise ValueError("Некорректное подключение Ollama.")
        if type(config.adaptive_context) is not bool:
            raise ValueError("Некорректный параметр контекста.")
        config.validate()
        return {
            "url": config.base_url(),
            "model": config.model,
            "adaptive_context": config.adaptive_context,
        }

    def _write(self, data):
        if not data:
            self.path.unlink(missing_ok=True)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_text(self.path, json.dumps(data, ensure_ascii=False) + "\n")

    def save(self, instruction):
        data = self.load()
        if instruction is None:
            data.pop("instruction", None)
        else:
            data["instruction"] = validate_instruction(instruction)
        self._write(data)

    def save_connection(self, config):
        data = self.load()
        if config is None:
            data.pop("external_ollama", None)
        else:
            data["external_ollama"] = self.validate_connection(
                {
                    "url": config.url,
                    "model": config.model,
                    "adaptive_context": config.adaptive_context,
                }
            )
        self._write(data)
