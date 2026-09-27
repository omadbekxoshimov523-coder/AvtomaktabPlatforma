#!/usr/bin/env python3
"""GitHub Actions workflow faylini tekshiruvchi (faqat Python standart kutubxonasi).

Nima uchun kerak: GitHub Actions'da noto'g'ri `if:` yoki `run:` yozilsa,
butun workflow parse qilinmaydi va CI "0 soniyada, 0 job bilan" xato bilan
tugaydi — sababni faqat GitHub UI'da ko'rish mumkin. Shu skript ikkala
klassadagi xatoni PUSH'dan OLDIN ushlab beradi.

Tekshiriladigan 3 qoida:
  1) `if:` shartida `secrets` ishlatilmasin.
     GitHub'da `if` uchun ruxsatli kontekstlar: github, needs, vars, inputs,
     steps, job, runner, env, strategy, matrix. `secrets` — YO'Q. Ishlatilsa
     "Unrecognized named-value: 'secrets'" xatosi chiqadi.
     Yechim: `secrets` ni `env:` orqali step ichiga o'kib, bo'shligi
     shu yerda tekshiriladi.
  2) Bir qatorli `run:` qiymatida `: ` (ikki nuqta + bo'sh joy) bo'lmasin.
     YAML uni mapping boshlanishi deb o'qib, sintaksis xatosi beradi.
     Yechim: `run: |` (block scalar) ishlatish.
  3) `run:`/`env:` qiymatlarida bo'sh joy bilan kengaytirilgan bo'yin
     qat'iy qoidasi buzilmasin (zaruriy emas, lekin aniqlik uchun).

Chiqish kodi: 0 — hammasi joyida, 1 — xato topildi.
Ishga tushirish:  python tools_workflow_check.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# `if` shartida ruxsatli kontekstlar (GitHub Actions hujjati bo'yicha)
ALLOWED_IF_CONTEXTS = {
    "github", "needs", "vars", "inputs", "steps", "job", "runner",
    "env", "strategy", "matrix", "always", "success", "failure",
    "cancelled", "hashFiles",
}

IF_RE = re.compile(r"^\s*(?:-\s+)?if:\s*(.+?)\s*$")
SECRET_IN_EXPR_RE = re.compile(r"secrets\.")


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def check_workflow(path: Path) -> list[str]:
    problems: list[str] = []

    if not path.is_file():
        return [f"{path}: fayl topilmadi"]

    raw = path.read_bytes()
    if b"\t" in raw:
        problems.append(f"{path}: TAB belgisi bor (YAML'da ishlatilmaydi)")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"{path}: UTF-8 emas ({exc})"]

    in_block = False           # `run: |` / `script: |` ichidamiz
    block_indent = 0

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))

        # `|` bilan ko'p qatorli qiymat ichidamiz — qoidalar qo'llanilmaydi
        if in_block:
            if stripped and indent <= block_indent:
                in_block = False
            else:
                continue
        elif stripped.endswith("|") or stripped.endswith(">"):
            in_block = True
            block_indent = indent
            continue

        # --- 1) if: shartida secrets
        m = IF_RE.match(line)
        if m and SECRET_IN_EXPR_RE.search(m.group(1)):
            problems.append(
                f"{path}:{lineno}: `if:` shartida `secrets.` ishlatilgan — "
                f"GitHub buni qabul qilmaydi. `env:` orqali step ichiga o'kib, "
                f"bo'shligi shu yerda tekshiring."
            )

        # --- 2) bir qatorli run: ichida ": "
        m2 = re.match(r"^\s*(?:-\s+)?run:\s*(.+?)\s*$", line)
        if m2:
            value = _strip_quotes(m2.group(1))
            # "${{ ... }}" ichidagi ":" ni hisobga olmaymiz
            probe = re.sub(r"\$\{\{.*?\}\}", "", value)
            if ": " in probe or probe.rstrip().endswith(":"):
                problems.append(
                    f"{path}:{lineno}: bir qatorli `run:` ichida ': ' bor — "
                    f"YAML mapping deb o'qib, workflow'ni buzadi. "
                    f"`run: |` (keyingi qatorga chiqib yozing) ishlating."
                )

    return problems


def main() -> int:
    root = Path(__file__).resolve().parent
    workflow_dir = root / ".github" / "workflows"
    files = sorted(workflow_dir.glob("*.y*ml")) if workflow_dir.is_dir() else []

    if not files:
        print("HABAR: .github/workflows da fayl yo'q — tekshiruv o'tkazildi")
        return 0

    all_problems: list[str] = []
    for f in files:
        found = check_workflow(f)
        name = f.name
        if found:
            all_problems.extend(found)
            print(f"XATO  {name}: {len(found)} muammo")
        else:
            print(f"OK    {name}")

    if all_problems:
        print("\n--- tafsilotlar ---")
        for p in all_problems:
            print(" *", p)
        print(f"\nMUAMMO: {len(all_problems)} ta xato. Push'dan oldan tuzating.")
        return 1

    print(f"\nBarcha workflow fayllari to'g'ri ({len(files)} ta).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
