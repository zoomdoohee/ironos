#!/usr/bin/env python3
"""Prepare Thai translation/font tables for IronOS.

IronOS advances one fixed-width cell for every Unicode code point. Thai vowels
and tone marks are combining characters, so rendering them as independent
symbols produces unreadable text. This script rewrites Thai grapheme clusters
(base + combining marks) to private-use single symbols and generates a bitmap
for each cluster by overlaying compact marks on the base glyph.
"""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent

# Thai combining signs that must share the previous consonant cell.
COMBINING = set("ัิีึืฺุู็่้๊๋์ํ๎")
PUA_START = 0xE000


def walk_strings(obj, fn):
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [walk_strings(v, fn) for v in obj]
    if isinstance(obj, dict):
        return {k: walk_strings(v, fn) for k, v in obj.items()}
    return obj


def collect_clusters(s):
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        # Thai consonants / independent letters can carry combining marks.
        if "\u0e01" <= ch <= "\u0e2e":
            j = i + 1
            while j < len(s) and s[j] in COMBINING:
                j += 1
            if j > i + 1:
                out.append(s[i:j])
            i = j
        else:
            i += 1
    return out


def make_cluster_map(data):
    clusters = set()

    def scan(s):
        clusters.update(collect_clusters(s))
        return s

    walk_strings(data, scan)
    return {cluster: chr(PUA_START + n) for n, cluster in enumerate(sorted(clusters))}


def replace_clusters(s, cmap):
    # Left-to-right cluster replacement. Newline and ASCII remain untouched.
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if "\u0e01" <= ch <= "\u0e2e":
            j = i + 1
            while j < len(s) and s[j] in COMBINING:
                j += 1
            cluster = s[i:j]
            out.append(cmap.get(cluster, cluster))
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def bytes_to_grid(data, width, height):
    grid = [[0 for _ in range(width)] for _ in range(height)]
    blocks = height // 8
    for block in range(blocks):
        for x in range(width):
            b = data[block * width + x]
            for r in range(8):
                if b & (1 << r):
                    grid[block * 8 + r][x] = 1
    return grid


def grid_to_bytes(grid, width, height):
    out = bytearray()
    for block in range(height // 8):
        for x in range(width):
            b = 0
            for r in range(8):
                if grid[block * 8 + r][x]:
                    b |= 1 << r
            out.append(b)
    return bytes(out)


def px(g, x, y):
    if 0 <= y < len(g) and 0 <= x < len(g[0]):
        g[y][x] = 1


def draw_mark(g, mark, width, height, has_upper_vowel=False):
    """Draw compact Thai marks inside the same cell as the consonant.

    The shapes are intentionally pixel-simple for the TS100 OLED. Tone marks
    are lifted above upper vowels when both occur in the same cluster.
    """
    large = width >= 10
    cx = width // 2

    if large:
        vowel_y = 2
        tone_y = 0 if has_upper_vowel else 1
        bottom_y = height - 2
        if mark == "ั":
            for x in range(cx - 2, cx + 2): px(g, x, vowel_y)
            px(g, cx + 2, vowel_y + 1)
        elif mark == "ิ":
            for x in range(cx - 2, cx + 2): px(g, x, vowel_y)
        elif mark == "ี":
            for x in range(cx - 2, cx + 2): px(g, x, vowel_y)
            px(g, cx + 2, vowel_y - 1); px(g, cx + 2, vowel_y)
        elif mark == "ึ":
            for x in range(cx - 2, cx + 1): px(g, x, vowel_y)
            px(g, cx + 2, vowel_y); px(g, cx + 2, vowel_y - 1); px(g, cx + 1, vowel_y - 1)
        elif mark == "ื":
            for x in range(cx - 2, cx + 2): px(g, x, vowel_y)
            px(g, cx + 1, vowel_y - 1); px(g, cx + 3, vowel_y - 1)
        elif mark == "็":
            px(g, cx - 2, tone_y + 1); px(g, cx - 1, tone_y); px(g, cx, tone_y + 1)
            px(g, cx + 1, tone_y); px(g, cx + 2, tone_y + 1)
        elif mark == "่":
            px(g, cx, tone_y); px(g, cx, tone_y + 1)
        elif mark == "้":
            px(g, cx - 1, tone_y + 1); px(g, cx, tone_y); px(g, cx + 1, tone_y + 1); px(g, cx + 2, tone_y)
        elif mark == "๊":
            px(g, cx, tone_y); px(g, cx - 1, tone_y + 1); px(g, cx + 1, tone_y + 1); px(g, cx, tone_y + 2)
        elif mark == "๋":
            px(g, cx, tone_y); px(g, cx, tone_y + 2); px(g, cx - 1, tone_y + 1); px(g, cx + 1, tone_y + 1)
        elif mark == "์":
            for x in range(cx - 2, cx + 2): px(g, x, tone_y)
            px(g, cx - 2, tone_y + 1); px(g, cx + 1, tone_y + 1)
        elif mark == "ํ":
            px(g, cx, tone_y); px(g, cx - 1, tone_y + 1); px(g, cx + 1, tone_y + 1); px(g, cx, tone_y + 2)
        elif mark == "๎":
            px(g, cx - 1, tone_y); px(g, cx + 1, tone_y); px(g, cx, tone_y + 1)
        elif mark == "ุ":
            px(g, cx, bottom_y); px(g, cx, bottom_y + 1); px(g, cx + 1, bottom_y + 1)
        elif mark == "ู":
            px(g, cx - 1, bottom_y); px(g, cx - 1, bottom_y + 1)
            px(g, cx + 1, bottom_y); px(g, cx + 1, bottom_y + 1)
        elif mark == "ฺ":
            px(g, cx, height - 1)
    else:
        # 6x8 font: keep marks to one/two pixels so the base stays legible.
        vowel_y = 0
        tone_y = 0
        if mark in "ัิ":
            px(g, cx - 1, vowel_y); px(g, cx, vowel_y)
        elif mark in "ีึื":
            px(g, cx - 1, vowel_y); px(g, cx, vowel_y); px(g, cx + 1, vowel_y)
        elif mark in "็่้๊๋์ํ๎":
            px(g, cx, tone_y)
            if mark in "้๊๋์": px(g, cx + 1, tone_y)
        elif mark == "ุ":
            px(g, cx, height - 1)
        elif mark == "ู":
            px(g, cx - 1, height - 1); px(g, cx + 1, height - 1)
        elif mark == "ฺ":
            px(g, cx, height - 1)


def compose(base_bytes, marks, width, height):
    g = bytes_to_grid(base_bytes, width, height)
    has_upper = any(m in "ัิีึื" for m in marks)
    for m in marks:
        draw_mark(g, m, width, height, has_upper_vowel=has_upper)
    return grid_to_bytes(g, width, height)


# 1) Rewrite Thai strings to one private-use symbol per grapheme cluster.
translation_path = HERE / "translation_TH.json"
data = json.loads(translation_path.read_text(encoding="utf-8"))
cluster_map = make_cluster_map(data)
data = walk_strings(data, lambda s: replace_clusters(s, cluster_map))
translation_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 2) Generate a temporary merged font module containing the PUA glyphs.
from thai_font import get_font_map_thai as base_large, get_small_font_map_thai as base_small

