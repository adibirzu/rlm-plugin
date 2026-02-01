#!/bin/bash
# RLM Plugin Installer v3.0.0
# Installs the RLM plugin for Claude Code and enables it in settings.
#
# Usage:
#   bash install.sh              # Install from current directory
#   bash install.sh --uninstall  # Remove the plugin

set -e

PLUGIN_DIR="$HOME/.claude/plugins/repos/rlm-plugin"
CACHE_DIR="$HOME/.claude/plugins/cache/local-plugins/rlm"
SETTINGS_FILE="$HOME/.claude/settings.json"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

uninstall() {
    echo "Uninstalling RLM plugin..."
    [ -d "$PLUGIN_DIR" ] && rm -rf "$PLUGIN_DIR" && info "Removed $PLUGIN_DIR"
    [ -d "$CACHE_DIR" ] && rm -rf "$CACHE_DIR" && info "Removed cache"

    if [ -f "$SETTINGS_FILE" ]; then
        # Remove rlm entries from settings (basic sed approach)
        if command -v python3 &>/dev/null; then
            python3 -c "
import json, sys
try:
    with open('$SETTINGS_FILE', 'r') as f:
        s = json.load(f)
    ep = s.get('enabledPlugins', {})
    ep.pop('rlm@local-plugins', None)
    ep.pop('rlm@local', None)
    s['enabledPlugins'] = ep
    with open('$SETTINGS_FILE', 'w') as f:
        json.dump(s, f, indent=2)
    print('Settings updated')
except Exception as e:
    print(f'Could not update settings: {e}', file=sys.stderr)
"
        else
            warn "python3 not available — manually remove 'rlm@local-plugins' from $SETTINGS_FILE"
        fi
    fi
    info "RLM plugin uninstalled. Restart Claude Code."
    exit 0
}

# Handle --uninstall flag
[ "${1:-}" = "--uninstall" ] && uninstall

echo "Installing RLM Plugin v3.0.0 for Claude Code..."
echo ""

# Step 1: Verify source files exist
REQUIRED_FILES=(".claude-plugin/plugin.json" "commands/rlm.md")
for f in "${REQUIRED_FILES[@]}"; do
    [ ! -f "$SCRIPT_DIR/$f" ] && error "Missing required file: $f (run from plugin directory)"
done
info "Source files verified"

# Step 2: Create plugin directory structure
mkdir -p "$PLUGIN_DIR/.claude-plugin"
mkdir -p "$PLUGIN_DIR/commands"
info "Plugin directories created"

# Step 3: Copy plugin files
cp "$SCRIPT_DIR/.claude-plugin/plugin.json" "$PLUGIN_DIR/.claude-plugin/"
cp "$SCRIPT_DIR/commands/rlm.md" "$PLUGIN_DIR/commands/"

# Copy optional files if they exist
for f in README.md IMPLEMENTATION.md EXAMPLES.md install.sh; do
    [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$PLUGIN_DIR/"
done
info "Plugin files copied to $PLUGIN_DIR"

# Step 4: Clear old cache (will be regenerated on Claude Code restart)
if [ -d "$CACHE_DIR" ]; then
    rm -rf "$CACHE_DIR"
    info "Old cache cleared (will regenerate on restart)"
fi

# Step 5: Update settings.json
if [ -f "$SETTINGS_FILE" ]; then
    # Validate existing settings.json is valid JSON
    if command -v python3 &>/dev/null; then
        if ! python3 -c "import json; json.load(open('$SETTINGS_FILE'))" 2>/dev/null; then
            error "Existing $SETTINGS_FILE is not valid JSON. Fix it manually before installing."
        fi
        # Backup before modifying
        cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup"
        info "Backed up settings to $SETTINGS_FILE.backup"
        python3 -c "
import json
with open('$SETTINGS_FILE', 'r') as f:
    s = json.load(f)
ep = s.setdefault('enabledPlugins', {})
ep['rlm@local-plugins'] = True
# Clean up old key if present
ep.pop('rlm@local', None)
with open('$SETTINGS_FILE', 'w') as f:
    json.dump(s, f, indent=2)
print('Settings updated')
"
        info "Plugin enabled in settings.json"
    else
        warn "python3 not available — manually add '\"rlm@local-plugins\": true' to $SETTINGS_FILE"
    fi
else
    mkdir -p "$(dirname "$SETTINGS_FILE")"
    echo '{"enabledPlugins":{"rlm@local-plugins":true}}' > "$SETTINGS_FILE"
    info "Created settings.json with plugin enabled"
fi

# Step 6: Verify
echo ""
echo "Installation complete!"
echo ""
echo "Files installed:"
ls -la "$PLUGIN_DIR/"
echo ""
echo "Settings:"
grep -o '"rlm[^"]*"[^,}]*' "$SETTINGS_FILE" 2>/dev/null || echo "(check manually)"
echo ""
echo "Next step: Restart Claude Code to load the plugin."
echo "Then use: /rlm \"your task\" /path/to/context"
