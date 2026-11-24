# CyberD CTF: The Incident — Hunt for VELVET LOCUST

A top-down threat hunting and incident response strategy game. You play a SOC
analyst inside "the Grid", Halcyon Dynamics' network drawn as a neon city, and
chase a fictional threat actor, VELVET LOCUST, through every stage of an
intrusion. Each zone teaches one stage of the attack, mapped to MITRE ATT&CK.

- Fully offline: no network calls, no telemetry, no accounts.
- Python 3.11+ and pygame-ce. The title screen plays Hackers Free Reign. During a hunt, Hack Your Dreams plays quietly in the background. Sound effects are synthesized.
- About 2–3 hours for a first playthrough. There are two analysts, each with a different perk.

## Run

```
pip install -r requirements.txt
python main.py
```

## Controls

| Action | Keys | Mouse |
|---|---|---|
| Move | WASD / arrow keys | Click the floor to walk there |
| Interact (host, Oracle, CTF cache) | E or Enter | Click the object |
| Hunt Terminal | T | Toolbar |
| Evidence Journal | J | Toolbar |
| Hypothesis Board | B | Toolbar |
| ATT&CK Matrix | M | Toolbar |
| Timeline | L | Toolbar |
| Respond (containment actions) | R | Toolbar |
| Oracle hint | H | Toolbar |
| Close a panel | Esc (or the panel's key) | Right click |
| Pause menu (settings, how to play, save & quit) | Esc or P | |
| Advance / skip dialogue | Enter, Space, E / Esc | Click |
| Fullscreen / mute | F11 / F8 | |

Inside panels: Up/Down select, Enter confirm, Tab switches focus or the
selected finding, PgUp/PgDn scrolls. Timeline: Space grabs an event, Up/Down
moves it, C checks. Respond: press Enter twice to commit an action. The game
can be played with the keyboard alone; *Full-keyboard mode* in Settings hides
the mouse cursor.

## The analysts

| | Demetri | Sasha |
|---|---|---|
| Role | Ethical Hacker / Incident Responder | Hacker / CTF Player |
| Accent | Red | Neon green |
| Perk | **Steady Hand**: 40% chance a premature action doesn't tip off the adversary; every correct response slows the Breach Clock (x0.9) | **Flag Sense**: pivot tips in the terminal, plus a bonus CTF cache puzzle in every zone (+25 points each) |

**Aisha_256** (Stealth Intrusion Analyst) is locked until you finish the hunt once or clear every Case File. **Pattern Breaker**: each piece of evidence you log pulls the Breach Clock back by 2 and, when that file has one, shows its weak point.

Your best rank is saved per analyst.

## How a zone plays

1. Talk to **Oracle** for the briefing.
2. Walk the data bus and **investigate hosts** (E) to collect evidence.
3. **Hunt** in the terminal. Queries prove or disprove your hypothesis:
   ```
   search proc where parent="winword.exe" and name="powershell.exe"
   search net where src="10.20.4.142" and dport=445 | count by dst
   decode base64 p-202          (decode a row's encoded blob by its id)
   ```
   Type `help`, `tables`, `fields <table>` or `examples` in the terminal.
4. Pin evidence on the **Board** and answer the hypothesis question.
5. Rebuild the **Timeline** and **map** each finding to a technique under the right tactic.
6. **Respond** in the right order: preserve, contain, eradicate, recover. Acting too early tips off VELVET LOCUST.
7. When every objective is done, the exit gate opens. Walk east through it.

The **Breach Clock** ticks from Zone 1 on (it freezes while paused and during
dialogue). At 100%, data is stolen: your containment score drops and the clock
resets. You can't lose the game, only points. Hints cost 10 / 15 / 25 points
by tier and never lock you out.

**Score** (max 1000): accuracy 400 + containment 300 + time 150 + flag 150,
minus hints, plus 25 per CTF cache. **Ranks**: Junior Analyst, Hunter (500+),
Senior Hunter (700+), Threat Hunt Lead (850+).

## Learning objectives by zone

| Zone | Phase | You learn to... | ATT&CK |
|---|---|---|---|
| 0 Briefing Room | Preparation | Use the tools, follow the hypothesis-driven hunt loop, and read the Pyramid of Pain | — |
| 1 Inbox Gate | Detection & Analysis | Read email headers and SPF/DKIM/DMARC, identify the sender infrastructure, and scope who got the lure | T1566.001 |
| 2 Execution Fields | Detection & Analysis | Spot odd parent/child processes, decode encoded PowerShell, and pivot from a process to its network activity | T1204.002, T1059.001 |
| 3 Clockwork Tower | Detection & Analysis | Find persistence in scheduled tasks and Run keys, and compare autostarts against a baseline | T1053.005, T1547.001 |
| 4 Shadow Archives | Detection & Analysis | Detect LSASS access by its access rights, find dump files, and work out whose credentials were exposed | T1003.001 |
| 5 Recon Maze | Detection & Analysis | Tell admin discovery from attacker discovery by host and account, and catch internal sweeps | T1087.002, T1018 |
| 6 Bridges | Containment, Eradication & Recovery | Follow admin-share writes, remote service creation and RDP chains that break the allowed paths; contain in a coordinated way | T1021.002, T1021.001, T1569.002 |
| 7 Beacon Spire | Containment, Eradication & Recovery | Find C2 beaconing (regular, fixed-size check-ins), encoded IDs in URLs, and DNS TXT tunnelling | T1071.001, T1071.004 |
| 8 Core Vault | Containment, Eradication & Recovery | Scope exfiltration, defuse staged ransomware, rebuild the kill chain, contain in order, and capture the flag | T1560.001, T1041, T1486, T1490 |
| 9 Debrief | Post-Incident Activity | Turn the incident into a report: lessons, fixes and detections per zone | — |

## Safety and realism

- All IPs come from documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) or private 10.x addresses.
- All domains end in `.example`, `.test` or `.invalid`.
- Hashes, people, hosts and companies are made up.
- Malicious commands are inert log text for analysis only. There is no working exploit code or malware.
- `tests/test_content.py` enforces all of this, and also checks that ATT&CK IDs and names are correct and that the code never imports a networking module.

