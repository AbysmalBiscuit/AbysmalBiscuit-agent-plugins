#!/usr/bin/env python3
"""Install abysmalbiscuit marketplace plugins, and the release binaries they run,
into every agent CLI on PATH.

Usage: install.py [plugin...], installing DEFAULT_PLUGINS when none are named.
The README has the curl one-liner that runs it without a checkout.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import partial
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


def step(*argv: str, stdin: str | None = None, label: str = "") -> bool:
    try:
        result = subprocess.run(argv, input=stdin, capture_output=True, text=True, check=False)
    except OSError as err:
        report(label or shlex.join(argv), f"{err}\n")
        return False
    report(label or shlex.join(argv), result.stdout + result.stderr)
    return result.returncode == 0


def install_binaries(plugins: Sequence[str]) -> bool:
    # One at a time: every cargo-dist installer edits the same ~/.cargo/env and
    # shell rc files.
    ok = True
    for name in (plugin for plugin in plugins if plugin in NEEDS_BINARY):
        if shutil.which(name):
            report(f"install {name} release binary", "already on PATH\n")
            continue
        url = (
            f"https://github.com/AbysmalBiscuit/{name}/releases/latest/download/{name}-installer.sh"
        )
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                installer = response.read().decode()
        except OSError as err:
            report(f"download {url}", f"{err}\n")
            ok = False
            continue
        ok &= step("sh", stdin=installer, label=f"install {name} release binary")
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
