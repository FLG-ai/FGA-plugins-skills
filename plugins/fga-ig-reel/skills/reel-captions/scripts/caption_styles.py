"""CSS for each caption style in the design system. Matches the options sheet in reel-design-system."""
FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@800;900&family=Instrument+Serif:ital@0;1'
         '&family=Montserrat:ital,wght@1,900&family=Calistoga&family=Anton&display=block" rel="stylesheet">')

def ol(w, c, drop=0):
    s = f'-webkit-text-stroke:{w}px {c};paint-order:stroke fill;'
    return s + (f'text-shadow:0 {drop}px 0 {c};' if drop else 'text-shadow:0 2px 3px rgba(0,0,0,.55),0 0 18px rgba(0,0,0,.6);')

def word_css(style, colors, key, small=False):
    txt, k, out = colors.get('text', '#ffffff'), colors.get('key', '#ffe94d'), colors.get('outline', '#14080f')
    m = 0.55 if small else 1.0
    px = lambda n: int(n * m)
    if style == 'italic_punch':
        return f"font:italic 900 {px(150)}px/1 Montserrat,sans-serif;text-transform:uppercase;letter-spacing:-.02em;color:{k if key else txt};{ol(px(8), out, px(7))}"
    if style == 'serif_mix':
        if key: return f"font:italic 400 {px(205)}px/1 'Instrument Serif',serif;color:{k};{ol(px(5), out, px(4))}"
        return f"font:900 {px(150)}px/1 'Inter Tight',sans-serif;letter-spacing:-.015em;color:{txt};{ol(px(8), out)}"
    if style == 'yellow_key':
        return f"font:900 {px(150)}px/1 'Inter Tight',sans-serif;letter-spacing:-.015em;color:{k if key else txt};{ol(px(10), out)}"
    # small_top
    if key: return f"font:italic 400 {px(92)}px/1 'Instrument Serif',serif;color:{txt};{ol(0, out)}"
    return f"font:800 {px(66)}px/1 'Inter Tight',sans-serif;color:{txt};{ol(0, out)}"
