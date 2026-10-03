#!/usr/bin/env python3
"""Install abysmalbiscuit marketplace plugins, and the release binaries they run,
into every agent CLI on PATH.

Usage: install.py [plugin...], installing DEFAULT_PLUGINS when none are named.
The README has the curl one-liner that runs it without a checkout.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

MARKETPLACE = "abysmalbiscuit"
SOURCE = "AbysmalBiscuit/AbysmalBiscuit-agent-plugins"
DEFAULT_PLUGINS = ("devkit", "mcpls", "agent-guard", "superpowers")
# Plugins whose MCP servers or hooks run a binary from the plugin repo's
# cargo-dist releases. The binary has the plugin's name.
NEEDS_BINARY = ("devkit", "mcpls")
# Each CLI's plugin install command.
CLIS = {"claude": "install", "codex": "add"}

_output = threading.Lock()


def report(label: str, output: str) -> None:
    with _output:
        print(f"\n$ {label}\n{output}", end="", flush=True)


def step(*argv: str, label: str = "") -> bool:
    # Resolving the full path lets Windows run .cmd shims, such as an npm-installed codex.
    command = [shutil.which(argv[0]) or argv[0], *argv[1:]]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as err:
        report(label or shlex.join(argv), f"{err}\n")
        return False
    report(label or shlex.join(argv), result.stdout + result.stderr)
    return result.returncode == 0


def install_binaries(plugins: Sequence[str]) -> bool:
    # A saved file, since Windows can refuse to start `powershell -c "irm ... | iex"`.
    if os.name == "nt":
        suffix, runner = ".ps1", ("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File")
    else:
        suffix, runner = ".sh", ("sh",)
    ok = True
    # One at a time: every cargo-dist installer edits the same PATH setup.
    for name in (plugin for plugin in plugins if plugin in NEEDS_BINARY):
        label = f"install {name} release binary"
        if shutil.which(name):
            report(label, "already on PATH\n")
            continue
        installer = f"{name}-installer{suffix}"
        url = f"https://github.com/AbysmalBiscuit/{name}/releases/latest/download/{installer}"
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp, installer)
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    script.write_bytes(response.read())
            except OSError as err:
                report(f"download {url}", f"{err}\n")
                ok = False
                continue
            ok &= step(*runner, str(script), label=label)
    return ok


def install_plugins(cli: str, plugins: Sequence[str]) -> bool:
    # One at a time: concurrent installs into one CLI overwrite each other's
    # config writes and silently drop plugins.
    if not step(cli, "plugin", "marketplace", "add", SOURCE):
        return False
    ok = True
    for plugin in plugins:
        ok &= step(cli, "plugin", CLIS[cli], f"{plugin}@{MARKETPLACE}")
    return ok


def main(argv: Sequence[str]) -> int:
    plugins = tuple(argv) or DEFAULT_PLUGINS
    jobs: list[Callable[[], bool]] = [partial(install_binaries, plugins)]
    for cli in CLIS:
        if shutil.which(cli):
            jobs.append(partial(install_plugins, cli, plugins))
        else:
            print(f"{cli}: not on PATH, skipping", file=sys.stderr)
    # The binaries and each CLI's config are separate files, so the jobs run
    # concurrently.
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        results = [future.result() for future in [pool.submit(job) for job in jobs]]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
