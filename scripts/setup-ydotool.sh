#!/usr/bin/env bash
# Install or uninstall ydotool + ydotoold for Glosio on Debian 13.
#
# Install (default):
#   - Installs the `ydotool` package from trixie-backports (provides both
#     ydotool and ydotoold plus the systemd user unit).
#   - Loads the `uinput` kernel module (now and on every boot).
#   - Writes a udev rule granting /dev/uinput rw to the active-seat user via
#     systemd-logind's `uaccess` tag — NOT via `input` group membership.
#     This keeps the capability scoped to the active GUI session rather than
#     uid-wide (no SSH/cron/non-seat exposure).
#   - Enables the `ydotool` systemd user unit so the daemon runs in your session.
#
# Uninstall (--uninstall):
#   - Stops and disables the systemd user unit.
#   - Removes the udev rule and modules-load drop-in.
#   - Leaves the `ydotool` package installed; remove it manually with
#     `sudo apt remove ydotool` if desired.
#
# Run as your normal user. Sudo will prompt for the system-level steps.

set -euo pipefail

UDEV_RULE="/etc/udev/rules.d/70-uinput.rules"
MODULES_LOAD="/etc/modules-load.d/uinput.conf"
SYSTEMD_UNIT="ydotool.service"

log()     { printf '\033[1;34m[*]\033[0m %s\n' "$*"; }
success() { printf '\033[1;32m[+]\033[0m %s\n' "$*"; }
warn()    { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
err()     { printf '\033[1;31m[-]\033[0m %s\n' "$*" >&2; }

usage() {
    cat <<EOF
Usage: $(basename "$0") [--uninstall] [--help]

Default action installs and configures ydotool for Glosio.
Use --uninstall to reverse the configuration.
EOF
}

require_not_root() {
    if [[ $EUID -eq 0 ]]; then
        err "Do not run as root. Run as your normal user; sudo will prompt as needed."
        err "Running as root would target root's systemd --user instance, not yours."
        exit 1
    fi
}

install_action() {
    log "Installing ydotool from trixie-backports..."
    if ! sudo apt install -y -t trixie-backports ydotool; then
        err "apt install failed. Is trixie-backports enabled in /etc/apt/sources.list.d/?"
        err "Add: deb http://deb.debian.org/debian trixie-backports main"
        exit 1
    fi

    log "Loading uinput kernel module..."
    sudo modprobe uinput
    echo uinput | sudo tee "$MODULES_LOAD" >/dev/null

    log "Writing udev rule (uaccess only, no input group): $UDEV_RULE"
    sudo tee "$UDEV_RULE" >/dev/null <<'EOF'
# Glosio: grant /dev/uinput rw to the active-seat user via systemd-logind ACL.
# Uses TAG+="uaccess" instead of GROUP="input" so the capability is scoped to
# the active GUI session (no SSH/cron/non-seat exposure).
KERNEL=="uinput", MODE="0660", TAG+="uaccess", OPTIONS+="static_node=uinput"
EOF

    log "Reloading udev and re-triggering /dev/uinput..."
    sudo udevadm control --reload-rules
    sudo udevadm trigger --name-match=uinput

    log "Enabling and starting ydotool systemd user unit..."
    systemctl --user daemon-reload
    systemctl --user enable --now "$SYSTEMD_UNIT"

    verify_install
}

verify_install() {
    log "Verifying..."
    local all_ok=1

    if [[ -e /dev/uinput ]]; then
        success "/dev/uinput exists"
    else
        err "/dev/uinput missing"
        all_ok=0
    fi

    # Ask the kernel directly whether the current UID can write — works
    # regardless of which mechanism granted access (uaccess ACL, group, mode).
    if [[ -w /dev/uinput ]]; then
        success "/dev/uinput is writable by $USER"
    else
        warn "/dev/uinput not writable by $USER from this shell."
        warn "If this shell is a tty (XDG_SESSION_TYPE=$XDG_SESSION_TYPE), uaccess won't apply here"
        warn "even when it's correctly granted to your graphical session. Test from Glosio instead,"
        warn "or run 'ydotool type hi' from a terminal inside your desktop session."
        all_ok=0
    fi

    if systemctl --user is-active --quiet "$SYSTEMD_UNIT"; then
        success "ydotool daemon is running"
    else
        err "ydotool daemon is not active. Check: systemctl --user status $SYSTEMD_UNIT"
        all_ok=0
    fi

    if [[ -S "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/.ydotool_socket" ]]; then
        success "ydotool socket present"
    else
        warn "ydotool socket not found at \$XDG_RUNTIME_DIR/.ydotool_socket — daemon may not have opened it yet"
    fi

    if [[ $all_ok -eq 1 ]]; then
        success "Setup complete. Restart Glosio to pick up the change."
    else
        warn "Setup partially complete. Resolve the issues above and re-run."
        exit 1
    fi
}

uninstall_action() {
    log "Stopping and disabling $SYSTEMD_UNIT..."
    systemctl --user disable --now "$SYSTEMD_UNIT" 2>/dev/null || true
    systemctl --user daemon-reload

    if [[ -f $UDEV_RULE ]]; then
        log "Removing $UDEV_RULE"
        sudo rm -f "$UDEV_RULE"
    else
        log "$UDEV_RULE not present, skipping"
    fi

    if [[ -f $MODULES_LOAD ]]; then
        log "Removing $MODULES_LOAD"
        sudo rm -f "$MODULES_LOAD"
    else
        log "$MODULES_LOAD not present, skipping"
    fi

    log "Reloading udev..."
    sudo udevadm control --reload-rules
    sudo udevadm trigger --name-match=uinput || true

    if dpkg -s ydotool >/dev/null 2>&1; then
        log "Removing ydotool package..."
        sudo apt remove -y ydotool
    else
        log "ydotool package not installed, skipping"
    fi

    success "Uninstalled."
    warn "The uinput kernel module is still loaded for this boot; it will not auto-load next boot."
}

main() {
    case "${1:-}" in
        --uninstall) require_not_root; uninstall_action ;;
        --verify)    verify_install ;;
        --help|-h)   usage ;;
        "")          require_not_root; install_action ;;
        *)           err "Unknown argument: $1"; usage; exit 1 ;;
    esac
}

main "$@"
