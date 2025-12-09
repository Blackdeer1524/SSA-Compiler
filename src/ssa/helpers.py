from hashlib import sha256
from typing import Any, Optional


bb_colors = {}


def color_label(l: str) -> str:
    if bb_colors.get(l) is None:
        h = sha256(l.encode()).hexdigest()

        r = h[-2:]
        g = h[0:2]
        b = h[-6:-4]

        if len(r) == 1:
            r = "0" + r
        if len(b) == 1:
            b = "0" + b
        if len(g) == 1:
            g = "0" + g

        bb_colors[l] = f"#{r}{g}{b}"

    return f'<B><font color="{bb_colors[l]}">{l}</font></B>'


def unwrap[T: Any](v: Optional[T]) -> T:
    assert v is not None
    return v
