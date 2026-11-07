#!/bin/bash
# Installs a desktop icon and an app-menu entry for the Self Balancing Bot app.
DIR="$(cd "$(dirname "$0")" && pwd)"
ENTRY="[Desktop Entry]
Type=Application
Name=Self Balancing Bot
Comment=Camera, LiDAR and drive dashboard for the Yahboom bot
Exec=\"$DIR/.venv/bin/python\" \"$DIR/main.py\"
Path=$DIR
Icon=$DIR/assets/icon.png
Terminal=false
Categories=Utility;Development;"
mkdir -p ~/.local/share/applications
echo "$ENTRY" > ~/.local/share/applications/self-balancing-bot.desktop
echo "$ENTRY" > ~/Desktop/self-balancing-bot.desktop
chmod +x ~/.local/share/applications/self-balancing-bot.desktop ~/Desktop/self-balancing-bot.desktop
gio set ~/Desktop/self-balancing-bot.desktop metadata::trusted true 2>/dev/null
echo "Launcher installed."
