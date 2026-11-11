#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Remove the steam-chat-badge service. Pass --keep-cef-debugging to leave
# Steam's remote debugging port enabled (for example for other tools).
set -euo pipefail

keep_flag=0
for arg in "$@"; do
    case "${arg}" in
        --keep-cef-debugging) keep_flag=1 ;;
        *) echo "usage: $0 [--keep-cef-debugging]" >&2; exit 2 ;;
    esac
done

unit_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"

systemctl --user disable --now steam-chat-badge.service 2>/dev/null || true
rm -f "${HOME}/.local/bin/steam-chat-badge" "${unit_dir}/steam-chat-badge.service"
rm -rf "${unit_dir}/steam-chat-badge.service.d"
systemctl --user daemon-reload
echo "Removed the steam-chat-badge service"

if (( ! keep_flag )); then
    for steam_dir in \
        "${XDG_DATA_HOME:-${HOME}/.local/share}/Steam" \
        "${HOME}/.steam/steam" \
        "${HOME}/.var/app/com.valvesoftware.Steam/.local/share/Steam" \
        "${HOME}/.var/app/com.valvesoftware.Steam/data/Steam" \
        ${STEAM_DIR:+"${STEAM_DIR}"}; do
        flag="${steam_dir}/.cef-enable-remote-debugging"
        if [[ -e "${flag}" ]]; then
            rm -f "${flag}"
            echo "Disabled Steam's remote debugging port (${flag}); restart Steam to close it"
        fi
    done
fi
