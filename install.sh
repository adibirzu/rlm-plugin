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
    local name=${0##*/}
    printf '%s\n' \
        "Usage: $name [--uninstall]" \
        "       $name --check [--json] [--source <skill-dir>] [--home <home-dir>]" \
        "       $name --sync-harnesses [--source <skill-dir>] [--home <home-dir>] [--backup]" \
        "" \
        "  (no arguments)     Install the Claude Code plugin from the marketplace." \
        "  --uninstall        Uninstall the Claude Code plugin." \
        "  --check            Report how each harness skill directory relates to the" \
        "                     skill source. Read-only. Exits $EXIT_DRIFT when any directory" \
        "                     has drifted, 0 when all present harnesses are linked." \
        "  --sync-harnesses   Symlink the skill into every harness that is present." \
        "                     An identical copy is replaced by a symlink. A copy that" \
        "                     differs is left alone unless --backup is given. Replaced" \
        "                     entries are moved to <home>/$BACKUP_DIR_NAME/, never" \
        "                     deleted. Exits 1 when an entry was refused." \
        "" \
        "  --source <dir>     Skill directory holding SKILL.md (default: skills/rlm" \
        "                     next to this script)." \
        "  --home <dir>       Home directory to inspect (default: \$HOME)." \
        "  --backup           Allow --sync-harnesses to move a differing copy aside." \
        "  --json             Print the --check report as JSON."
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
    (CDPATH='' cd -P -- "$1" 2>/dev/null && pwd -P)
}

# Lists every symlink under a directory with its target text, so two trees
# whose links point at different files never compare as equal.
link_map() {
    (CDPATH='' cd -P -- "$1" 2>/dev/null \
        && find . -type l -exec sh -c 'for entry; do printf "%s -> %s\n" "$entry" "$(readlink "$entry")"; done' sh {} + \
        | sort)
}

