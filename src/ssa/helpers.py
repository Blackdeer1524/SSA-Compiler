def color_label(l: str) -> str:
    h = hash(l)
    b = hex(h % 16)[2:]
    h //= 16

    g = hex(h % 16)[2:]
    h //= 16

    r = hex(h % 16)[2:]

    if len(r) == 1:
        r = r + "F"
    if len(b) == 1:
        b = b + "F"
    if len(g) == 1:
        g = g + "F"
    return f'<B><font color="#{r}{g}{b}">{l}</font></B>'
