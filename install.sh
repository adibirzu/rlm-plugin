#!/usr/bin/env bash
# Install or uninstall RLM through Claude Code's supported plugin interface.

set -euo pipefail

readonly MARKETPLACE_REPO="adibirzu/adibirzu-plugins"
readonly MARKETPLACE_NAME="adibirzu-plugins"
readonly PLUGIN_ID="rlm@${MARKETPLACE_NAME}"

usage() {
    printf 'Usage: %s [--uninstall]\n' "${0##*/}"
}

fail() {
    printf 'Error: %s\n' "$1" >&2
    exit 1
}

require_claude() {
    command -v claude >/dev/null 2>&1 || fail "Claude Code is required. Install it before running this script."
}

case "${1:-}" in
    "")
        require_claude
        if claude plugin marketplace list --json \
            | grep -Eq '"name"[[:space:]]*:[[:space:]]*"adibirzu-plugins"'; then
            printf 'Marketplace %s is already configured.\n' "$MARKETPLACE_NAME"
        else
            printf 'Adding the %s marketplace...\n' "$MARKETPLACE_NAME"
            claude plugin marketplace add "$MARKETPLACE_REPO"
        fi
        printf 'Installing %s...\n' "$PLUGIN_ID"
        claude plugin install "$PLUGIN_ID" --scope user
        printf 'Installed. Run /reload-plugins in Claude Code, then invoke /rlm:rlm.\n'
        ;;
    --uninstall)
        require_claude
        claude plugin uninstall "$PLUGIN_ID" --scope user
        printf 'Uninstalled %s.\n' "$PLUGIN_ID"
        ;;
    -h|--help)
        usage
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
