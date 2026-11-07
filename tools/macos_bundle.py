"""macOS build helpers: native icon, runtime notices and symlink-preserving archive."""

import ast
import json
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path


def make_icon(source, work):
    iconset = work / "Shelter.iconset"
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            output = iconset / f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
            subprocess.run(
                [
                    "sips",
                    "-z",
                    str(size * scale),
                    str(size * scale),
                    str(source),
                    "--out",
                    str(output),
                ],
                check=True,
                capture_output=True,
            )
    icon = work / "Shelter.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icon)], check=True)
    return icon


def runtime_notices(work):
    """Read only installed runtime licenses; fail rather than ship missing notices."""
    import tkinter as tk

    python_license = Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"
    root = tk.Tk()
    root.withdraw()
    try:
        tcl = Path(root.tk.call("info", "library"))
        tk_library = Path(root.tk.eval("set tk_library"))
    finally:
        root.destroy()
    result = {"PYTHON_LICENSE.txt": python_license}
    for label, directory in (("TCL", tcl), ("TK", tk_library)):
        candidates = [parent / "license.terms" for parent in (directory, *directory.parents)]
        # Homebrew installs Tcl/Tk's shared distribution notice at the keg root.
        notice = next((p for p in candidates if p.is_file()), None)
        if notice is None:
            # python.org's framework carries the Tcl/Tk notices in Resources.
            candidates = list(Path(sys.base_prefix).rglob("license.terms"))
            notice = next((p for p in candidates if label.lower() in str(p).lower()), None)
        if notice is None:
            raise RuntimeError(f"Missing {label} license")
        result[label + "_LICENSE.txt"] = notice

    # Include notices of Homebrew dylibs actually collected by PyInstaller.
    def paths(value):
        if isinstance(value, str) and value.startswith("/"):
            resolved = Path(value).resolve()
            if "Cellar" in resolved.parts:
                yield resolved
        elif isinstance(value, (tuple, list)):
            for item in value:
                yield from paths(item)

    analysis = next((work / "pyinstaller").rglob("Analysis-00.toc"))
    checked = set()
    for path in paths(ast.literal_eval(analysis.read_text())):
        parts = path.parts
        index = parts.index("Cellar")
        keg = Path(*parts[: index + 3])
        if keg in checked:
            continue
        checked.add(keg)
        before = len(result)
        for pattern in ("LICENSE*", "COPYING*", "license.terms", "COPYRIGHT*"):
            for license_file in keg.glob(pattern):
                if license_file.is_file():
                    result[f"{parts[index + 1]}-{license_file.name}"] = license_file
        if len(result) == before:
            raise RuntimeError(f"Missing runtime notices for {keg.name}")
    return result


def archive_app(app, archive, extra_files, runtime, metadata, receipt, root):
    """ditto keeps framework symlinks, executable bits and the .app directory."""
    staging = archive.parent / "archive-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    shutil.copytree(app, staging / app.name, symlinks=True)
    plist = staging / app.name / "Contents/Info.plist"
    data = plistlib.loads(plist.read_bytes())
    version = json.loads(metadata.read_text())["version"]
    data.update(
        CFBundleDisplayName="Shelter Humanizer",
        CFBundleName="Shelter Humanizer",
        CFBundleShortVersionString=re.match(r"\d+\.\d+\.\d+", version)[0],
        CFBundleVersion=version,
        NSHighResolutionCapable=True,
        LSMinimumSystemVersion=platform.mac_ver()[0],
    )
    plist.write_bytes(plistlib.dumps(data))
    for name in extra_files:
        shutil.copy2(root / name, staging / Path(name).name)
        shutil.copy2(root / name, staging / app.name / "Contents/Resources" / Path(name).name)
    licenses = staging / "licenses"
    licenses.mkdir()
    for name, path in runtime.items():
        shutil.copy2(path, licenses / name)
    shutil.copytree(licenses, staging / app.name / "Contents" / "Resources" / "licenses")
    # Adding data after ad-hoc signing invalidates the resource seal. Re-sign the
    # assembled bundle; this is integrity signing, never a Developer ID identity.
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(staging / app.name)], check=True
    )
    # Deliver the exact bundle that is archived and verified.
    shutil.rmtree(app)
    shutil.copytree(staging / app.name, app, symlinks=True)
    shutil.copy2(metadata, staging / "BUILD_INFO.json")
    shutil.copy2(receipt, staging / "SELFTEST.json")
    if archive.exists():
        archive.unlink()
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", str(staging), str(archive)], check=True)
    shutil.rmtree(staging)


def verify_dependencies(app):
    """A standalone bundle must not load dylibs from the builder's Homebrew/Python."""
    magic = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"}
    for path in (app / "Contents").rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) not in magic:
                continue
        output = subprocess.check_output(["otool", "-L", str(path)], text=True)
        for line in output.splitlines()[1:]:
            dependency = line.strip().split(" (")[0]
            if dependency.startswith("/") and not dependency.startswith(("/System/", "/usr/lib/")):
                raise RuntimeError(f"Non-bundled dependency: {dependency}")
