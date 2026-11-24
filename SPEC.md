# CyberD CTF: The Incident — Hunt for VELVET LOCUST

The living design spec. The original build brief is the source of truth; this
file records the decisions made during the build. Player-facing documentation
is in `README.md`.

## Title and flow

- Main title: **CyberD CTF: The Incident** (it matches the intro art). Campaign subtitle: **Hunt for VELVET LOCUST**. "The Grid" is the in-world name for Halcyon Dynamics' network.
- Flow: splash (LYMBO STUDIOS, 2.6 s, skippable) -> title (PRESS ENTER TO JACK IN, then the menu) -> cinematic (9 typewritten pages, about 70 s, skippable) -> character select -> zones 0–8 -> debrief.
- The main menu has New Game, Continue (greyed out without a save), Case Files, Settings, How to Play and Quit. Case Files is an alternate mode that ships with the game. It picks an analyst, then opens the five built-in cases in `challenges/` (ransomware, phishing, card skimming, SIM swap, cryptojacking). Each note is wrapped in two or three layers that are peeled one at a time; the encoding is hidden, xor keys live in the case evidence, and each note carries decoy flags. Answers are stored as sha256. It does not start a campaign save. Every analyst plays that mode the same way. In a zone, Esc/P opens the pause menu: Resume, Settings, How to Play, Save & Quit, Quit.
- Aisha_256 is a third analyst. She stays locked until a hunt reaches the debrief or every Case File is cleared. Her top-down sheet is `Aisha_256 Cyber Sprite top-down.png`. Pattern Breaker pulls the Breach Clock back by 2 for each new piece of evidence and shows that evidence's weak point when it has one.

## Architecture

- `ZoneState` (`game/systems/zone_state.py`) owns all of a zone's rules and has no rendering. The UI and the tests call the same methods (`collect`, `run_query`, `submit_choice`, `map_finding`, `respond`, `check_timeline`, `submit`, `next_hint`). Results come out as events through `drain()`, which the zone scene turns into toasts, sounds and dialogue.
- `game/systems/autoplay.py` solves any zone through those same calls. `tests/test_zones.py` uses it to play the whole campaign for both analysts, and `tests/test_ui_smoke.py` drives the real `App` headlessly (scenes, panels, gate, next zone, debrief).
- Objectives complete strictly in order, but any work done early (evidence, a matching query) counts once its objective comes up.
- Rendering: logical 1280x720, `SCALED | RESIZABLE`, F11 fullscreen. The scene stack supports `switch` (with a fade), `push` and `pop`. Overlays are non-opaque scenes, so the zone scene stops updating underneath them and the clock pauses.
- Maps are procedural and seeded per zone: a start room with Oracle, a three-tile data-bus corridor, one room per host node alternating above and below the bus, and an exit room with a gate column. Tiles are 48 px. Fog of war reveals a 6-tile radius plus whole rooms. Sasha's cache sits in a 3x2 pocket off the bus.
- The last zone file is the debrief; every zone before it is playable (`debrief_index()`).

## Breach Clock and VELVET LOCUST

- `clock.rate` is percent per minute. The adversary state machine moves through dormant, active, spreading (after 240 s, x1.25), alerted (after a tip-off, x2 for 45 s) and contained.
- Premature actions tip off VELVET LOCUST: the clock jumps (`clock` field, default 6) and the alert begins. Steady Hand avoids this 40% of the time. Bad actions add 3.
- Good actions pull the clock back 1.5 points; with Steady Hand they also slow the clock x0.9 (floor 0.4).
- At 100% the zone records a data-loss event (containment -20) and the clock resets to `clock.reset`. The game cannot be lost.
- The clock only runs while you are in the zone: it pauses during dialogue and pause, and keeps running while tool panels are open.

## Hunt Terminal

- Syntax: `search <table> [where cond] [| fields a, b | sort f [desc] | head N | count [by f] | dedup f]`.
- Conditions: `= != ~ > < >= <=` and `in (...)`, combined with and / or / not and parentheses. Conditions written side by side mean "and". Matching is case-insensitive, and `=` supports the `*` wildcard. `\"` escapes a quote inside a string.
- Errors suggest close table and field names.
- A query objective is satisfied when its result contains every `required` row id and returns at most `max_rows` rows, which teaches filtering. If the needed rows are present but buried in a larger result, the player gets a "tighten the filter" message.
- `decode <kind> <ref>`: the ref can be raw text, a row id (the longest matching blob in that row), an evidence id (must already be collected), or `cache`.