large = base_large()
small = base_small()
for cluster, pua in cluster_map.items():
    base = cluster[0]
    marks = cluster[1:]
    if base in large:
        large[pua] = compose(large[base], marks, 12, 16)
    if base in small:
        small[pua] = compose(small[base], marks, 6, 8)


def dict_source(name, mapping):
    lines = [f"def {name}():", "    return {"]
    for ch, blob in mapping.items():
        lines.append(f"        {ch!r}: bytes.fromhex({blob.hex()!r}),")
    lines += ["    }", ""]
    return "\n".join(lines)

module = (
    '"""Generated Thai font map with precomposed grapheme clusters."""\n'
    'from typing import Dict\n\n'
    + dict_source("get_font_map_thai", large)
    + dict_source("get_small_font_map_thai", small)
)
(HERE / "thai_composed_font.py").write_text(module, encoding="utf-8")

# 3) Patch font_tables.py to expose the generated Thai font maps.
path = HERE / "font_tables.py"
text = path.read_text(encoding="utf-8")

if "from thai_composed_font import get_font_map_thai" not in text:
    text = text.replace(
        "from typing import Dict, Final, Tuple\n",
        "from typing import Dict, Final, Tuple\nfrom thai_composed_font import get_font_map_thai, get_small_font_map_thai\n",
        1,
    )

if 'NAME_THAI: Final = "thai"' not in text:
    text = text.replace(
        'NAME_GREEK: Final = "greek"\n',
        'NAME_GREEK: Final = "greek"\nNAME_THAI: Final = "thai"\n',
        1,
    )

if "    NAME_THAI,\n    NAME_CJK" not in text:
    text = text.replace(
        "    NAME_GREEK,\n    NAME_CJK,  # CJK must come last\n",
        "    NAME_GREEK,\n    NAME_THAI,\n    NAME_CJK,  # CJK must come last\n",
        1,
    )

marker = "ALL_PRE_RENDERED_FONTS = [\n"
start = text.find(marker)
if start != -1:
    end = text.find("]\n", start)
    block = text[start:end]
    if "NAME_THAI" not in block:
        text = text[:end] + "    NAME_THAI,\n" + text[end:]

if "elif font_name == NAME_THAI:" not in text:
    text = text.replace(
        "    elif font_name == NAME_GREEK:\n        return get_font_map_greek(), get_small_font_map_greek()\n",
        "    elif font_name == NAME_GREEK:\n        return get_font_map_greek(), get_small_font_map_greek()\n"
        "    elif font_name == NAME_THAI:\n        return get_font_map_thai(), get_small_font_map_thai()\n",
        1,
    )

path.write_text(text, encoding="utf-8")
print(f"Thai font tables enabled; precomposed {len(cluster_map)} grapheme clusters")
