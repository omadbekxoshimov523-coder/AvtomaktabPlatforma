# -*- coding: utf-8 -*-
r"""JS/CSS aware encoding tuzatuvchi + "escape" vositasi.

IKKI VAZIFA:

1) MOJIBAKE TUZATISH (double-encoding).
   UTF-8 baytlari Windows-1251 (yoki Latin-1) da o'qilib, qayta UTF-8
   sifatida saqlangan matnni tiklaydi:
       "РЯ“€"  ->  "\U0001f4ca"   (📈)
       "вЂ”"   ->  "—"     (em-dash)
       "В·"    ->  "·"     (middle dot)
   Har bir "run" (ketma-ketlik) CP1251 -> UTF-8 orqali qayta ochiladi
   va faqat natija TOZAROQ bo'lsa qabul qilinadi (xato-deteksiya ~0).

2) MOJIBAKE'GA QARSHI HIMOYA (escape).
   JS/CSS matn (string va template literal) ichidagi barcha U+2000+
   belgilar -> Unicode escape'ga o'kaziladi:
       "📈 " -> "\u{1f4ca} "
       "—"   -> "\u2014"
       "·"   -> "\u00b7"
   ASCII lotin va kirill O'QILADI (O'zbekcha/Ruscha tarjimalar
   tahrirlashga qulay bo'lib qoladi), faqat zaif ko'p-baytli
   belgilar (emoji, typografik punktuatsiya) escape bo'ladi.
   Natija: fayl kodirovkasi qanday bo'lmasin, belgilar to'g'ri chiqadi.

Ishlatish:
    python tools_fix_encoding.py            # faqat hisobot (o'zgartirmaydi)
    python tools_fix_encoding.py --apply    # tuzatadi

XAVFSIZLIK: skanner segmentlari o'zaro QATLAMAS (non-overlapping)
bo'lishi majburiy - bu assert orqali tekshiriladi. Aks holda
almashinuv natijasi buziladi.
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- skanner

# `/` regex literal yoki bo'lish ekanini aniqlash uchun
_REGEX_PREV = {
    '(', ',', '=', ':', '[', '!', '&', '|', '?', '{', '}', ';', '+', '-', '*',
    '%', '^', '~', '<', '>', '=>', '&&', '||', '==', '===', '!=', '!==', '??',
    'return', 'case', 'in', 'of', 'typeof', 'void', 'delete', 'new', 'do',
    'else', 'yield', 'await',
}
_RE_IDCHAR = re.compile(r'[A-Za-z0-9_$]')


def _flush(out, a, b):
    if b > a:
        out.append(('code', a, b))


def _scan_quoted(src, i, q):
    """i belgisi q-quote boshlanishi. Yopilgan quote DAN KEYINGI indeks."""
    n = len(src)
    j = i + 1
    while j < n:
        c = src[j]
        if c == '\\':
            j += 2
            continue
        if c == q:
            return j + 1
        if c == '\n':            # JS da satr ichida yangi qator yo'q
            return j
        j += 1
    return n


def _scan_regex(src, i):
    n = len(src)
    j, in_class = i + 1, False
    while j < n:
        ch = src[j]
        if ch == '\\':
            j += 2
            continue
        if ch == '\n':
            return None
        if ch == '[':
            in_class = True
        elif ch == ']':
            in_class = False
        elif ch == '/' and not in_class:
            j += 1
            while j < n and src[j].isalpha():
                j += 1
            return j
        j += 1
    return None


def _scan_template(src, i, n):
    """` belgisidan boshlanuvchi template. Qaytaradi: (keyingi_indeks, segments)."""
    segs = []
    start, i = i, i + 1
    while i < n:
        c = src[i]
        if c == '\\':
            i += 2
            continue
        if c == '`':
            segs.append(('template', start, i + 1))
            return i + 1, segs
        if c == '$' and i + 1 < n and src[i + 1] == '{':
            segs.append(('template', start, i))        # interpolatsiyadan oldingi xom matn
            j = _scan_code(src, i + 2, segs, n, stop_at_brace=True)
            # _scan_code interpolatsiya ichidagi 'code' segmentini o'zi qo'shdi
            start = i = j + 1                          # '}' ni o'tkazib yuboramiz
            continue
        i += 1
    segs.append(('template', start, n))
    return n, segs


