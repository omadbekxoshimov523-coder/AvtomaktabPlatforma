# -*- coding: utf-8 -*-
"""QA: frontend t() kalitlarini i18n.js lug'atlari bilan solishtirish + sintaksis sniffer."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web" / "js"

# 1) i18n.js da barcha kalitlar
i18n_src = (WEB / "i18n.js").read_text(encoding="utf-8")
keys = set()
for m in re.finditer(r'"([a-z][a-z0-9_.]*)"\s*:', i18n_src):
    keys.add(m.group(1))

# 2) barcha t("...") / txt("...") / errorText("...") chaqiruvlari
#    `map.js` (MODUL 4) `t` emas `txt` yordamchisini ishlatadi, xatolar uchun
#    esa `errorText` — ular ham lug'atda BO'LISHI shart.
used = {}
for f in WEB.glob("*.js"):
    src = f.read_text(encoding="utf-8")
    for m in re.finditer(r"\bt\(\"([a-z][a-z0-9_.]*)\"\)", src):
        used.setdefault(m.group(1), set()).add(f.name)
    for m in re.finditer(r"\btxt\(\"([a-z][a-z0-9_.]*)\"", src):
        used.setdefault(m.group(1), set()).add(f.name)
    # errorText("coord.bad_lat") -> lug'atda "err.coord.bad_lat" bo'lishi SHART
    for m in re.finditer(r"\berrorText\(\"([a-z][a-z0-9_.]*)\"\)", src):
        used.setdefault("err." + m.group(1), set()).add(f.name)

missing = sorted(k for k in used if k not in keys)
print("=== I18N KALITLARI ===")
print("Lug'atda:", len(keys), "| Ishlatilgan:", len(used), "| Yo'qotilgan:", len(missing))
for k in missing:
    print("  YO'Q:", k, "<-", sorted(used[k]))

# 3) sintaksis sniffer: bo'sh-string shorthand + qavs balansi
#    Qavs hisobi uchun `tools_js_check.py` dagi HAQIQIY lexer ishlatiladi
#    (oddiy `str.count()` yondashuvi regex va satrlardagi qavslarni ham
#    sanab, yolg'on xato berardi — masalan "https://" URL'i).
print("\n=== SINTAKSIS SNIFFER ===")
bad = 0
from tools_js_check import tokenize  # noqa: E402

PAIRS = {")": "(", "]": "[", "}": "{"}
OPENERS = set("([{")
for f in sorted(WEB.glob("*.js")):
    src = f.read_text(encoding="utf-8")
    # bo'sh-string shorthand — bu har qanday JS dvigatelida SyntaxError
    for i, line in enumerate(src.splitlines(), 1):
        if re.search(r'\{\s*""\s*[,}]', line):
            print(f"  [{f.name}:{i}] bo'sh-string shorthand: {line.strip()}")
            bad += 1
    stack = []
    for (line, kind, val) in tokenize(src):
        if kind == "ERR":
            print(f"  [{f.name}:{line}] {val}")
            bad += 1
            break
        if kind == "OTHER" and val in OPENERS:
            stack.append((val, line))
        elif kind == "OTHER" and val in PAIRS:
            if not stack or stack[-1][0] != PAIRS[val]:
                print(f"  [{f.name}:{line}] '{val}' yopilishi kutilgan edi: {stack[-1] if stack else 'bo\'sh stek'}")
                bad += 1
                break
            stack.pop()
    else:
        if stack:
            op, ln = stack[-1]
            print(f"  [{f.name}:{ln}] '{op}' yopilmagan (stekda {len(stack)} ta qoldi)")
            bad += 1
print("Jami muammo:", bad)