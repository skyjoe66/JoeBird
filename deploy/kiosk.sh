#!/bin/bash
exec > "$HOME/kiosk.log" 2>&1
echo "kiosk.sh started $(date)"
env | grep -E 'WAYLAND_DISPLAY|XDG_RUNTIME_DIR|DISPLAY'

URL="http://localhost/"
until curl -s --max-time 3 -o /dev/null "$URL"; do
    echo "waiting for $URL"
    sleep 2
done
echo "server reachable, launching chromium"

rm -f /home/joe/.config/chromium/Singleton{Lock,Socket,Cookie}
exec chromium "$URL" \
    --kiosk \
    --password-store=basic \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-session-crashed-bubble \
    --enable-features=OverlayScrollbar \
    --start-maximized