def _scan_code(src, i, out, n, stop_at_brace=False):
    """Kodni skanlaydi. `stop_at_brace` True bo'lsa mos '}' da to'xtaydi
    va o'sha '}' indeksini QAYTARADI (segmentga kirmaydi)."""
    code_start, depth, prev = i, 0, None
    while i < n:
        c = src[i]

        if src.startswith('//', i):
            _flush(out, code_start, i)
            j = src.find('\n', i)
            j = n if j < 0 else j
            out.append(('comment', i, j))
            i = code_start = j
            prev = None
            continue
        if src.startswith('/*', i):
            _flush(out, code_start, i)
            j = src.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(('comment', i, j))
            i = code_start = j
            prev = None
            continue
        if c in '"\'':
            _flush(out, code_start, i)
            j = _scan_quoted(src, i, c)
            out.append(('string', i, j))
            i = code_start = j
            prev = 'str'
            continue
        if c == '`':
            _flush(out, code_start, i)
            j, sub = _scan_template(src, i, n)
            out.extend(sub)
            i = code_start = j
            prev = 'str'
            continue
        if c == '/' and (prev is None or prev in _REGEX_PREV):
            j = _scan_regex(src, i)
            if j is not None:
                _flush(out, code_start, i)
                out.append(('regex', i, j))
                i = code_start = j
                prev = 'regex'
                continue
        if c == '{':
            depth += 1
        elif c == '}':
            if stop_at_brace and depth == 0:
                _flush(out, code_start, i)
                return i
            depth -= 1
        if _RE_IDCHAR.match(c):
            j = i
            while j < n and _RE_IDCHAR.match(src[j]):
                j += 1
            prev = src[i:j]
            i = j
            continue
        if c in ' \t\r\n':
            i += 1
            continue
        prev = c
        i += 1
    _flush(out, code_start, n)
    return n


def segments(src):
    """(kind, start, end) ro'yxati: 'code' | 'string' | 'template' |
    'comment' | 'regex'. O'zaro qatlamAS (non-overlapping) KAFOLATLANADI."""
    out = []
    _scan_code(src, 0, out, len(src))
    out.sort(key=lambda s: s[1])
    prev_end = 0
    for kind, s, e in out:
        assert s >= prev_end, ('segmentlar ustma-ust tushdi: %s:%d-%d'
                               % (kind, s, e))
        prev_end = e
    return out


# ---------------------------------------------------------------- mojibake

_CYR = 'Ѐ-ӿ'
_TYPO = '‘’“”–—…'
_C1 = '\x80-\x9f'
BAD_PAIR = re.compile('[%s][%s%s]' % (_CYR, _TYPO, _C1))
BAD_PAIR2 = re.compile('[%s%s][%s]' % (_TYPO, _C1, _CYR))
REPL_CHR = re.compile('\\ufffd')


def _score(s):
    """Yomonlik balli - kichsa, toza matn."""
    sc = 10 * len([c for c in s if '\x80' <= c <= '\x9f'])
    sc += 4 * len(BAD_PAIR.findall(s))
    sc += 4 * len(BAD_PAIR2.findall(s))
    sc += 2 * len(REPL_CHR.findall(s))
    sc += 0.15 * len(re.findall('[%s]' % _CYR, s))
    return sc


def _charset_chars(codec):
    out = set()
    for cp in range(0x100):
        try:
            out.add(bytes([cp]).decode(codec))
        except Exception:
            pass
    return frozenset(out)


CHARSETS = [(_charset_chars('cp1251'), 'cp1251'),
            (_charset_chars('latin-1'), 'latin-1')]


def find_mojibake(text):
    """[(start, end, toza_matn)] - text ichidagi mojibake runlari."""
    hits = []
    for chars, codec in CHARSETS:
        run, start = [], 0
        for idx, ch in enumerate(text):
            if ch in chars:
                if not run:
                    start = idx
                run.append(ch)
            else:
                if len(run) >= 3:
                    _try_run(hits, start, ''.join(run), codec)
                run = []
        if len(run) >= 3:
            _try_run(hits, start, ''.join(run), codec)

    # ustma-ust tushmaslik uchun eng uzunini ushlab qolamiz
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    out, last_end = [], -1
    for s, e, t in hits:
        if s >= last_end:
            out.append((s, e, t))
            last_end = e
    return out


def _try_run(hits, start, piece, codec):
    if len(piece) > 200:                 # juda uzun bo'lsa bo'lib ko'ramiz
        chunks = [(start + i, piece[i:i + 200])
                  for i in range(0, len(piece), 200)]
    else:
        chunks = [(start, piece)]
    for off, chunk in chunks:
        try:
            raw = chunk.encode(codec)
        except Exception:
            continue
        try:
            fixed = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        if fixed != chunk and _score(fixed) < _score(chunk):
            hits.append((off, off + len(chunk), fixed))


# ---------------------------------------------------------------- escape

# U+2000+ BARCHASI (emoji, tipografika, arx belgilar, VS16)
# + U+2000 dan past lekin CP1251 da mos kelib buziladigan belgilar:
#   U+00A0 nbsp, U+00A9 (c), U+00AE (r), U+00B0 (deg), U+00B7 (middle
#   dot!), U+00BC/BD (1/4,1/2), U+00D7 (x), U+00F7 (/)
#   Misol: '·' UTF-8 = C2 B7 -> CP1251 da "\u0412\u00b7" bo'lib buziladi.
_ESC_RE = re.compile('[\u00a0\u00a9\u00ae\u00b0\u00b7\u00bc\u00bd'
                    '\u00d7\u00f7\u2000-\U0010ffff]')
