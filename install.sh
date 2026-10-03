#!/usr/bin/env bash
# Install abysmalbiscuit marketplace plugins, and the release binaries they run,
# into every agent CLI on PATH. Usage: install.sh [plugin...]
set -uo pipefail

readonly MARKETPLACE=abysmalbiscuit
readonly SOURCE=AbysmalBiscuit/AbysmalBiscuit-agent-plugins
readonly DEFAULT_PLUGINS=(devkit mcpls agent-guard superpowers)
# Plugins whose MCP servers or hooks need a binary from the plugin repo's releases.
readonly NEEDS_BINARY=(devkit mcpls)

status=0

step() {
	printf '\n$ %s\n' "$*"
	"$@" || status=1
}

needs_binary() {
	local plugin
	for plugin in "${NEEDS_BINARY[@]}"; do
		[[ $plugin == "$1" ]] && return 0
	done
	return 1
}

install_binary() {
	local name=$1
	if command -v "$name" >/dev/null; then
		echo "$name: already on PATH"
		return
	fi
	printf '\n$ install %s release binary\n' "$name"
	curl --proto '=https' --tlsv1.2 -fsSL \
		"https://github.com/AbysmalBiscuit/$name/releases/latest/download/$name-installer.sh" | sh ||
		status=1
}

install_claude() {
	step claude plugin marketplace add "$SOURCE"
	local plugin
	for plugin in "$@"; do
		step claude plugin install "$plugin@$MARKETPLACE"
	done
}

install_codex() {
	step codex plugin marketplace add "$SOURCE"
	local plugin
	for plugin in "$@"; do
		step codex plugin add "$plugin@$MARKETPLACE"
	done
}

main() {
	local plugins=("$@")
	((${#plugins[@]})) || plugins=("${DEFAULT_PLUGINS[@]}")

	local plugin
	for plugin in "${plugins[@]}"; do
		needs_binary "$plugin" && install_binary "$plugin"
	done

	local cli
	for cli in claude codex; do
		if command -v "$cli" >/dev/null; then
			"install_$cli" "${plugins[@]}"
		else
			echo "$cli: not on PATH, skipping" >&2
		fi
	done
	return "$status"
}

main "$@"
