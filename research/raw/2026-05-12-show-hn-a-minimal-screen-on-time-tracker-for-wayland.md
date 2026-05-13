# Show HN: A minimal screen-on time tracker for Wayland

- Source: Hacker News Show HN
- Published: Wed, 13 May 2026 00:30:45 +0000
- URL: https://github.com/skorotkiewicz/work-track
- Domain: github.com
- Tags: builders, tools, indie

## Feed summary

Article URL: https://github.com/skorotkiewicz/work-track
Comments URL: https://news.ycombinator.com/item?id=48116395
Points: 1
# Comments: 0

## Extracted article text

A minimal screen-on time tracker for Wayland.
Tracks how long your screen is active each day. Hooks into swayidle
to detect screen on/off and suspend/resume events, persists daily totals to JSON, and correctly handles midnight boundaries.
- Runtime:
$XDG_RUNTIME_DIR/worktrack/
(tmpfs, no disk writes during tracking) - Persist:
$XDG_DATA_HOME/worktrack/YYYY-MM-DD.json
work-track on # screen on (swayidle resume / after-resume)
work-track off # screen off (swayidle timeout / before-sleep)
work-track status # print today's total
work-track save # bank current session, persist to JSON
work-track log # show last 7 days
mini-track stats N # last N days (default: 1)
Add to your compositor startup config (e.g., Niri):
spawn-sh-at-startup "swayidle -w \
timeout 300 'swaylock -f -i /usr/share/backgrounds/archlinux/snow.jpg' \
timeout 600 'work-track off; niri msg action power-off-monitors' \
resume 'work-track on' \
before-sleep 'work-track off; swaylock -f -i /usr/share/backgrounds/archlinux/snow.jpg' \
after-resume 'work-track on' &"
resume
→ monitor wakeafter-resume
→ system resume
Runtime state lives in $XDG_RUNTIME_DIR
(tmpfs/RAM) instead of writing straight to the JSON for two reasons:
-
Zero disk wear: If
work-track status
is used in a Waybar that updates every 5 seconds, writing to JSON would wear out your SSD. tmpfs allows instant, zero-wear reads/writes. -
Crash safety: If the system loses power while the screen is active, the in-memory state is lost. This prevents writing an incorrect “always-on” session to disk, which would otherwise corrupt historical accuracy. At most, a small amount of unrecorded time is lost, while existing daily JSON data remains valid. A systemd timer reduces this gap to roughly ~5 minutes.
See systemd for implementation details.
{
"custom/worktrack": {
"exec": "work-track status",
"interval": 60,
"format": "⏱ {}"
}
}
{
"date": "2026-05-12",
"seconds": 13335
}
