# The settings file

Save it as `design-system.json` in the design system folder. The reel editor skills read it, so keep these keys and value names exactly. Fill only what the person chose. Leave out anything they skipped.

```json
{
  "name": "My reel look",
  "fonts": { "captions": "Montserrat", "titles": "Calistoga", "numbers": "Anton", "accents": "Instrument Serif" },
  "colors": { "text": "#ffffff", "key": "#ffe94d", "outline": "#14080f", "accent": "#ddd0ff", "accent2": "#ffb3d1" },
  "captions": { "style": "italic_punch", "px": 150, "y": 1360, "outline": 8, "under_windows": { "px": 80, "y": 1400 }, "notes": "One word at a time, key words in yellow" },
  "hook": { "style": "bubbly", "clears_on": "first spoken number", "notes": "Stacked lines pop in from the first frame" },
  "number_pop": { "font": "Anton", "color": "key", "px": 540, "outline": 16, "rotate": -4, "notes": "Fills the middle as it is said" },
  "list_cards": { "number_font": "Anton", "label_font": "Archivo Black", "y": 420, "notes": "01, 02, 03 up top, label with a tick" },
  "word_pops": { "font": "Instrument Serif", "font_style": "italic", "notes": "Feeling words around the head, never on the face" },
  "series_title": { "font": "Calistoga", "text": "my reel series|part 1", "notes": "Same look every episode. Lines split with |" },
  "sounds": { "typing": "click1", "pop": "pop", "reveal": "sparkle", "transition": "swish", "volume_db": -14 },
  "safe_zone": { "top": 250, "bottom": 1480, "side": 60, "buttons_x": 940, "buttons_y": 1050 },
  "rules": ["Never black text on a yellow block. Use outlined text instead.", "Caption every spoken word."],
  "references": [
    { "id": "ref1", "who": "Creator name", "title": "Reel topic", "url": "https://www.instagram.com/reel/...",
      "captions": ["Hook frame", "Caption style", "Proof card"], "notes": "What they do, one or two sentences.", "borrowed": "Captions above the head" }
  ]
}
```

## Allowed values
- `captions.style`: `italic_punch`, `serif_mix`, `yellow_key`, `small_top`. These match options A to D in the starter set.
- `hook.style`: `bubbly`, `editorial`, `soft_serif`, `poster`, `grotesk`. These match title options A to E.
- `number_pop.color`: a key from `colors` or a hex value. For number option C (butter serif) use `#f6e7a1`, not `key`, so changing the key color later doesn't change the number.
- `sounds` values: file names in `sounds/` without `.m4a`.
- `captions.y` (top of the caption block) and `word_pops.spots` (a list of `[x, y, rotate, "word"]`) move the previews. Set them when a default position covers the face in their frame.
- `safe_zone`: keep these numbers unless the person checked their own phone and gave new ones.
- `rules`: always include the two rules above, plus every rule the person adds.

Frame sizes and positions are in pixels on a 1080x1920 frame.
