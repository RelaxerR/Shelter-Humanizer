"""Packaged-app smoke test: offline, no user interaction, explicit receipt file only."""

import hashlib
import json
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from . import __version__
from .build_info import build_info
from .diagnostics import snapshot
from .files import read_text, write_text
from .gui import SAMPLE, App
from .local_setup import LocalSetup
from .managed_runtime import ManagedRuntime
from .preferences import Preferences
from .prompts import system_instruction
from .providers import (
    LOCAL_GENERATION_TIMEOUT,
    Client,
    ProviderCancelled,
    ProviderConfig,
    ProviderError,
)
from .service import offline, rewrite

SMOKE_TEXT = (
    "Важно отметить, что сервис осуществляет проверку.\n"
    "Цена — 2 000 ₽. «Точная цитата» https://example.org/docs\n"
    "про\u200bверка. пpоверка. 👩‍💻."
)


def run(path: str) -> int:
    receipt = {"version": __version__, "ok": False, "network_used": False}
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        app = App(root, auto_connect=False)
        assert app.depth_key() == "edit"
        with tempfile.TemporaryDirectory() as directory:
            preferences = Preferences(Path(directory) / "preferences.json")
            preferences.save("Редактируй бережно.")
            assert preferences.load()["instruction"] == "Редактируй бережно."
            assert "Редактируй бережно." in system_instruction(preferences.load()["instruction"])
            preferences.save(None)
            assert not preferences.path.exists()
            runtime = ManagedRuntime(directory)
            wizard = LocalSetup(root, lambda: app.colors, lambda model, url: None, runtime)
            default_model = wizard.choice.get()
            assert default_model == "qwen3.5:4b"
            assert runtime.selected_model() == "" and runtime.process is None
            assert not (Path(directory) / "selection.json").exists()
            wizard.close()
            runtime.save_model("deepseek-r1:8b-0528-qwen3-q4_K_M")
            wizard = LocalSetup(root, lambda: app.colors, lambda model, url: None, runtime)
            assert wizard.choice.get() == "deepseek-r1:8b-0528-qwen3-q4_K_M"
            wizard.close()
            runtime.save_model("my-editor:q4", allow_custom=True)
            assert ManagedRuntime(directory).selected_model() == "my-editor:q4"
            runtime.close()
        with tempfile.TemporaryDirectory(prefix="Shelter files ") as directory:
            source = Path(directory) / "Русский исходник.txt"
            target = Path(directory) / "Результат.txt"
            report = Path(directory) / "Отчёт.json"
            write_text(source, SMOKE_TEXT)
            with patch(
                "shelter_humanizer.gui.filedialog.askopenfilename", return_value=str(source)
            ):
                app.load()
            assert app.get_text(app.source) == SMOKE_TEXT
            app.show_result(offline(SMOKE_TEXT, "clean"))
            with patch(
                "shelter_humanizer.gui.filedialog.asksaveasfilename", return_value=str(target)
            ):
                assert app.save()
            with patch(
                "shelter_humanizer.gui.filedialog.asksaveasfilename", return_value=str(report)
            ):
                app.report()
            assert read_text(target) == app.get_text(app.output)
            assert json.loads(read_text(report))["original"] == SMOKE_TEXT
        app.set_source(SAMPLE)
        result = offline(SAMPLE)
        app.show_result(result)
        root.update()
        assert app.get_text(app.source) == SAMPLE
        assert app.get_text(app.output) == SAMPLE
        app.set_source(SMOKE_TEXT)
        result = offline(SMOKE_TEXT)
        app.show_result(result)
        root.update()
        assert "про\u200bверка" not in app.get_text(app.output)
        assert "2 000 ₽" in app.get_text(app.output)
        assert "👩‍💻" in app.get_text(app.output)
        assert app.logo.width() > 0
        menu = app.source.shelter_menu
        root.tk.call(menu.cget("postcommand"))
        select_all = next(
            i
            for i in range(menu.index("end") + 1)
            if menu.type(i) == "command" and menu.entrycget(i, "label") == "Выделить всё"
        )
        menu.invoke(select_all)
        assert app.source.get("sel.first", "sel.last") == SMOKE_TEXT

        class SyntheticAI:
            def complete(self, messages):
                self.system_sha256 = hashlib.sha256(messages[0]["content"].encode()).hexdigest()
                return "Про\u200bверка\u00a0текста. «Точная цитата» 👩‍💻"

        synthetic_ai = SyntheticAI()
        generated = rewrite(
            "Проверка текста. «Точная цитата» 👩‍💻", synthetic_ai, second_pass=False
        )
        assert generated.text == "Проверка\u00a0текста. «Точная цитата» 👩‍💻"
        assert generated.original == "Проверка текста. «Точная цитата» 👩‍💻"

        class FailedReview:
            calls = 0

            def complete(self, messages):
                self.calls += 1
                if self.calls == 1:
                    return "Сервис про\u200bверяет 10 файлов."
                raise ProviderError("Synthetic optional review timeout")

        first_draft = rewrite("Сервис осуществляет проверку 10 файлов.", FailedReview())
        assert first_draft.text == "Сервис проверяет 10 файлов."
        assert any("вычитка не завершилась" in warning for warning in first_draft.warnings)
        assert app.configs["ollama"].timeout == 180 and LOCAL_GENERATION_TIMEOUT == 900
        for theme in ("dark", "light"):
            app.apply_theme(theme)
            root.update()
            assert app.get_text(app.source) == SMOKE_TEXT
            assert app.get_text(app.output) == result.text
        receipt.update(
            ok=True,
            tk=str(root.tk.call("info", "patchlevel")),
            source_preserved=True,
            unicode_removed=True,
            numbers_preserved=True,
            emoji_preserved=True,
            themes_preserve_text=True,
            logo_loaded=True,
            neutral_example_loaded=True,
            post_ai_cleanup=True,
            ai_generation_used=False,
            default_depth=app.depth_key(),
            default_model=default_model,
            saved_model_preserved=True,
            ai_system_sha256=synthetic_ai.system_sha256,
            review_timeout_preserves_draft=True,
            local_generation_timeout=LOCAL_GENERATION_TIMEOUT,
            custom_model_selection=True,
            instruction_preferences_reset=True,
            build=build_info(),
            diagnostics_version=snapshot()["app_version"],
            context_menu_loaded=True,
            txt_open_save_json_export=True,
            cpu_only_opt_in=not app.configs["ollama"].cpu_only,
        )
        app.close()
        root = None
    except Exception:
        receipt["error"] = "Packaged GUI self-test failed"
    finally:
        if root is not None:
            root.destroy()
    write_text(Path(path), json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return 0 if receipt["ok"] else 1


def run_ollama(model: str, path: str) -> int:
    """Explicit online acceptance using an already installed external model only."""
    receipt = {"ok": False, "model": model, "network_used": True}
    app = None
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = tk.Tk()
            root.withdraw()
            preferences = Preferences(Path(directory) / "settings.json")
            app = App(root, auto_connect=False, preferences=preferences)
            config = ProviderConfig(model=model, timeout=180, inspect_model=True)
            assert model in Client(config).models()
            preferences.save_connection(config)
            app.configs["ollama"] = config
            app.mode.set("ollama")
            app.second_pass.set(False)
            app.set_source("Сегодня хорошая погода. Мы гуляем в парке.")
            errors = []
            app.error = errors.append
            app.run("edit")
            deadline = time.monotonic() + 180
            while app.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(0.02)
            assert not app.busy and not errors, errors
            assert app.result is not None and app.get_text(app.output).strip()
            receipt["generated_text"] = app.get_text(app.output)
            receipt["stats"] = app.last_diagnostics
            previous = app.get_text(app.output)
            app.run("edit")
            app.cancel.set()
            deadline = time.monotonic() + 5
            while app.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(0.02)
            assert not app.busy and app.get_text(app.output) == previous
            assert app.runtime.process is None
            app.close()
            app = None
            root = tk.Tk()
            root.withdraw()
            app = App(root, preferences=preferences)
            assert app.configs["ollama"].model == model and not app.managed_connection
            app.close()
            app = None
            assert model in Client(config).models()
            cancel = threading.Event()
            client = Client(config, cancel=cancel)
            timer = threading.Timer(0.25, cancel.set)
            timer.start()
            try:
                # A long request makes mid-stream cancellation observable even on a warm model.
                client.complete([{"role": "user", "content": "Перечисли тысячу названий цветов."}])
                raise AssertionError("Request completed before cancellation")
            except ProviderCancelled:
                receipt["transport_cancelled"] = True
            finally:
                timer.cancel()
            receipt.update(
                ok=True,
                gui_generation=True,
                previous_result_preserved=True,
                selection_restored=True,
                external_service_survived_close=True,
            )
    except Exception as exc:
        receipt["error"] = str(exc)
    finally:
        if app is not None and not app.closed:
            app.close()
    write_text(Path(path), json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return 0 if receipt["ok"] else 1
