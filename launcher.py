"""Source and frozen desktop entry point."""

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--ollama-self-test":
        from shelter_humanizer.selftest import run_ollama

        return run_ollama(sys.argv[2], sys.argv[3])
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from shelter_humanizer.selftest import run

        return run(sys.argv[2])
    if len(sys.argv) > 1:
        from shelter_humanizer.cli import main as cli_main

        return cli_main()
    try:
        from shelter_humanizer.gui import launch
    except ModuleNotFoundError as exc:
        if exc.name not in ("tkinter", "_tkinter"):
            raise
        print(
            "Tkinter is missing. On macOS install matching Python/Tk: "
            "brew install python@3.14 python-tk@3.14; recreate .venv. "
            "See docs/MACOS.md. CLI analyze/clean remain available.",
            file=sys.stderr,
        )
        return 2
    launch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
