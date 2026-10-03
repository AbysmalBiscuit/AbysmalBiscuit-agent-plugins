import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent


@pytest.fixture
def install() -> ModuleType:
    spec = importlib.util.spec_from_file_location("install", ROOT / "install.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_clis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: str = "", barrier: str = ""
) -> Path:
    """Put fake claude and codex on PATH; every call is appended to the returned log.

    The call that installs `barrier` waits for the other CLI to reach its own
    `barrier` call and logs a timeout if it never does, which only happens when
    the CLIs run one after the other.
    """
    log = tmp_path / "calls.log"
    log.touch()
    binary = tmp_path / "bin"
    binary.mkdir()
    for name, other in (("claude", "codex"), ("codex", "claude")):
        script = binary / name
        script.write_text(
            f"""#!/bin/sh
echo "{name} $*" >> "{log}"
case "$*" in
  "plugin install {barrier}@abysmalbiscuit"|"plugin add {barrier}@abysmalbiscuit")
    touch "{tmp_path}/{name}.reached"
    i=0
    while [ ! -e "{tmp_path}/{other}.reached" ] && [ $i -lt 50 ]; do sleep 0.1; i=$((i+1)); done
    [ -e "{tmp_path}/{other}.reached" ] || echo "{name} timeout" >> "{log}"
    ;;
esac
[ "{name} $*" = "{failing}" ] && exit 3
exit 0
"""
        )
        script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary}:/usr/bin:/bin")
    return log


def calls(log: Path, cli: str) -> list[str]:
    return [line for line in log.read_text().splitlines() if line.startswith(cli)]


def test_clis_install_concurrently_each_in_order(install, tmp_path, monkeypatch):
    log = fake_clis(tmp_path, monkeypatch, barrier="agent-guard")

    status = install.main(["agent-guard", "superpowers"])

    assert status == 0
    assert calls(log, "claude") == [
        "claude plugin marketplace add AbysmalBiscuit/AbysmalBiscuit-agent-plugins",
        "claude plugin install agent-guard@abysmalbiscuit",
        "claude plugin install superpowers@abysmalbiscuit",
    ]
    assert calls(log, "codex") == [
        "codex plugin marketplace add AbysmalBiscuit/AbysmalBiscuit-agent-plugins",
        "codex plugin add agent-guard@abysmalbiscuit",
        "codex plugin add superpowers@abysmalbiscuit",
    ]


def test_failed_marketplace_skips_that_clis_plugins_only(install, tmp_path, monkeypatch):
    log = fake_clis(
        tmp_path,
        monkeypatch,
        failing="claude plugin marketplace add AbysmalBiscuit/AbysmalBiscuit-agent-plugins",
    )

    status = install.main(["superpowers"])

    assert status == 1
    assert calls(log, "claude") == [
        "claude plugin marketplace add AbysmalBiscuit/AbysmalBiscuit-agent-plugins"
    ]
    assert calls(log, "codex")[-1] == "codex plugin add superpowers@abysmalbiscuit"


def test_installs_only_release_binaries_missing_from_path(install, tmp_path, monkeypatch):
    log = fake_clis(tmp_path, monkeypatch)
    mcpls = tmp_path / "bin" / "mcpls"
    mcpls.write_text("#!/bin/sh\n")
    mcpls.chmod(0o755)
    fetched: list[str] = []

    def urlopen(url: str, **_: object) -> io.BytesIO:
        fetched.append(url)
        return io.BytesIO(f'echo "installer {url}" >> "{log}"\n'.encode())

    monkeypatch.setattr(install.urllib.request, "urlopen", urlopen)

    status = install.main(["devkit", "mcpls"])

    devkit_installer = (
        "https://github.com/AbysmalBiscuit/devkit/releases/latest/download/devkit-installer.sh"
    )
    assert status == 0
    assert fetched == [devkit_installer]
    assert calls(log, "installer") == [f"installer {devkit_installer}"]


def test_install_names_only_listed_plugins(install):
    manifest = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    listed = {plugin["name"] for plugin in manifest["plugins"]}

    assert set(install.DEFAULT_PLUGINS) <= listed
    assert set(install.NEEDS_BINARY) <= listed
