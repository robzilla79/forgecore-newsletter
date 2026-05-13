# Show HN: Tmux-palette – Raycast-style command palette for tmux

- Source: Hacker News Show HN
- Published: Wed, 13 May 2026 00:03:11 +0000
- URL: https://www.eduwass.com/blog/tmux-palette/
- Domain: eduwass.com
- Tags: builders, tools, indie

## Feed summary

Article URL: https://www.eduwass.com/blog/tmux-palette/
Comments URL: https://news.ycombinator.com/item?id=48116193
Points: 1
# Comments: 3

## Extracted article text

A Raycast-Style Command Palette for tmux
Tweeted a screenshot of this earlier today, people asked for the code, open-sourced it the same day: github.com/eduwass/tmux-palette.
tmux has a million commands and zero discoverability. You either know the bind or you don't. Raycast fixed that for macOS apps. This does the same for tmux: hit a key, fuzzy-find, run.
The opentui detour
First version used opentui — flexbox layout in the terminal, theming, mouse events. Tutorial-clean code, ~50 lines per palette.
It shipped. It was slow.
=== bun no-op === 0.00 s
=== bun + opentui import === 0.19 s
opentui ships native Yoga bindings. They deserialize on import. Every popup open paid 190ms loading them before drawing a single character. Felt like a 200ms hiccup every time. bun build --compile
doesn't help — it bundles the runtime, not the imports.
The rewrite
I dropped the framework. The renderer now writes ANSI escape codes straight to stdout, like the prototype I started with.
stdout.write("\x1b[?2026h\x1b[?25l\x1b[H" + frame + "\x1b[?2026l")
That's the whole render call. ?2026h/l
is synchronized output — tmux 3.4+ swaps the frame atomically, so holding the arrow key doesn't flicker. Cold start went from 190ms to 20ms.
The framework gained ~100 lines for manual width/scroll/mouse handling. Each palette stayed the same size. Net wash on lines, 10× speedup.
User-land config
Customization lives in ~/.config/tmux-palette/
. Four JSON files, one job each. Add your own commands without forking:
// ~/.config/tmux-palette/commands.json
[
{ "icon": "", "title": "Toggle Diff Viewer", "category": "Tools",
"action": { "tmux": "run-shell '~/scripts/diff-viewer.sh'" } }
]
shortcuts.json
overrides the right-side label. theme.json
overrides colors. aliases.json
adds chips. The source-level definePalette()
API is still there for power users, but nobody should have to fork to label a key.
The dispatch trick
tmux's confirm-before
and command-prompt
need stdin. If you run them inside the popup, they hang — the popup owns stdin.
So the palette doesn't run the command. It writes the encoded command to a tempfile and exits. The bash wrapper reads the file after display-popup
returns and runs it in the host context. Prompts get stdin, users press y/n, world keeps spinning.
tmux display-popup -E "TMUX_PALETTE_CMD='$CMD_FILE' bun src/cli.ts"
[ -s "$CMD_FILE" ] && eval "tmux $(cat "$CMD_FILE")"
Embarrassingly long to figure out the first time. Sub-100-byte fix.
Install
git clone https://github.com/eduwass/tmux-palette ~/Sites/tmux-palette
cd ~/Sites/tmux-palette && bun install
Then in .tmux.conf
:
bind -n C-Space run-shell "~/Sites/tmux-palette/bin/tmux-palette.sh"
Reload, hit Ctrl+Space.
The README has an agent-handoff prompt — paste it into Claude Code / Codex / opencode / Cursor and it does the install, asks you which key to bind, optionally reads your terminal config and writes a matching theme. Onboarding via "paste this into your agent" feels right for 2026.
Repo: github.com/eduwass/tmux-palette.
Read other posts →