## Art: your images

All images load through `assets/manifest.json`, so you can swap art without
touching code. Anything missing or broken falls back to a procedural
placeholder and is noted once on the console; the game never crashes over art.
Your originals in the `assets/` root are never renamed or deleted. The scanner
copies them into this layout:

```
assets/
  manifest.json                       what the game loads (paths relative to assets/)
  Intro_Screen.png, Sasha_lvl1.png...  your originals (left untouched)
  backgrounds/
    intro.png                          title screen
    zone_01.png ...                    optional: art behind a zone map (key = zone id)
    cinematic.png                      optional: backdrop for the opening story
  characters/<id>/<tier>/
    portrait.png                       dialogue/HUD face and select-screen art
    spritesheet.png                    in-game animation
  ui/logo.png                          CyberD CTF logo (splash and placeholder title)
  ui/icon.png                          square window icon made from the logo
  ui/favicon.ico                       same icon at 16, 32, 48 and 256 pixels
  tiles/floor.png, wall.png, bus.png   optional map tiles (any square size)
```

**I added new images.** Run `python tools/scan_assets.py` to see what was
found and what each image is guessed to be. Then run
`python tools/scan_assets.py --organize` to copy the images into place and
update the manifest (your manual edits to scale, fps, animations and hotspots
are kept). Finally, run `python tools/preview_sprites.py` to check how each
sprite sheet is sliced.

### Sprite sheet format

- A grid of frames, one animation per row. The game's sheets are 4 columns x 6 rows:
  - Row 0: idle down, up, left, right (one frame each)
  - Rows 1–4: walk down, up, left, right (4 frames each)
  - Row 5: `interact` (typing on a laptop, plays once)
- Rows and columns can be unevenly spaced. The manifest stores measured pixel
  extents in `layout.rows` and `layout.cols`. Each cell is cropped, then
  bottom-centre aligned on a `frame_width` x `frame_height` canvas.
- If `layout` is missing, the sheet is cut into an even grid of `frame_width` x `frame_height` cells.
- Transparent PNGs are best. For a sheet on a solid background, set
  `"layout": {"background": "flood"}` and the background is removed at load time.
- Per-character settings: `scale` (0.4 for the painted 1024x1536 sheets),
  `smooth` (true for painted art, false for pixel art), and `animations`
  (`{"walk_down": {"row": 1, "start": 0, "frames": 4, "fps": 8}}`).
  A missing `walk_left` or `walk_right` is mirrored from the other one.
