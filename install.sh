#!/usr/bin/env bash
# Install or uninstall RLM through Claude Code's supported plugin interface,
# or link the shared skill into every agent harness skill directory.

set -euo pipefail

readonly MARKETPLACE_REPO="adibirzu/adibirzu-plugins"
readonly MARKETPLACE_NAME="adibirzu-plugins"
readonly PLUGIN_ID="rlm@${MARKETPLACE_NAME}"
readonly SKILL_NAME="rlm"
readonly BACKUP_DIR_NAME=".rlm-skill-backups"
readonly EXIT_DRIFT=3

# Skill directories, relative to the home directory. Order matters: when two
# entries resolve to the same directory, the later one is reported as an alias.
readonly HARNESS_DIRS=(
    ".claude/skills"
    ".codex/skills"
    ".gemini/skills"
    ".gemini/config/skills"
    ".agents/skills"
    ".cursor/skills"
    ".config/opencode/skills"
    ".opencode/skills"
    ".pi/skills"
    ".grok/skills"
    ".cline/skills"
)
readonly STATES=(
    linked alias source harness-absent missing stale-link
    copy-identical copy-diverged conflict
)

usage() {
    cat <<EOF
Usage: ${0##*/} [--uninstall]
       ${0##*/} --check [--json] [--source <skill-dir>] [--home <home-dir>]
       ${0##*/} --sync-harnesses [--source <skill-dir>] [--home <home-dir>] [--backup]

  (no arguments)     Install the Claude Code plugin from the marketplace.
  --uninstall        Uninstall the Claude Code plugin.
  --check            Report how each harness skill directory relates to the
                     skill source. Read-only. Exits ${EXIT_DRIFT} when any directory
                     has drifted, 0 when all present harnesses are linked.
  --sync-harnesses   Symlink the skill into every harness that is present.
                     An identical copy is replaced by a symlink. A copy that
                     differs is left alone unless --backup is given. Replaced
                     directories are moved to <home>/${BACKUP_DIR_NAME}/, never
                     deleted. Exits 1 when a directory was refused.

  --source <dir>     Skill directory holding SKILL.md (default: skills/rlm
                     next to this script).
  --home <dir>       Home directory to inspect (default: \$HOME).
  --backup           Allow --sync-harnesses to move a differing copy aside.
  --json             Print the --check report as JSON.
EOF
}

fail() {
    printf 'Error: %s\n' "$1" >&2
    exit 1
}

usage_error() {
    printf 'Error: %s\n' "$1" >&2
    usage >&2
    exit 2
}

require_claude() {
    command -v claude >/dev/null 2>&1 || fail "Claude Code is required. Install it before running this script."
}

physical_dir() {
    (cd "$1" 2>/dev/null && pwd -P)
}

json_escape() {
    local text=$1
    text=${text//\\/\\\\}
    text=${text//\"/\\\"}
    text=${text//$'\n'/\\n}
    text=${text//$'\r'/\\r}
    text=${text//$'\t'/\\t}
    printf '%s' "$text"
}

SOURCE_DIR=""
HOME_DIR=""
SEEN_DIRS=""
STATE=""
DETAIL=""

# Sets STATE and DETAIL for one harness skill directory. Never writes.
classify() {
    local rel=$1
    local skills_dir="$HOME_DIR/$rel"
    local target="$skills_dir/$SKILL_NAME"
    local physical seen resolved
    DETAIL=""

    if [ ! -d "$(dirname "$skills_dir")" ]; then
        STATE="harness-absent"
        return
    fi
    if [ ! -e "$skills_dir" ] && [ ! -L "$skills_dir" ]; then
        STATE="missing"
        DETAIL="skills directory does not exist yet"
        return
    fi
    if ! physical=$(physical_dir "$skills_dir"); then
        STATE="conflict"
        DETAIL="skills path is not a usable directory"
        return
    fi
    while IFS= read -r seen; do
        if [ "${seen%%|*}" = "$physical" ]; then
            STATE="alias"
            DETAIL="same directory as ${seen#*|}"
            return
        fi
    done <<EOF
$SEEN_DIRS
EOF
    SEEN_DIRS="${SEEN_DIRS}${physical}|${rel}
"

    if [ -L "$target" ]; then
        resolved=$(physical_dir "$target") || resolved=""
        if [ "$resolved" = "$SOURCE_DIR" ]; then
            STATE="linked"
        else
            STATE="stale-link"
            DETAIL="points to $(readlink "$target")"
        fi
    elif [ -d "$target" ]; then
        if [ "$(physical_dir "$target")" = "$SOURCE_DIR" ]; then
            STATE="source"
        elif diff -rq -x __pycache__ -x .DS_Store "$SOURCE_DIR" "$target" >/dev/null 2>&1; then
            STATE="copy-identical"
        else
            STATE="copy-diverged"
            DETAIL="local copy differs from the source"
        fi
    elif [ -e "$target" ]; then
        STATE="conflict"
        DETAIL="exists and is not a directory"
    else
        STATE="missing"
    fi
}

is_drift() {
    case "$1" in
        linked|alias|source|harness-absent) return 1 ;;
        *) return 0 ;;
    esac
}

run_check() {
    local as_json=$1
    local rel state count entries="" summary="" drift=0 separator=""

    for rel in "${HARNESS_DIRS[@]}"; do
        classify "$rel"
        if is_drift "$STATE"; then
            drift=1
        fi
        if [ "$as_json" -eq 1 ]; then
            entries="${entries}${separator}
    {\"dir\": \"$(json_escape "$rel")\", \"path\": \"$(json_escape "$HOME_DIR/$rel/$SKILL_NAME")\", \"state\": \"$STATE\", \"detail\": \"$(json_escape "$DETAIL")\"}"
            separator=","
        else
            printf '%-15s %-26s %s\n' "$STATE" "$rel" "$DETAIL"
        fi
        summary="${summary}${STATE}
"
    done

    if [ "$as_json" -eq 1 ]; then
        printf '{\n  "source": "%s",\n  "home": "%s",\n' "$(json_escape "$SOURCE_DIR")" "$(json_escape "$HOME_DIR")"
        if [ "$drift" -eq 1 ]; then
            printf '  "in_sync": false,\n'
        else
            printf '  "in_sync": true,\n'
        fi
        printf '  "harnesses": [%s\n  ],\n  "summary": {' "$entries"
        separator=""
        for state in "${STATES[@]}"; do
            count=$(printf '%s' "$summary" | grep -cx -- "$state" || true)
            printf '%s"%s": %s' "$separator" "$state" "$count"
            separator=", "
        done
        printf '}\n}\n'
    elif [ "$drift" -eq 1 ]; then
        printf 'Drift found. Run %s --sync-harnesses to link the skill.\n' "${0##*/}"
    else
        printf 'All present harnesses are linked to %s.\n' "$SOURCE_DIR"
    fi

    if [ "$drift" -eq 1 ]; then
        return "$EXIT_DRIFT"
    fi
}

move_to_backup() {
    local rel=$1 target=$2 stamp=$3
    local destination="$HOME_DIR/$BACKUP_DIR_NAME/$stamp/${rel//\//_}/$SKILL_NAME"

    [ ! -e "$destination" ] || fail "Backup destination already exists: $destination"
    mkdir -p "$(dirname "$destination")"
    mv -- "$target" "$destination"
    printf '%s' "$destination"
}

run_sync() {
    local allow_backup=$1
    local rel skills_dir target stamp saved refused=0

    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    for rel in "${HARNESS_DIRS[@]}"; do
        classify "$rel"
        skills_dir="$HOME_DIR/$rel"
        target="$skills_dir/$SKILL_NAME"
        case "$STATE" in
            linked|alias|source|harness-absent)
                printf '%-15s %s\n' "$STATE" "$rel"
                ;;
            missing)
                mkdir -p "$skills_dir"
                ln -s "$SOURCE_DIR" "$target"
                printf '%-15s %s\n' "linked" "$rel"
                ;;
            stale-link)
                ln -sfn "$SOURCE_DIR" "$target"
                printf '%-15s %s (was: %s)\n' "relinked" "$rel" "${DETAIL#points to }"
                ;;
            copy-identical)
                saved=$(move_to_backup "$rel" "$target" "$stamp")
                ln -s "$SOURCE_DIR" "$target"
                printf '%-15s %s (identical copy moved to %s)\n' "linked" "$rel" "$saved"
                ;;
            copy-diverged)
                if [ "$allow_backup" -eq 1 ]; then
                    saved=$(move_to_backup "$rel" "$target" "$stamp")
                    ln -s "$SOURCE_DIR" "$target"
                    printf '%-15s %s (local copy moved to %s)\n' "linked" "$rel" "$saved"
                else
                    printf 'Refused: %s differs from the source. Rerun with --backup to move it aside.\n' "$target" >&2
                    refused=1
                fi
                ;;
            conflict)
                printf 'Refused: %s (%s). Resolve it by hand.\n' "$target" "$DETAIL" >&2
                refused=1
                ;;
        esac
    done
    return "$refused"
}

harness_mode() {
    local mode=$1
    shift
    local source_arg="" home_arg="${HOME:-}" as_json=0 allow_backup=0

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --source|--home)
                [ "$#" -ge 2 ] || usage_error "$1 needs a directory."
                if [ "$1" = "--source" ]; then
                    source_arg=$2
                else
                    home_arg=$2
                fi
                shift 2
                ;;
            --json)
                [ "$mode" = "--check" ] || usage_error "--json only applies to --check."
                as_json=1
                shift
                ;;
            --backup)
                [ "$mode" = "--sync-harnesses" ] || usage_error "--backup only applies to --sync-harnesses."
                allow_backup=1
                shift
                ;;
            *)
                usage_error "Unknown option for $mode: $1"
                ;;
        esac
    done

    if [ -z "$source_arg" ]; then
        source_arg="$(dirname "${BASH_SOURCE[0]}")/skills/$SKILL_NAME"
    fi
    [ -f "$source_arg/SKILL.md" ] || usage_error "No SKILL.md in skill source: $source_arg"
    SOURCE_DIR=$(physical_dir "$source_arg")
    [ -n "$home_arg" ] || usage_error "No home directory. Pass --home <dir>."
    HOME_DIR=$(physical_dir "$home_arg") || usage_error "Home directory does not exist: $home_arg"

    if [ "$mode" = "--check" ]; then
        run_check "$as_json"
    else
        run_sync "$allow_backup"
    fi
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
    --check|--sync-harnesses)
        harness_mode "$@"
        ;;
    -h|--help)
        usage
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
