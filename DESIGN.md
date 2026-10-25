# LionWeather design

Expands the kooexperience design core (`~/.agent-memory/design/DESIGN-core.md`). The core wins on conflict.

## Read
People in Singapore deciding whether to take an umbrella, usually on a phone, in a few seconds. Mood: a calm instrument panel. Dial: ENERGY 1 / RHYTHM 1 / MOTION 1.

## Rules
- The current reading comes first: place, temperature, condition, one sentence on rain, and the reading time with its source ("NEA reading at 2:17 pm").
- Every number on the Now screen comes from one observation or the forecast that is labelled as such. A missing value is hidden or written "n/a", never a dash or a default.
- Light while the sun is up in Singapore, dark from sunset to sunrise (`ThemeContext` uses SunCalc). The reason is the use scene: phones outdoors by day, in bed at night. No toggle.
- Weather icons follow the time of the slot they describe: a moon, not a sun, after dark.
- Text sits on solid surfaces. Map controls and the radar legend sit outside the map.
- Plain words: "Rain map", "Forecast model", "Update". No model names, sources in brackets, "cached" or error codes in the UI.
- Designed states: loading, no saved place (central Singapore reading), offline (keeps the last reading and says when it was), location blocked (points to search), search with no results.

## Tokens (`src/index.css`, mapped in `tailwind.config.js`)
| Token | Day | Night | Use |
|---|---|---|---|
| bg | `#f4f6f9` | `#0b1220` | page |
| surface / surface-2 | `#ffffff` / `#eef2f6` | `#131c2e` / `#1a2538` | panels, hover |
| line | `#d5dde7` | `#2b384c` | borders, dividers |
| ink | `#111827` | `#e8eef6` | text |
| muted | `#4b5563` | `#9fb0c4` | secondary text (7:1 or better) |
| accent | `#0369a1` | `#7dd3fc` | sky blue: active tab, primary button, links, focus ring |
| rain | `#0369a1` | `#38bdf8` | rain chance of 50% or more |
Status only: good, warn, bad. Chart series use `--c1` to `--c5`, set per theme.

- Type: IBM Plex Sans, self-hosted, chosen for its clear tabular figures. Sizes 12, 14, 16, 24, and 56 for the hero temperature.
- Radius: 6 for controls, 10 for rows, 16 for panels. No shadows, glass, gradients or animated backgrounds.
- Focus: 2px accent outline with a 2px offset everywhere.