- Gear tiers live under `tiers` (`lvl1`, `lvl10`, `lvl20`). `tier_by_zone`
  chooses which tier is shown in each zone.
- `hotspots.intro` holds normalized positions on the painted intro image
  (PRESS START, each character, the name plates and the centre card area). The
  title screen uses them to highlight the painting.
- Character select is a carousel on `Blank Select screen.png`.
  `hotspots.character_select` marks the centre frame, the two painted
  platforms and where the front analyst stands. The platforms are re-tinted to
  the accent of whoever stands on them.
- Optional per-character keys: `locked_image` (shown on the carousel while
  the analyst is locked) and `cutout` (`{"tolerance": 16, "open": 3}`, a
  stricter background removal for full-body art drawn on black with dark
  outlines). Files the manifest points at directly are left alone by the
  scanner.

## Case Files

An alternate mode that ships with the game, separate from the hunt. Title menu, **Case Files**, then pick an analyst. Every analyst plays it the same way. Campaign rank and the autosave are left alone.

The built-in cases live in `challenges/`. Each case is a `.json` file plus a text artifact. The game reads them as text and does not run them. Five ship, easiest first:

| Lv | Case | Crime | Layers |
|---|---|---|---|
| 2 | Locked share, copy already gone | Double-extortion ransomware | base64, rot13 |
| 3 | The login page one word off | Credential phishing with a live code relay | base64, xor |
| 3 | Checkout page, extra listener | Web card skimming | hex, base64, rot13 |
| 3 | Seven minutes, one number | SIM swap account takeover | xor, base64 |
| 4 | Build server never sleeps | Cryptojacking (T1496 Resource Hijacking) | base64, xor, rot13 |

Business email compromise stays in the VELVET LOCUST hunt.

How a case plays:

- The encoding isn't shown. `identify` describes the working text (alphabet, length, whether it reads as English) without naming the answer.
- `decode base64|hex|rot13` peels one layer. `decode xor <key>` works on hex bytes; the key is never in the clue, only in the `evidence` lines, next to a decoy secret.
- `undo` steps back one decode, `reset` goes back to the artifact, `show` prints the working text in full.
- Every note lists three or more flags. Only one answers the clue's question; the evidence decides which. Submitting a decoy says so.
- `hint` gives up to three hints. Solving with no hints and no wrong answers is a clean solve.

### Writing a case

1. Write the plaintext note in `tools/case_sources/<id>.txt`. Put the right flag and a few decoys in it.
2. Create `challenges/<id>.json` with `title`, `clue`, `difficulty` (1 to 5), `layers` in the order the player peels them (for example `["base64", {"kind": "xor", "key": "jx9"}, "rot13"]`), `evidence`, and `hints`.
3. Run `python tools/build_case.py <id> --flag "FLAG{...}"`. It writes the artifact and stores the answer as `answer_sha256`, so the json doesn't give it away. Put `rot13` after hex, base64, or xor layers; the tool refuses orders that don't round-trip.

A plain `"answer"` field still works for quick cases, and so does the older single `"encoding"` / `"key"` form.

## Adding a zone

