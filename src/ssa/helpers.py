seed = 37
last_color = seed

colors = {}

def color_label(l: str) -> str:
    global last_color
    if colors.get(l) is None:
        r = hex((last_color + 170) % 256)[2:]
        g = hex((last_color + 85) % 256)[2:]
        b = hex(last_color % 256)[2:]
        
        if len(r) == 1:
            r = "0" + r
        if len(b) == 1:
            b = "0" + b
        if len(g) == 1:
            g = "0" + g
        
        colors[l] = f"#{r}{g}{b}"

        last_color += seed

    return f'<B><font color="{colors[l]}">{l}</font></B>'
