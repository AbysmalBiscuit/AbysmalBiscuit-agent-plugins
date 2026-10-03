# AbysmalBiscuit-agent-plugins

The `abysmalbiscuit` marketplace: one place to install Lev's agent plugins, and the third-party plugins he uses, into Claude Code and Codex.

Each plugin lives in its own repo; this repo only lists them in [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json). Claude Code reads that file natively and Codex falls back to it, so both CLIs share one manifest. Entries track each plugin's default branch. A fresh install always gets the latest commit, and Codex reinstalls from a fresh clone, but Claude Code's `plugin update` only moves to new code when the `version` in the plugin's `plugin.json` changes. Bump that version with every release that should reach existing Claude installs.

| Plugin | Default | What it is |
|---|---|---|
| [devkit](https://github.com/AbysmalBiscuit/devkit) | yes | Local-dev coordination for parallel agents: file locks, ports, dev servers, issue lifecycle |
| [mcpls](https://github.com/AbysmalBiscuit/mcpls) | yes | Language server intelligence and push diagnostics |
| [agent-guard](https://github.com/AbysmalBiscuit/agent-guard) | yes | Checks agent tool calls, edits, and changesets against local rules |
| [superpowers](https://github.com/obra/superpowers) | yes | Skills library: TDD, debugging, planning, collaboration workflows |
| [pr-crucible](https://github.com/AbysmalBiscuit/pr-crucible) | no | Staged, evidence-backed, adversarial PR review |

## Install anywhere: `install.py`

```bash
curl -fsSL https://raw.githubusercontent.com/AbysmalBiscuit/AbysmalBiscuit-agent-plugins/main/install.py | python3 -
```

For each of `claude` and `codex` on PATH it registers the marketplace and installs the default plugins. It also installs the devkit and mcpls release binaries, which those plugins run, when they are not already on PATH. Name plugins to install only those:

```bash
curl -fsSL https://raw.githubusercontent.com/AbysmalBiscuit/AbysmalBiscuit-agent-plugins/main/install.py | python3 - pr-crucible
```

It needs Python 3.9 or newer and nothing outside the standard library. The binary downloads, the Claude installs, and the Codex installs run concurrently. Within one CLI, plugins install one at a time: concurrent installs into the same CLI overwrite each other's config writes and silently drop plugins.

The script installs; it does not update. Use the CLI commands below to update.

## Claude Code

```bash
claude plugin marketplace add AbysmalBiscuit/AbysmalBiscuit-agent-plugins
claude plugin install devkit@abysmalbiscuit
```

Update with `claude plugin marketplace update abysmalbiscuit` followed by `claude plugin update <plugin>@abysmalbiscuit`.

### Claude Code on the web

Commit this to `.claude/settings.json` in a repo opened on the web:

```json
{
  "extraKnownMarketplaces": {
    "abysmalbiscuit": {
      "source": { "source": "github", "repo": "AbysmalBiscuit/AbysmalBiscuit-agent-plugins" }
    }
  },
  "enabledPlugins": {
    "devkit@abysmalbiscuit": true,
    "mcpls@abysmalbiscuit": true,
    "agent-guard@abysmalbiscuit": true,
    "superpowers@abysmalbiscuit": true
  }
}
```

If plugins do not load there, run `install.py` from a `SessionStart` hook instead.

## Codex

```bash
codex plugin marketplace add AbysmalBiscuit/AbysmalBiscuit-agent-plugins
codex plugin add devkit@abysmalbiscuit
```

Update with `codex plugin marketplace upgrade abysmalbiscuit`, then remove and re-add the plugin: Codex installs a git-sourced plugin from a fresh clone.

### Codex cloud

Add the `install.py` line to the environment's setup script.

## Adding a plugin

Add an entry to `.claude-plugin/marketplace.json`. Use only `git-subdir` (plugin in a subdirectory) or `url` (plugin at the repo root) sources: both CLIs understand them, while Codex skips Claude's `github` source type. Add the plugin to `DEFAULT_PLUGINS` in `install.py` if every environment should get it, and to `NEEDS_BINARY` if it runs a binary published as a cargo-dist release. CI validates the manifest, lints `install.py`, and runs `test_install.py`, which also checks that `install.py` names only listed plugins.