1. Copy a zone file, e.g. `data/zones/zone_03.json`, to a new number. The last zone file is always the debrief, so renumber `zone_09.json` (and its `index`) to stay last.
2. Edit the fields:
   - `index`, `name`, `phase`, `lesson`, `accent`, and `attack` (technique IDs that exist in `data/attack_techniques.json`).
   - `clock`: `rate` (% per minute, 0 for none), `start`, `reset`, and optionally `spread` and `infected` node order.
   - `nodes`: hosts to investigate. Each has `id`, `host`, `label`, `ip`, `role`, and the `evidence` ids it holds.
   - `evidence`: `title`, `type`, `host`, `time`, `lines` (the artifact text), and an optional `tip`.
   - `telemetry`: one table per name (`proc`, `net`, `dns`...), each with `rows` (every row needs an `id`), `columns`, `description`, and `noise` (the count of seeded background rows taken from `data/telemetry_noise.json`). For periodic traffic such as beacons, use `generate`.
   - `objectives`, completed in order. Every objective has `id`, `type`, `title`, `desc` and three `hints`. The types are:
     - `talk`
     - `open` (`panel`)
     - `visit` (`nodes`)
     - `collect` (`evidence`)
     - `query` (`table`, `required` row ids, `max_rows`, `solution`)
     - `decode` (`answer_contains`, `solution`)
     - `choice` (`prompt`, `options` with exactly one `correct`, optional `pins`)
     - `timeline` (`events` listed in the correct order)
     - `map` (`findings`)
     - `respond`
     - `flag`
     - Optional on any objective: `reward_evidence` and `dialogue`.
   - `findings`: `text`, `technique`, `tactics`, and optional `accept`, `hint` and `success`.
   - `responses`: `label`, `description`, `tradeoff`, and `outcome` (`good`, `premature` or `bad`). Good actions can also set `required`, `requires` and `clears`; any action can set `clock` and `feedback`.
   - `puzzle` (optional, Sasha's cache): `title`, `encoding` (base64, hex, xor or rot13), `answer`, `key`, `clue`.
   - `dialogue`: `intro`, `talk` and `outro` lists of line keys.
3. Strings can contain `[[base64:text]]`, `[[base64u16:text]]`, `[[hex:text]]`, `[[rot13:text]]` or `[[xor:0x5c:text]]`. These are encoded at load time, so a puzzle can never drift from its answer.
4. Add the dialogue lines to `data/dialogue/shared.json`, with per-character overrides in `data/dialogue/<id>.json`. Add a `z<N>_node_<id>` thought for each node.
5. Add the zone to `tier_by_zone` in the manifest, and optionally add `backgrounds/<zone id>.png`.
6. Run `python -m pytest`. `tests/test_zones.py` solves every zone automatically for both analysts. It checks that every query solution fits `max_rows`, that every technique sits under the right tactic, and that the response order can be satisfied. `tests/test_content.py` checks the dialogue keys and the safety rules.

## Adding a character

1. Add an entry to `data/characters.json` with `id`, `name`, `role`, `bio`, `accent`, `select_line`, `perk` (`id`, `name`, `description`) and a `palette` (used for placeholder art).
2. Reuse a perk id (`steady_hand`, `flag_sense`), or add a new one in `game/characters/perks.py` and check it where it matters (`ZoneState`).
3. Create `data/dialogue/<id>.json` with a `select` line, any `_p` (player) line overrides, and the node thoughts.
4. Drop the portrait and sprite sheet images into `assets/`, then run `python tools/scan_assets.py --organize` and `python tools/preview_sprites.py --char <id>`.

## Tools and developer commands

| Command | What it does |
|---|---|
| `python main.py --no-assets` | Ignore `assets/` and play with procedural placeholders only |
| `python main.py --scene zone --character=sasha --zone=4` | Jump straight into a zone |
| `python main.py --scene gallery` | Every character tier and animation, real art vs placeholders |
| `python main.py --scene title --snapshot out.png --frames 120` | Render off-screen and save a PNG (uses a throwaway save folder) |
| `python tools/scan_assets.py [--organize]` | Report images, sizes, guessed roles and manifest problems / organize them |
| `python tools/preview_sprites.py [--char ID] [--tier T] [--show]` | Contact sheets of how sprite sheets are sliced (written to `previews/`) |
| `python -m pytest` | Run the tests: query language, decoding, scoring, save/load, asset fallback, every zone solved headlessly, UI smoke tests, content safety |

Saves are local JSON files in `saves/`: `autosave.json` (written at the start
of each zone), `profile.json` (best rank per analyst), and `settings.json`.

## Project layout

```
main.py                 entry point
game/engine/            app loop, scenes, input, camera, pathfinding, settings
game/art/               manifest loader, sprite slicing, placeholders, screen effects
game/audio/synth.py     music playback and synthesized sound effects
game/systems/           query language, terminal, zone rules, scoring, saves, ATT&CK, dialogue
game/world/             zone loading, procedural maps, map rendering
game/entities/          player, Oracle, host nodes, adversary state machine
game/ui/                widgets, HUD, dialogue box, tool panels
game/scenes/            splash, title, cinematic, character select, zone, debrief, overlays
data/                   zones, dialogue, characters, ATT&CK subset, background telemetry
tools/                  scan_assets.py, preview_sprites.py
tests/                  pytest suite
```
