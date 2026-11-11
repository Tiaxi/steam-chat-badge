#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Install steam-chat-badge as a systemd user service.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="${HOME}/.local/bin"
unit_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
dropin_dir="${unit_dir}/steam-chat-badge.service.d"

die() { echo "error: $*" >&2; exit 1; }

command -v python3 >/dev/null || die "python3 is required"
python3 -c 'import gi; gi.require_version("Gio", "2.0"); from gi.repository import Gio' 2>/dev/null \
    || die "PyGObject is required (Fedora: python3-gobject, Debian/Ubuntu: python3-gi, Arch: python-gobject)"
command -v systemctl >/dev/null || die "systemd is required"

# Find the Steam folder. STEAM_DIR overrides the search.
flatpak=0
if [[ -n "${STEAM_DIR:-}" ]]; then
    steam_dir="${STEAM_DIR}"
else
    steam_dir=""
    for candidate in \
        "${XDG_DATA_HOME:-${HOME}/.local/share}/Steam" \
        "${HOME}/.steam/steam" \
        "${HOME}/.var/app/com.valvesoftware.Steam/.local/share/Steam" \
        "${HOME}/.var/app/com.valvesoftware.Steam/data/Steam"; do
        if [[ -d "${candidate}/ubuntu12_32" || -f "${candidate}/steam.sh" ]]; then
            steam_dir="$(realpath "${candidate}")"
            break
        fi
    done
    [[ -n "${steam_dir}" ]] || die "Steam folder not found; set STEAM_DIR=/path/to/Steam"
fi
[[ "${steam_dir}" == *"/.var/app/com.valvesoftware.Steam/"* ]] && flatpak=1

install -Dm755 "${repo}/steam-chat-badge" "${bin_dir}/steam-chat-badge"
install -Dm644 "${repo}/systemd/steam-chat-badge.service" "${unit_dir}/steam-chat-badge.service"
echo "Installed ${bin_dir}/steam-chat-badge"
echo "Installed ${unit_dir}/steam-chat-badge.service"

if (( flatpak )); then
    mkdir -p "${dropin_dir}"
    cat > "${dropin_dir}/flatpak.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=%h/.local/bin/steam-chat-badge --app-uri application://com.valvesoftware.Steam.desktop
EOF
    echo "Configured for Flatpak Steam (${dropin_dir}/flatpak.conf)"
fi

flag="${steam_dir}/.cef-enable-remote-debugging"
if [[ ! -e "${flag}" ]]; then
    touch "${flag}"
    echo "Enabled Steam's remote debugging port (${flag})"
fi

systemctl --user daemon-reload
systemctl --user enable steam-chat-badge.service
systemctl --user restart steam-chat-badge.service

if ! python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/json/version", timeout=2)' 2>/dev/null; then
    echo
    echo "Restart Steam (Steam > Exit, then start it again) to open the debugging port."
fi
echo
echo "Done. Check the service with: journalctl --user -u steam-chat-badge -f"