# True when the first directory is the second one or lies beneath it. The
# comparison is by inode, so a path spelled in another case still matches.
is_within() {
    local current=$1

    while :; do
        if [ "$current" -ef "$2" ]; then
            return 0
        fi
        case "$current" in
            /?*) current=${current%/*} ;;
            *) return 1 ;;
        esac
        current=${current:-/}
    done
}

same_tree() {
    diff -rq -x __pycache__ -x .DS_Store "$1" "$2" >/dev/null 2>&1 \
        && [ "$(link_map "$1")" = "$(link_map "$2")" ]
}

json_escape() {
    local text=$1
    text=${text//\\/\\\\}
    text=${text//\"/\\\"}
    text=${text//$'\n'/\\n}
    text=${text//$'\r'/\\r}
    text=${text//$'\t'/\\t}
    case "$text" in
        *[[:cntrl:]]*)
            local code char
            for code in 1 2 3 4 5 6 7 8 11 12 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 127; do
                char=$(printf '%b' "\\0$(printf '%03o' "$code")")
                text=${text//"$char"/$(printf '\\u%04x' "$code")}
            done
            ;;
    esac
    printf '%s' "$text"
}

SOURCE_DIR=""
HOME_DIR=""
SEEN_PATHS=()
SEEN_RELS=()
SEEN_COUNT=0
STATE=""
DETAIL=""
BACKUP_PATH=""

# Sets STATE and DETAIL for one harness skill directory. Never writes.
classify() {
    local rel=$1
    local skills_dir="$HOME_DIR/$rel"
    local target="$skills_dir/$SKILL_NAME"
    local physical resolved index=0
    DETAIL=""

    if [ ! -d "$(dirname "$skills_dir")" ]; then
        STATE="harness-absent"
        return
    fi
    if physical=$(physical_dir "$(dirname "$skills_dir")") && is_within "$physical" "$SOURCE_DIR"; then
        STATE="conflict"
        DETAIL="harness directory is inside the skill source"
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
    if is_within "$physical" "$SOURCE_DIR"; then
        STATE="conflict"
        DETAIL="skills directory is inside the skill source"
        return
    fi
    while [ "$index" -lt "$SEEN_COUNT" ]; do
        if [ "${SEEN_PATHS[$index]}" = "$physical" ]; then
            STATE="alias"
            DETAIL="same directory as ${SEEN_RELS[$index]}"
            return
        fi
        index=$((index + 1))
    done
    SEEN_PATHS[SEEN_COUNT]=$physical
    SEEN_RELS[SEEN_COUNT]=$rel
    SEEN_COUNT=$((SEEN_COUNT + 1))

    if [ -L "$target" ]; then
        if [ "$target" -ef "$SOURCE_DIR" ]; then
            STATE="linked"
        else
            STATE="stale-link"
            DETAIL="points to $(readlink "$target")"
        fi
    elif [ -d "$target" ]; then
        resolved=$(physical_dir "$target") || resolved=""
        if [ "$target" -ef "$SOURCE_DIR" ]; then
            STATE="source"
        elif [ -z "$resolved" ] || is_within "$SOURCE_DIR" "$resolved"; then
            STATE="conflict"
            DETAIL="contains the skill source or cannot be read"
        elif same_tree "$SOURCE_DIR" "$target"; then
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

# Moves one entry into the backup directory and sets BACKUP_PATH.
move_to_backup() {
    local rel=$1 target=$2 stamp=$3
    local destination="$HOME_DIR/$BACKUP_DIR_NAME/$stamp/${rel//\//_}/$SKILL_NAME"

    if [ -e "$destination" ] || [ -L "$destination" ]; then
        printf 'Refused: backup destination already exists: %s\n' "$destination" >&2
        return 1
    fi
    if ! mkdir -p "$(dirname "$destination")" || ! mv -- "$target" "$destination"; then
        printf 'Refused: could not move %s to %s. Nothing was linked there.\n' "$target" "$destination" >&2
        return 1
    fi
    BACKUP_PATH=$destination
}

create_link() {
    local target=$1

    if [ -e "$target" ] || [ -L "$target" ]; then
        printf 'Refused: %s is occupied. Nothing was linked there.\n' "$target" >&2
        return 1
    fi
    ln -s "$SOURCE_DIR" "$target"
}

# Backs an entry up and links the skill in its place. If the link cannot be
# created, the original entry is put back.
replace_with_link() {
    local target=$2

    move_to_backup "$1" "$target" "$3" || return 1
    if create_link "$target"; then
        return 0
    fi
    if [ ! -e "$target" ] && [ ! -L "$target" ] && mv -- "$BACKUP_PATH" "$target"; then
        printf 'Link failed: %s was restored from the backup.\n' "$target" >&2
    else
        printf 'Link failed: the original entry is kept at %s.\n' "$BACKUP_PATH" >&2
    fi
    return 1
}

run_sync() {
    local allow_backup=$1
    local rel skills_dir target stamp refused=0

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
                if mkdir -p "$skills_dir" && create_link "$target"; then
                    printf '%-15s %s\n' "linked" "$rel"
                else
                    refused=1
                fi
                ;;
            stale-link|copy-identical)
                if replace_with_link "$rel" "$target" "$stamp"; then
                    printf '%-15s %s (%s moved to %s)\n' "linked" "$rel" "$STATE" "$BACKUP_PATH"
                else
                    refused=1
                fi
                ;;
            copy-diverged)
                if [ "$allow_backup" -ne 1 ]; then
                    printf 'Refused: %s differs from the source. Rerun with --backup to move it aside.\n' "$target" >&2
                    refused=1
                elif replace_with_link "$rel" "$target" "$stamp"; then
                    printf '%-15s %s (local copy moved to %s)\n' "linked" "$rel" "$BACKUP_PATH"
                else
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
    if [ "$HOME_DIR" = "$SOURCE_DIR" ] || [ "${HOME_DIR#"$SOURCE_DIR"/}" != "$HOME_DIR" ]; then
        usage_error "The home directory must not be inside the skill source: $HOME_DIR"
    fi

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