TEXT_KINDS = ('string', 'template')


def escape_text(body):
    """JS/CSS matn ichidagi U+2000+ belgilarni Unicode escape'ga o'kazadi."""

    def rep(m):
        cp = ord(m.group(0))
        return ('\\u{%x}' % cp) if cp > 0xFFFF else ('\\u%04x' % cp)

    return _ESC_RE.sub(rep, body)


# ---------------------------------------------------------------- asosiy

TARGET_DIRS = ['web']
TARGET_EXT = {'.js', '.css'}
SKIP_DIRS = {'__pycache__', '.git', 'node_modules', 'uploads', 'data'}


def iter_targets():
    for base in TARGET_DIRS:
        root = os.path.join(ROOT, base)
        if not os.path.isdir(root):
            continue
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith('.')]
            for f in sorted(fn):
                if os.path.splitext(f)[1] in TARGET_EXT:
                    yield os.path.join(dp, f)


def read_text(path):
    raw = open(path, 'rb').read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    if bom:
        raw = raw[3:]
    return raw.decode('utf-8'), bom, raw


def _apply_edits(text, edits):
    """edits: [(start, end, yangi_matn)] - o'zaro qatlamamasligi tekshiriladi."""
    edits = sorted(edits, key=lambda x: x[0])
    last = -1
    for s, e, _t in edits:
        assert s >= last, 'overlapping edit %d-%d' % (s, e)
        last = e
    out = text
    for s, e, t in sorted(edits, key=lambda x: -x[0]):
        out = out[:s] + t + out[e:]
    return out


def process(path, apply=False, do_escape=True):
    text, had_bom, raw = read_text(path)
    nl = '\r\n' if b'\r\n' in raw else '\n'
    body = text.replace('\r\n', '\n')

    # --- BOSQICH 1: mojibake tuzatish (barcha segmentlarda)
    segs = segments(body)
    fixes = []
    for _kind, s, e in segs:
        for rs, re_, fixed in find_mojibake(body[s:e]):
            fixes.append((s + rs, s + re_, fixed))
    body1 = _apply_edits(body, fixes)

    # --- BOSQICH 2: escape (faqat MATN segmentlarida, TUZATILGAN matn ustida).
    #     Segmentlar qaytadan skanlanadi: tuzatish uzunlikni o'zgartirgan.
    edits2 = []
    if do_escape:
        for kind, s, e in segments(body1):
            if kind not in TEXT_KINDS:
                continue
            chunk = body1[s:e]
            new = escape_text(chunk)
            if new != chunk:
                edits2.append((s, e, new))
    new_body = _apply_edits(body1, edits2)

    changed = bool(fixes) or bool(edits2) or had_bom
    if changed and apply:
        with open(path, 'wb') as fh:
            fh.write(new_body.replace('\n', nl).encode('utf-8'))

    segs_n = segments(new_body)
    return {'path': path, 'bom': had_bom, 'edits': fixes + edits2,
            'fixes': fixes, 'changed': changed,
            'skeleton': _skeleton(body, segs),
            'new_skeleton': _skeleton(new_body, segs_n),
            'seg_sig': tuple(k for k, s, e in segs),
            'new_seg_sig': tuple(k for k, s, e in segs_n)}


def _skeleton(text, segs):
    """Segmentlardagi kod skeleti - escape/tuzatish uni O'ZGARTIRMALIGI kerak."""
    parts = [text[s:e] for kind, s, e in segs if kind == 'code']
    return ''.join(parts)


def esc(s):
    return s.encode('unicode_escape').decode('ascii')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--no-escape', action='store_true',
                    help='faqat mojibake tuzatish (escape qilma)')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args()

    n_fix = n_esc = n_bom = 0
    for path in iter_targets():
        rel = os.path.relpath(path, ROOT).replace('\\', '/')
        r = process(path, args.apply, not args.no_escape)
        if r['skeleton'] != r['new_skeleton'] or r['seg_sig'] != r['new_seg_sig']:
            print('!! %s: sintaksis skeleti o\'zgardi - BEKOR QILINDI' % rel)
            continue
        nf = len(r['fixes'])
        ne = len(r['edits']) - nf
        n_fix += nf
        n_esc += ne
        n_bom += 1 if r['bom'] else 0
        if r['changed']:
            print('\n=== %s  (mojibake:%d escape:%d bom:%s) ==='
                  % (rel, nf, ne, r['bom']))
            if args.verbose:
                for s, e, t in r['edits']:
                    print('   %s' % esc(t[:120]))
        else:
            print('ok %s' % rel)

    print('\n' + '=' * 70)
    print('MOJIBAKE: %d   ESCAPE: %d   BOM: %d' % (n_fix, n_esc, n_bom))
    print('Holat: %s' % ('TUZATILDI' if args.apply else
                         ('o\'zgarish kerak' if (n_fix or n_esc or n_bom)
                          else 'toza')))
    return 0


if __name__ == '__main__':
    sys.exit(main())