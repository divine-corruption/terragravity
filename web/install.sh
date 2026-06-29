#!/bin/sh
# Terragravity Hermes — macOS / Linux installer
# Usage:  curl -fsSL https://terragravity.cloud/install.sh | sh
#         curl -fsSL https://terragravity.cloud/install.sh | sh -s -- --gateway https://api.terragravity.cloud
#
# Installs the terragravity-hermes launcher to ~/.terragravity, puts a `tg`
# command on PATH, and creates a desktop shortcut. Idempotent: re-running
# upgrades in place. No root required.
set -eu

# ── Config (overridable via flags / env) ─────────────────────────────
TG_GATEWAY="${TG_GATEWAY:-https://api.terragravity.cloud}"
TG_HOME="${TG_HOME:-$HOME/.terragravity}"
TG_BASE="${TG_BASE:-https://terragravity.cloud}"

while [ $# -gt 0 ]; do
  case "$1" in
    --gateway) TG_GATEWAY="$2"; shift 2 ;;
    --home)    TG_HOME="$2"; shift 2 ;;
    --base)    TG_BASE="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;36m›\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

# ── Detect OS ────────────────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
  Darwin) PLATFORM="macos" ;;
  Linux)  PLATFORM="linux" ;;
  *) die "Unsupported OS: $OS (use install.ps1 on Windows)" ;;
esac
say "Installing Terragravity Hermes for $PLATFORM"

# ── Prereqs ──────────────────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || die "python3 is required but not found"
command -v curl    >/dev/null 2>&1 || die "curl is required but not found"

# ── Layout ───────────────────────────────────────────────────────────
mkdir -p "$TG_HOME/bin"
say "Fetching launcher → $TG_HOME/bin/tg-launcher.py"
curl -fsSL "$TG_BASE/launcher.py" -o "$TG_HOME/bin/tg-launcher.py" \
  || die "failed to download launcher from $TG_BASE/launcher.py"

# ── Config file ──────────────────────────────────────────────────────
cat > "$TG_HOME/config.env" <<EOF
# Terragravity launcher config (edit freely)
TG_GATEWAY=$TG_GATEWAY
# Paste your API key here (get one from the Terragravity dashboard):
TG_API_KEY=
EOF
chmod 600 "$TG_HOME/config.env"

# ── `tg` wrapper on PATH ─────────────────────────────────────────────
cat > "$TG_HOME/bin/tg" <<EOF
#!/bin/sh
set -a; . "$TG_HOME/config.env"; set +a
exec python3 "$TG_HOME/bin/tg-launcher.py" "\$@"
EOF
chmod +x "$TG_HOME/bin/tg"

# Link into a PATH dir if possible, else advise.
LINKED=""
for d in "$HOME/.local/bin" "/usr/local/bin"; do
  if [ -d "$d" ] && [ -w "$d" ]; then
    ln -sf "$TG_HOME/bin/tg" "$d/tg" && LINKED="$d" && break
  fi
done
if [ -z "$LINKED" ]; then
  mkdir -p "$HOME/.local/bin"
  ln -sf "$TG_HOME/bin/tg" "$HOME/.local/bin/tg" && LINKED="$HOME/.local/bin"
fi
ok "Installed launcher (tg → $LINKED/tg)"

# ── Desktop shortcut ─────────────────────────────────────────────────
if [ "$PLATFORM" = "linux" ]; then
  APPS="$HOME/.local/share/applications"; mkdir -p "$APPS"
  DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
  DESK="$APPS/terragravity.desktop"
  cat > "$DESK" <<EOF
[Desktop Entry]
Type=Application
Name=Terragravity Hermes
Comment=Talk to your Hermes agent from anywhere
Exec=$TG_HOME/bin/tg chat
Terminal=true
Categories=Development;Utility;
EOF
  chmod +x "$DESK"
  if [ -d "$DESKTOP_DIR" ]; then cp -f "$DESK" "$DESKTOP_DIR/terragravity.desktop" 2>/dev/null && chmod +x "$DESKTOP_DIR/terragravity.desktop" || true; fi
  ok "Desktop shortcut created (applications menu + Desktop)"
elif [ "$PLATFORM" = "macos" ]; then
  APP="$HOME/Desktop/Terragravity Hermes.command"
  cat > "$APP" <<EOF
#!/bin/sh
exec "$TG_HOME/bin/tg" chat
EOF
  chmod +x "$APP"
  ok "Desktop shortcut created (~/Desktop/Terragravity Hermes.command)"
fi

# ── Done ─────────────────────────────────────────────────────────────
printf '\n'
ok "Terragravity Hermes installed."
printf '\n'
printf '  Next steps:\n'
printf '   1. Add your API key:   edit %s  (set TG_API_KEY=...)\n' "$TG_HOME/config.env"
printf '   2. Make sure PATH has: %s   (restart shell or: export PATH="%s:$PATH")\n' "$LINKED" "$LINKED"
printf '   3. Try it:             tg health   then   tg chat\n'
printf '\n'
printf '  Gateway: %s\n' "$TG_GATEWAY"
printf '\n'
