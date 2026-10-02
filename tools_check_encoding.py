# -*- coding: utf-8 -*-
"""KODIROVKA TEKSHIRUVCHISI - "mojibake" ni oldindan hal qilish.

Platforma bo'ylab barcha matn fayllarini tekshiradi va quyidagi
muammolarni topadi:

  [1] UTF-8 BOM (EF BB BF)          - keraksiz, ba'zi servrlar buzadi
  [2] UTF-8 decode xatosi            - fayl butunlay noto'g'ri kodirovkada
  [3] MOJIBAKE (double-encoding)     - UTF-8 -> CP1251/Latin-1 -> UTF-8
  [4] U+FFFD (replacement char)      - belgi butunlay yo'qolgan

Ishlatish:
    python tools_check_encoding.py           # xato topilsa kod 1
    python tools_check_encoding.py --fix     # avtomatik tuzatadi

CI / test-suite ga ulash uchun `check_all()` funksiyasidan foydalaning.
"""
import argparse
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools_fix_encoding import (ROOT, segments, find_mojibake,       # noqa: E402
                                process as _fix_process, SKIP_DIRS)

# ------------------------------------------------------------------ qamrov

TEXT_DIRS = ['app', 'web', 'tests', 'bot']
TEXT_EXT = {'.py', '.js', '.css', '.html', '.md', '.txt', '.sql',
            '.json', '.yml', '.yaml', '.example', '.csv'}
TEXT_FILES = {'.env.example', '.editorconfig', '.gitattributes',
              '.gitignore', 'server.py', 'README.md'}
EXTRA_EXTS = {'.example'}          # .env.example kabi

SKIP_DIRS = SKIP_DIRS | {'.git', 'node_modules', '.venv', 'venv',
                         'backups', 'shots', 'logs'}
BINARY_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.pdf',
              '.zip', '.gz', '.db', '.sqlite', '.sqlite3', '.xlsx', '.woff',
              '.woff2', '.ttf', '.eot'}

# JS fayllari uchun segmentlarga bo'lib tekshiriladi (string/template),
# qolganlari butun fayl bo'yicha tekshiriladi.
SEGMENTED_EXT = {'.js', '.css'}


def iter_text_files():
    for base in TEXT_DIRS + ['']:
        root = os.path.join(ROOT, base) if base else ROOT
        if not os.path.isdir(root):
            continue
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith('.')]
            for name in sorted(fn):
                full = os.path.join(dp, name)
                ext = os.path.splitext(name)[1].lower()
                if ext in BINARY_EXT or ext == '.bak':
                    continue
                if ext not in TEXT_EXT and name not in TEXT_FILES:
                    continue
                # base='' da yuqoridagi kataloglar qayta sanalmaydi
                rel = os.path.relpath(full, ROOT)
                if base == '' and rel.split(os.sep)[0] in TEXT_DIRS:
                    continue
                yield full


def scan_file(path):
    """(rel, [xatolar]) qaytaradi. xatolar: (kod, qator, tavsif)."""
    rel = os.path.relpath(path, ROOT).replace('\\', '/')
    problems = []
    raw = open(path, 'rb').read()
    if not raw:
        return rel, problems

    if raw.startswith(b'\xef\xbb\xbf'):
        problems.append(('BOM', 0, 'UTF-8 BOM bor (olib tashlanishi kerak)'))

    # UTF-16 BOM larni aniqlash
    if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
        problems.append(('UTF16', 0, 'UTF-16 fayl - UTF-8 ga o\'tkazish kerak'))
        return rel, problems

    try:
        text = raw[3:] if raw.startswith(b'\xef\xbb\xbf') else raw
        text = text.decode('utf-8')
    except UnicodeDecodeError as e:
        problems.append(('UTF8', 0, 'UTF-8 emas: %s' % e))
        return rel, problems

    ext = os.path.splitext(path)[1].lower()
    if ext in SEGMENTED_EXT:
        try:
            segs = segments(text)
        except AssertionError as e:
            problems.append(('SEG', 0, 'JS segmentlash xatosi: %s' % e))
            segs = []
        parts = [(text[s:e], kind) for kind, s, e in segs] or [(text, 'code')]
    else:
        parts = [(text, 'code')]

    # offset -> qator
    starts = [0]
    for ln in text.split('\n')[:-1]:
        starts.append(starts[-1] + len(ln) + 1)

    def line_of(off):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    for chunk, kind in parts:
        base = text.index(chunk, 0) if len(parts) > 1 else 0
        for rs, _re, _fx in find_mojibake(chunk):
            problems.append(('MOJIBAKE', line_of(base + rs),
                             _preview(chunk[rs:_re])))
        for m in _REPL.finditer(chunk):
            problems.append(('FFFD', line_of(base + m.start()),
                             _preview(chunk[m.start():m.start() + 8])))
    return rel, problems


import re                                             # noqa: E402
_REPL = re.compile('\\ufffd')


def _preview(s, n=40):
    s = s.strip()
    if len(s) > n:
        s = s[:n] + '...'
    return s.encode('unicode_escape').decode('ascii')


# ------------------------------------------------------------------ API


def check_all():
    """{rel: [xatolar]} - bo'sh dict = hammasi toza."""
    out = {}
    for full in iter_text_files():
        rel, problems = scan_file(full)
        if problems:
            out[rel] = problems
    return out


def fix_all():
    """BOM va mojibakeni avtomatik tuzatadi (tools_fix_encoding orqali)."""
    n = 0
    for full in iter_text_files():
        ext = os.path.splitext(full)[1].lower()
        _rel, problems = scan_file(full)
        if not problems:
            continue
        if any(code == 'UTF8' or code == 'UTF16' for _c, _l, _d in problems):
            continue                      # qo'lda tuzatish kerak
        r = _fix_process(full, apply=True,
                         do_escape=(ext in SEGMENTED_EXT))
        if r['changed']:
            n += 1
            print('  tuzatildi: %s' % os.path.relpath(full, ROOT))
    return n


# ------------------------------------------------------------------ CLI

CODES = {'BOM': 'UTF-8 BOM', 'UTF16': 'UTF-16', 'UTF8': 'UTF-8 xato',
         'MOJIBAKE': 'MOJIBAKE (double-encoding)', 'FFFD': 'yo\'qolgan belgi',
         'SEG': 'JS segmentlash'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fix', action='store_true')
    args = ap.parse_args()

    if args.fix:
        n = fix_all()
        print('Tuzatilgan fayllar: %d' % n)
        return 0

    bad = check_all()
    total = sum(len(v) for v in bad.values())
    if not bad:
        print('KODIROVKA TOZA: barcha fayllar UTF-8, BOM yo\'q, mojibake yo\'q.')
        return 0

    print('MUAMMOLAR: %d fayl, %d ta\n' % (len(bad), total))
    for rel in sorted(bad):
        print('=== %s ===' % rel)
        for code, line, desc in bad[rel][:12]:
            print('   [%s] %s: %s' % (CODES.get(code, code),
                                      ('qator %d' % line) if line else '-', desc))
        if len(bad[rel]) > 12:
            print('   ... yana %d' % (len(bad[rel]) - 12))
        print()
    print('TUZATISH: python tools_check_encoding.py --fix')
    return 1


if __name__ == '__main__':
    sys.exit(main())