# Design notes

Subject: replaying a Formula 1 weekend, for fans without data-science knowledge. The page's one
job is to let someone step through the sessions and watch the race prediction change.

## Tokens

| Name | Hex | Use |
|---|---|---|
| Tarmac | `#1A1B1E` | page background (track surface, not pure black) |
| Tarmac raised | `#232428` / `#2C2E33` | panels, rows on hover |
| Paint line | `#383A40` | hairlines, dividers |
| Chalk | `#F2F1EC` | primary text (pit-board paint white) |
| Fog | `#A3A5AB` / `#76787F` | secondary / muted text |
| Start-light red | `#E8002D` | start lights, live state, the main action - nothing decorative |
| Timing purple | `#B452F0` | fastest / best of session (as on F1 timing screens) |
| Timing green | `#2FD158` | gained places / correct call |
| Timing yellow | `#F5C518` | caution: penalties, Sprint weekends |

Team colours come from the data and are always paired with the driver code.

Type: Archivo, one family, scale 13 / 16 / 20 / 25 / 49 px (major third). The expanded width
(wdth 125, 800) is reserved for page titles and on-screen-graphics elements: positions, driver
codes, the winner line. Section headings are normal width, bold (`.h2` 25px, `.h3` 20px). Text and
numbers use tabular figures. Sentence case everywhere; the only capitals are driver codes (the
sport's own three-letter abbreviations).

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
- Pass 2 (frontend-design skill): type scale with the wide face kept for page titles and
  on-screen elements; only the tower boxed; race control shows the latest session and folds the rest;
  accuracy chart switched from a 0-1 line chart (differences invisible) to a zoomed dot comparison
  that says the scale is zoomed; removed the decorative rule and repeated "Result hidden" labels.
