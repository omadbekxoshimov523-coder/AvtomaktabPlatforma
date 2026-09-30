# -*- coding: utf-8 -*-
"""Mini JS lexer + bracket/shorthand validator (no node needed).
Detects: unbalanced (), [], {}; and object-literal shorthand with empty-string key `{ "" }`
which is a SyntaxError in every JS engine.
"""
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web" / "js"

EXPR_KEYS = {"(", "[", "{", ",", ";", ":", "=", "!", "?", "&", "|", "+", "-", "*", "%", "<", ">", "^", "~", "=>", "return", "case", "in", "of", "typeof", "void", "delete", "new", "do", "else", "yield", "await"}


def tokenize(src):
    toks = []  # (line, kind, value)
    i, n, line = 0, len(src), 1
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        # comments
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0:
                toks.append((line, "ERR", "unterminated block comment"))
                return toks
            i = j + 2
            continue
        # strings
        if c in "\"'":
            q = c
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "\n":
                    toks.append((line, "ERR", "unterminated string"))
                    return toks
                if src[j] == q:
                    break
                j += 1
            if j >= n:
                toks.append((line, "ERR", "unterminated string"))
                return toks
            toks.append((line, "STR", src[i:j + 1]))
            i = j + 1
            continue
        # template literal with nested ${}
        if c == "`":
            j = i + 1
            depth = 0
            while j < n:
                ch = src[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "`":
                    if depth == 0:
                        break
                    j += 1
                    continue
                if src.startswith("${", j):
                    depth += 1
                    j += 2
                    continue
                if ch == "}" and depth > 0:
                    depth -= 1
                    j += 1
                    continue
                if ch == '"':
                    j2 = j + 1
                    while j2 < n and src[j2] != '"' and src[j2] != "\\":
                        j2 += 1
                    j = j2 + 1
                    continue
                if ch == "'":
                    j2 = j + 1
                    while j2 < n and src[j2] != "'" and src[j2] != "\\":
                        j2 += 1
                    j = j2 + 1
                    continue
                j += 1
            if j >= n:
                toks.append((line, "ERR", "unterminated template"))
                return toks
            toks.append((line, "TPL", src[i:j + 1]))
            i = j + 1
            continue
        # regex literal: /.../ when previous token suggests expression position
        if c == "/" and not src.startswith("//", i) and not src.startswith("/*", i):
            prev = toks[-1][1] if toks else None
            prevv = toks[-1][2] if toks else ""
            regex_ok = (
                prev is None
                or prev in ("OPEN", "SEP", "OP", "KEYWORD")
                or (prev == "IDENT" and prevv in ("return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "case", "do", "else", "yield", "await"))
            )
            if regex_ok:
                j = i + 1
                cls = False
                while j < n:
                    ch = src[j]
                    if ch == "\\":
                        j += 2
                        continue
                    if ch == "[":
                        cls = True
                    elif ch == "]":
                        cls = False
                    elif ch == "/" and not cls:
                        break
                    elif ch == "\n":
                        break
                    j += 1
                if j < n and src[j] == "/":
                    j += 1
                    while j < n and src[j].isalpha():
                        j += 1
                    toks.append((line, "REGEX", src[i:j]))
                    i = j
                    continue
        # numbers
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            j = i
            while j < n and (src[j].isalnum() or src[j] in "._"):
                j += 1
            toks.append((line, "NUM", src[i:j]))
            i = j
            continue
        # identifiers / keywords
        if c.isalpha() or c == "_" or c == "$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            word = src[i:j]
            kw = word in ("return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "case", "do", "else", "yield", "await", "if", "for", "while", "switch", "function", "var", "let", "const", "async")
            toks.append((line, "KEYWORD" if kw else "IDENT", word))
            i = j
            continue
        # operators / punctuation
        two = src[i:i + 2]
        if two in ("=>", "==", "===", "!=", "!==", "<=", ">=", "&&", "||", "++", "--", "+=", "-=", "*=", "/=", "**", "??", "?."):
            toks.append((line, "OP2", two))
            i += 2
            continue
        if c in "()[]{}":
            toks.append((line, "OPEN" if c in "([{" else "CLOSE", c))
        elif c == ",":
            toks.append((line, "SEP", c))
        elif c in ";:?=+-*/%!&|<>^~":
            toks.append((line, "OP", c))
        else:
            toks.append((line, "OTHER", c))
        i += 1
    return toks


def validate(src, name):
    toks = tokenize(src)
    errors = []
    for (line, kind, val) in toks:
        if kind == "ERR":
            errors.append(f"{name}:{line}: {val}")
    # bracket balance
    stack = []  # (char, line)
    pairs = {"(": ")", "[": "]", "{": "}"}
    for (line, kind, val) in toks:
        if kind == "OPEN":
            stack.append((val, line))
        elif kind == "CLOSE":
            if not stack:
                errors.append(f"{name}:{line}: closing '{val}' without opener")
            else:
                op, oline = stack.pop()
                if pairs[op] != val:
                    errors.append(f"{name}:{line}: '{op}' (opened line {oline}) closed by '{val}'")
    for (val, line) in stack:
        errors.append(f"{name}:{line}: unclosed '{val}'")
    # empty-string shorthand inside object literal
    for idx, (line, kind, val) in enumerate(toks):
        if kind == "STR" and val == '""':
            prev = toks[idx - 1][1] if idx > 0 else None
            prevv = toks[idx - 1][2] if idx > 0 else None
            nxt = toks[idx + 1][1] if idx + 1 < len(toks) else None
            # `{  ""  ,` or `{  ""  }`  => shorthand (illegal)
            if (prev == "OPEN" and prevv == "{") and nxt in ("SEP", "CLOSE"):
                errors.append(f"{name}:{line}: empty-string shorthand {{ \"\" }} - SyntaxError")
            # `""` followed by `,` or `}` where prev token is also `{`? covered above
    return errors


def debug_dump(name, lo, hi):
    src = (WEB / name).read_text(encoding="utf-8")
    for (line, kind, val) in tokenize(src):
        if lo <= line <= hi:
            print(f"  L{line}: {kind:7s} {val[:60]!r}")


def main():
    import sys as _s
    if len(_s.argv) > 2:
        debug_dump(_s.argv[1], int(_s.argv[2]), int(_s.argv[3]))
        return 0
    total = 0
    for f in sorted(WEB.glob("*.js")):
        src = f.read_text(encoding="utf-8")
        errs = validate(src, f.name)
        if errs:
            total += len(errs)
            for e in errs:
                print("  " + e)
        else:
            print(f"  OK  {f.name}")

    # window.X global bog'lanish tekshiruvi:
    # agar fayl `window.UI` ni O'QISA (≈ `const X = window.UI`), kodi biron joyda
    # `window.UI = ...` yozilgan bo'lishi shart. Aks holda brauzerda UI undefined bo'ladi.
    #
    # ISTISNO: tashqi kutubxonalar o'zlari `window.X` ni yozadi (masalan Yandex
    # Maps skripti `window.ymaps` ni yaratadi) — ularni ro'yxatga olamiz,
    # aks holda tekshiruv yolg'on xato beradi.
    EXTERNAL_GLOBALS = {
        "ymaps": "Yandex Maps JS API (web/js/map.js da skript orqali yuklanadi)",
    }
    assigned = set()
    reads = []  # (filename, line, name)

    def scan(f):
        src = f.read_text(encoding="utf-8")
        toks = tokenize(src)
        for i in range(len(toks) - 2):
            t0 = toks[i]
            if t0[1] == "IDENT" and t0[2] == "window" and toks[i + 1][1] == "OTHER" and toks[i + 1][2] == "." and toks[i + 2][1] == "IDENT":
                name = toks[i + 2][2]
                nxt = toks[i + 3][2] if i + 3 < len(toks) else ""
                is_assign = (toks[i + 3][1] == "OP" and nxt == "=") if i + 3 < len(toks) else False
                if is_assign:
                    assigned.add(name)
                else:
                    reads.append((f.name, t0[0], name))

    for f in sorted(WEB.glob("*.js")):
        scan(f)
    for fn, line, name in reads:
        if name not in assigned and name not in EXTERNAL_GLOBALS:
            total += 1
            print(f"  {fn}:{line}: window.{name} o'qilgan, lekin hech bir faylda window.{name} = ... yozilmagan")

    print(f"\nJami xatolar: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())