## Scoring

- Accuracy 400 x correct / graded.
- Containment 300 x (100 - 12 per tip-off - 20 per data loss - 8 per bad action)%.
- Time 150 up to 120 minutes, falling to 25.
- Flag 150.
- Minus hints (10/15/25), plus 25 per CTF cache.
- Ranks are set at 500 / 700 / 850. The best result per analyst is stored in `saves/profile.json`.
- Autosave happens at the start of each zone. Continuing restarts the current zone, and `RunState.reset_zone` discards partial progress inside it.

## Accessibility

Settings, stored in `saves/settings.json`:

- Text size: 1.0 / 1.15 / 1.3
- Colorblind palette: red and green signals become blue and orange
- CRT scanlines
- Music and sound volume, mute (F8). The title screen uses Hackers Free Reign at the music slider. A hunt uses Hack Your Dreams at about a third of that volume.
- Dialogue speed
- Screen shake
- Full-keyboard mode (hides the cursor)

Every screen works keyboard-only.

## Art decisions (Step 0)

- All images load through `assets/manifest.json`. Originals stay in the `assets/` root; `tools/scan_assets.py --organize` copies them into the layout.
- The character art is painted, not pixel art, so sprites use smooth scaling (`"smooth": true`, `"scale": 0.4`).
- Sprite sheets are 4 columns x 6 rows with uneven row spacing. The manifest stores the measured `layout.rows` / `layout.cols` extents. The loader crops each cell and bottom-aligns it on a `frame_width` x `frame_height` canvas.
  - Row 0: idle down, up, left, right (one frame each)
  - Rows 1–4: walk down, up, left, right (4 frames)
  - Row 5: `interact` (laptop typing, ends on a checkmark; plays once)
- `layout.background: "flood"` means the sheet has no alpha. The solid background connected to the top-left corner is removed at load time.
- Gear tiers follow the story (`tier_by_zone` in the manifest): lvl1 for zones 0–2, lvl10 for zones 3–5, lvl20 for zones 6–9.
- `Intro_Screen.png` is the title screen; it highlights the painted PRESS START banner using `hotspots.intro`.
- Character select uses `Blank Select screen.png`. The three analysts stand on a carousel: the one in front fills the frame (name, role, perk, bio) and the other two stand on the painted platforms. Left/Right or clicking a side analyst turns the carousel (0.35 s, wraps around); Enter or clicking the front analyst confirms. The platforms and the front ring are re-tinted to the accent of whoever stands on them. Positions come from `hotspots.character_select`. A locked analyst shows their `locked_image` (Aisha_256: `Aisha_256 Locked.png`) and can't be confirmed.
- `Top_Down.png` is reference art only (the `reference` list in the manifest).
- Portraits are cut out (solid background removed) and cropped to a face for dialogue and the HUD.
- `cast.oracle` is the white-haired guide. `The Oracle.png` is a 4 by 3 sheet of framed busts used for the figure in each zone, dialogue, and hints. `cast.seer` is VELVET LOCUST: `The Seer_Dialogue.png` is the matching sheet, shown when you tip them off, when evidence is lost, and at the vault. Posters stay out of play.
- The CyberD CTF logo in `ui/logo.png` is the splash mark. `ui/icon.png` and `ui/favicon.ico` are the square window icon, set before the window opens. Optional art the game picks up automatically when listed in the manifest: `backgrounds.<zone id>`, `backgrounds.cinematic`, `tiles.floor|wall|bus`. Missing art uses procedural placeholders.

## Content rules

- Fully offline: no network calls, telemetry, accounts or external APIs.
- IPs come only from 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24, plus private 10.x for internal hosts.
- Domains use only `.example`, `.test` or `.invalid`. All names, hashes and companies are fictional.
- No real malware, no exploit code and no real attacker infrastructure. Malicious commands are inert, readable log text.
- MITRE ATT&CK IDs and names are accurate. `tests/test_content.py` checks the core set and the tactic structure.
