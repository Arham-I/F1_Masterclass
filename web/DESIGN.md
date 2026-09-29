# Design notes

Subject: replaying a Formula 1 weekend, for fans without data-science knowledge. The page's one
job is to let someone step through the sessions and watch the race prediction change.

## Tokens

Direction (pass 3): classier, more masculine, sharper - paddock-motorhome metal and machined edges.

| Name | Hex | Use |
|---|---|---|
| Gunmetal | `#1B1E22` | page background (visibly grey metal, not near-black) |
| Panel / raised | `#23272C` / `#2B3036` | panels, rows on hover |
| Steel hairline | `#3B4148` | dividers, borders |
| Bone | `#ECE9E3` | primary text |
| Titanium | `#A7ADB5` / `#8B929B` | secondary / muted text |
| Racing red | `#C8102E` | start lights, live state, the main action - nothing decorative |
| LED on / off | `#E3142F` / `#3A2A2E` | lamp pixels on the gantry housing `#121417` |
| Timing purple | `#B452F0` | fastest / best of session (as on F1 timing screens) |
| Timing green | `#2FD158` | gained places / correct call |
| Timing yellow | `#E8B923` | caution: penalties, Sprint weekends |

Team colours come from the data and are always paired with the driver code.

Type: Saira (squared, motorsport-technical; variable width, used at wdth 112 for titles and on-screen
elements, 100 for section headings, weight 600) with IBM Plex Sans for text and data (tabular
figures). Scale 13 / 16 / 20 / 25 / 49 px. Sentence case everywhere; the only capitals are driver
codes.

Edges: 2px radius everywhere (full rounding only for dots and lamps). Chamfered cut corners - the
F1 TV-graphics motif - only on the timing tower, the result chart, the gantry housing and the main
buttons.

Start lights: each lamp is an LED cluster (a 5 x 5 pixel grid on a round lamp), lit pixels red,
unlit pixels still visible - no glow. The logo is the same gantry as an LED matrix: a chamfered
housing, two rows of five, three columns lit.

## Layout

```
Replay page
[Play] [●● FP1][●● FP2][●● FP3][○○ Quali][○○ Lights out]      <- sticky start-light gantry
+-- Race control (newest first) ------+ +-- Who can win ---------+
| FP3  Antonelli topped FP3 ...       | | win-chance lines       |
| FP2  ...                            | | ±places per session    |
+-------------------------------------+ +------------------------+
+-- Timing tower: predicted finishing order (full width) -----------+
| 1 ▲2 | LEC  likely P1-P6  38.32% win  73.33% podium ...           |
+-------------------------------------------------------------------+
Session data: timesheet / race pace / tyres
```

Everything is left-aligned. Only the timing tower is a boxed panel (it is the "screen"); race
control, who-can-win and session data are open sections under a hairline, so the page has a clear
main element instead of a grid of identical cards. The calendar is a list, like a championship
calendar.

## Principles

1. The start-light gantry is the one bold element. Revealing the race is "lights out", which is the
   single orchestrated animation.
2. Timing-screen colours carry meaning (purple best, green gained, yellow caution), never decoration.
3. Motion only answers the viewer: rows glide when a session is revealed; nothing animates on its own.
4. Plain, sentence-case copy that names things the way a fan would.

## Pass log

- Pass 1: start-light gantry, timing-screen colours, removed template tells (caps eyebrows,
  dot-joined meta, one-word colour accents, arrow links, fade-in on every section).
- Pass 3 (frontend-design skill, brief "classier, masculine, sharper"): gunmetal/bone/titanium
  tonal palette with a deeper racing red; Saira + IBM Plex Sans; sharp 2px edges and chamfers on
  the signature elements; glowing lamps replaced by LED-pixel clusters; new LED-matrix logo and
  favicon.
- Pass 2 (frontend-design skill): type scale with the wide face kept for page titles and
  on-screen elements; only the tower boxed; race control shows the latest session and folds the rest;
  accuracy chart switched from a 0-1 line chart (differences invisible) to a zoomed dot comparison
  that says the scale is zoomed; removed the decorative rule and repeated "Result hidden" labels.
