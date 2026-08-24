#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).with_name("font_tables.py")
text = path.read_text(encoding="utf-8")

if "from thai_font import get_font_map_thai" not in text:
    text = text.replace(
        "from typing import Dict, Final, Tuple\n",
        "from typing import Dict, Final, Tuple\nfrom thai_font import get_font_map_thai, get_small_font_map_thai\n",
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
print("Thai font tables enabled")
