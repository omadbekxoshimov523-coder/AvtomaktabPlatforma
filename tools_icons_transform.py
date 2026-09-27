#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Emoji -> SVG ikonka transformatsiyasi (Task 1, mexanik qismi).
ICONS registri (ui.js) bilan bog'langan `ICONS` nomlari yordamida
JS fayllardagi `text: "<emoji> " + X` naqshlarini
`icon: "nomi", text: X` ko'rinishiga o'tkazadi.

Foydalanish:
  py tools_icons_transform.py --apply        # o'zgartirishni qo'llash
  py tools_icons_transform.py                # quruq (dry-run) hisobot
  py tools_icons_transform.py --file web\\js\\views-admin.js --apply

Xavfsizlik: faqat registrda bor ikonka nomiga xaritalangan emoji almashtiriladi;
  registrsiz emojilar hisobotda qoldiriladi (buzilish xavfsiz).
"""
import argparse
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------- Ikonka nomlari (ui.js ICONS kalitlari) --------------
# Ushbu ro'yxat ui.js:9-66 dagi ICONS kalitlariga mos. Yangi ikonka qo'shilsa shu yerga qo'shing.
ICON_NAMES = {
    "home", "dashboard", "calendar", "lessons", "users", "user", "student",
    "instructor", "shield", "bell", "settings", "logout", "plus", "minus",
    "x", "check", "check_circle", "alert", "alert_circle", "info",
    "file", "file_text", "download", "upload", "edit", "trash", "search",
    "filter", "refresh", "phone", "mail", "map", "clock", "book", "key",
    "lock", "eye", "copy", "tools", "car", "undo", "camera", "save",
    "menu", "message", "play", "pause", "chart", "graduation", "star",
    "wallet", "checkup", "warn", "arrow_left", "arrow_right", "dot",
}

# emoji -> ikonka nomi (faqat ishonchli 1:1 xaritalar)
EMOJI2ICON = {
    "🏠": "home",
    "📊": "chart",
    "📅": "calendar",
    "📚": "book",
    "👥": "users",
    "👤": "user",
    "🎓": "graduation",
    "🧑‍🏫": "instructor",
    "👨‍🏫": "instructor",
    "🛡️": "shield",
    "🔔": "bell",
    "⚙️": "settings",
    "🔧": "tools",
    "🚪": "logout",
    "⬅️": "arrow_left",
    "➡️": "arrow_right",
    "←": "arrow_left",
    "→": "arrow_right",
    "➕": "plus",
    "➕": "plus",
    "❌": "x",
    "✖️": "x",
    "✅": "check",
    "✔️": "check",
    "📄": "file",
    "📝": "edit",
    "✏️": "edit",
    "🗑️": "trash",
    "🗑": "trash",
    "🔍": "search",
    "📁": "file",
    "💾": "save",
    "📥": "download",
    "📤": "upload",
    "📞": "phone",
    "✉️": "mail",
    "📧": "mail",
    "📍": "map",
    "🗺️": "map",
    "🕐": "clock",
    "🕑": "clock",
    "🕒": "clock",
    "🕓": "clock",
    "🕔": "clock",
    "🕖": "clock",
    "🕗": "clock",
    "⏰": "clock",
    "📖": "book",
    "🔑": "key",
    "🔐": "lock",
    "👁️": "eye",
    "📋": "copy",
    "🚗": "car",
    "🚙": "car",
    "🔴": "checkup",
    "🔵": "info",
    "🟢": "check_circle",
    "🟡": "alert",
    "🟣": "dot",
    "🟠": "alert",
    "📌": "dot",
    "❓": "info",
    "ℹ️": "info",
    "💬": "message",
    "💡": "info",
    "⭐": "star",
    "🖥️": "dashboard",
    "📺": "lessons",
    "🎬": "play",
    "▶️": "play",
    "⏸️": "pause",
    "⏹️": "square",
    "🚦": "checkup",
    "🚕": "car",
    "🚌": "car",
    "🚐": "car",
    "🏫": "graduation",
    "🎯": "check_circle",
    "📈": "chart",
    "📉": "chart",
    "🧮": "dashboard",
    "💳": "wallet",
    "💰": "wallet",
    "🏦": "wallet",
    "💵": "wallet",
    "🪙": "wallet",
    "🧾": "file_text",
    "🗒️": "file_text",
    "📑": "file_text",
    "📜": "file",
    "🖊️": "edit",
    "✍️": "edit",
    "🎫": "file",
    "🗂️": "file",
    "📂": "file",
    "📦": "download",
    "🧠": "info",
    "🔬": "search",
    "🖼️": "camera",
    "📷": "camera",
    "🎥": "camera",
    "📹": "camera",
    "🎦": "camera",
    "📱": "phone",
    "🖨️": "copy",
    "🔊": "bell",
    "🔕": "bell",
    "🚨": "alert",
    "⚠️": "alert",
    "❗": "alert",
    "⛔": "x",
    "🚫": "x",
    "🔒": "lock",
    "🕹️": "play",
    "⏫": "upload",
    "⏬": "download",
    "🔎": "search",
    "📆": "calendar",
    "🗓️": "calendar",
    "📊": "chart",
}

# Unicode emoji blok (ko'p kodepoint emojilarni izlash uchun)
EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # har xil emoji bloklari
    "\U00002600-\U000027BF"  # matematik operatorlar / Dingbats (⚠⭐)
    "\U00002B00-\U00002BFF"  # strelkalar (➡)
    "\U0000FE0F\U0000200D"   # variatsiya / ZWJ belgilari (ichki)
    "]+"
)

# har bir emoji (shu jumladan ko'p baytli) tarkibini ...
# `text: "emoji " + X` va `icon:"..."` naqshlarini aniqlash
PAT_TEXT_PREFIX = re.compile(r'(\btext:\s*")([^"]*?)("\s*\+\s*)([^,}\]]+)')
PAT_ICON_ATTR = re.compile(r'\bicon:\s*"([a-z0-9_]+)"')


def scan_line(line):
    """Qatordagi emojilarni aniqlab, har birining ichiga qaytadi."""
    found = []
    for m in EMOJI_RE.finditer(line):
        found.append(m.group(0))
    return found


def replace_text_prefix(line, counts, report):
    """`text: "E " + X` -> `icon: "n", text: X` transform."""
    def _rep(m):
        prefix, emoji, sep, expr = m.group(1), m.group(2), m.group(3), m.group(4)
        # emoji qismini ikonka nomiga qidiramiz
        matched = None
        for e in EMOJI2ICON:
            if e in emoji:
                matched = e
                break
        if matched and EMOJI2ICON[matched] in ICON_NAMES:
            name = EMOJI2ICON[matched]
            # qolgan emoji tarkibini (variatsiya/ZWJ) o'chirib, bo'shliqni saqlaymiz
            rest = emoji.replace(matched, "").strip(" \uFE0F\u200D")
            suffix = (" " + rest) if rest else ""
            counts["ok"] += 1
            report[name] = report.get(name, 0) + 1
            # faqat bo'sh bo'lmagan emoji prefixi bo'lsa almashtiramiz
            return f'icon: "{name}", {prefix}{suffix}' + sep + expr
        counts["skip"] += 1
        return m.group(0)
    return PAT_TEXT_PREFIX.sub(_rep, line)


def process_file(path, apply):
    """Faylni o'qiydi, satr-satr transform qiladi, hisobot qaytaradi."""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    counts = {"ok": 0, "skip": 0, "emoji_left": 0}
    report = {}
    out = []
    for line in lines:
        if apply:
            new = replace_text_prefix(line, counts, report)
            out.append(new)
        else:
            # dry-run: faqat hisob
            replace_text_prefix(line, counts, report)
            out.append(line)
    emoji_left = sum(len(scan_line(l)) for l in "".join(out) if l)
    counts["emoji_left"] = len(EMOJI_RE.findall("".join(out)))
    if apply:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.writelines(out)
    return counts, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--file", default=None, help="Faqat bir faylni qayta ishlash")
    ap.add_argument("--report-only", action="store_true", help="Faqat hisobot")
    a = ap.parse_args()

    target = "web/js"
    if a.file:
        files = [os.path.join(ROOT, a.file)]
    else:
        jsdir = os.path.join(ROOT, target)
        files = sorted(
            os.path.join(jsdir, f) for f in os.listdir(jsdir) if f.endswith(".js")
        )

    print(f"{'QIYIN TRANSFORM' if a.apply else 'QURUQ (dry-run) hisobot'}")
    print("=" * 60)
    grand_ok = grand_skip = grand_left = 0
    for f in files:
        if not os.path.exists(f):
            continue
        counts, report = process_file(f, a.apply)
        mode = "O'ZGARTIRILDI" if a.apply else "hist"
        print(f"  {os.path.basename(f):22s} ok={counts['ok']:4d}  skip={counts['skip']:3d}  emoji_qoldi={counts['emoji_left']:3d}")
        grand_ok += counts["ok"]
        grand_skip += counts["skip"]
        grand_left += counts["emoji_left"]
    print("=" * 60)
    print(f"JAMI: almashtirildi={grand_ok}  skip={grand_skip}  qolgan_emoji={grand_left}")
    if not a.apply and grand_ok:
        print("\n`--apply` bilan qo'llang. Keyin: py tools_js_check.py va py tools_qa_i18n.py")


if __name__ == "__main__":
    main()
