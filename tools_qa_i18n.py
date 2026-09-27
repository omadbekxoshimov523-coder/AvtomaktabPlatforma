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

# 2) barcha t("...") chaqiruvlari
used = {}
for f in WEB.glob("*.js"):
    src = f.read_text(encoding="utf-8")
    for m in re.finditer(r"\bt\(\"([a-z][a-z0-9_.]*)\"\)", src):
        used.setdefault(m.group(1), set()).add(f.name)

missing = sorted(k for k in used if k not in keys)
print("=== I18N KALITLARI ===")
print("Lug'atda:", len(keys), "| Ishlatilgan:", len(used), "| Yo'qotilgan:", len(missing))
for k in missing:
    print("  YO'Q:", k, "<-", sorted(used[k]))

# 3) sintaksis sniffer: bo'sh-string shorthand, qavs/braces balansi
print("\n=== SINTAKSIS SNIFFER ===")
bad = 0
for f in WEB.glob("*.js"):
    src = f.read_text(encoding="utf-8")
    # bo'sh-string shorthand
    for i, line in enumerate(src.splitlines(), 1):
        if re.search(r'\{\s*""\s*[,}]', line):
            print(f"  [{f.name}:{i}] bo'sh-string shorthand: {line.strip()}")
            bad += 1
    # izohlar va stringlarni olib tashlash
    clean = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    clean = re.sub(r"//[^\n]*", "", clean)
    clean = re.sub(r"`(?:[^`\\]|\\.)*`", '""', clean, flags=re.S)
    clean = re.sub(r'"(?:[^"\\]|\\.)*"', '""', clean)
    clean = re.sub(r"'(?:[^'\\]|\\.)*'", '""', clean)
    for op, cl in [("{", "}"), ("(", ")"), ("[", "]"), ("<", ">")]:
        if clean.count(op) != clean.count(cl) and op != "<":
            print(f"  [{f.name}] balans: {op}={clean.count(op)} {cl}={clean.count(cl)}")
            bad += 1
print("Jami muammo:", bad)