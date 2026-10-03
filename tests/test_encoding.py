# -*- coding: utf-8 -*-
"""KODIROVKA testlari - "mojibake" ning qaytishiga qarshi kuzatuv.

Muammo: `web/js/views-student.js` fayli bir vaqt UTF-8 baytlari Windows-1251
deb o'qilib, qayta UTF-8 sifatida saqlangan edi (double-encoding). Natijada
barcha emoji va tipografik belgilar buzilib chiqdi:
    "РЯ“€ "  (📈)      "вЂ”"  (—)
    "РЯ“Ђ "  (📨)      "В·"   (·)

Kelajakda shu xato TIKILMASLIGI uchun quyidagilar tekshiriladi:

  1. Hech qanday matn faylida UTF-8 BOM yo'q
  2. Barcha matn fayllar toza UTF-8 da ochiladi (strict decode)
  3. Hech qanday mojibake belgisi yo'q (CP1251/Latin-1 round-trip testi)
  4. U+FFFD (replacement char) - butunlay yo'qolgan belgi - ishlatilmagan
  5. `.editorconfig` va `.gitattributes` mavjud va UTF-8 ni talab qiladi
  6. HTML fayllarda `<meta charset="UTF-8">` `<head>` ning eng boshida
  7. Backend barcha javoblarda `charset=utf-8` yuboradi
  8. JS matnlaridagi emoji/beglar Unicode escape ko'rinishida
     (fayl kodirovkasi qanday bo'lsa ham, belgilar to'g'ri chiqadi)

Ishga tushirish:
    python -m tests.test_encoding
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools_fix_encoding import (find_mojibake, segments,           # noqa: E402
                                SKIP_DIRS as ENC_SKIP_DIRS)

TEXT_DIRS = ['app', 'web', 'tests', 'bot']
TEXT_EXT = {'.py', '.js', '.css', '.html', '.md', '.txt', '.sql',
            '.json', '.yml', '.yaml', '.example', '.csv'}
TEXT_FILES = {'.env.example', '.editorconfig', '.gitattributes',
              '.gitignore', 'server.py', 'README.md'}
BINARY_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.pdf',
              '.zip', '.gz', '.db', '.sqlite', '.sqlite3', '.xlsx', '.woff',
              '.woff2', '.ttf', '.eot'}
SKIP = ENC_SKIP_DIRS | {'backups', 'shots', 'logs', '__pycache__'}
SEGMENTED_EXT = {'.js', '.css'}

REPL_CHR = re.compile('\\ufffd')


def _iter_files():
    seen = set()
    for base in TEXT_DIRS + ['']:
        root = ROOT / base if base else ROOT
        if not root.is_dir():
            continue
        for dp, dn, fn in os_walk(root):
            dn[:] = [d for d in dn if d not in SKIP and not d.startswith('.')]
            for name in sorted(fn):
                full = Path(dp) / name
                ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
                ext = '.' + ext if ext else ''
                if ext in BINARY_EXT or name.endswith('.bak'):
                    continue
                if ext not in TEXT_EXT and name not in TEXT_FILES:
                    continue
                rel = full.relative_to(ROOT)
                if base == '' and rel.parts[0] in TEXT_DIRS:
                    continue
                if full in seen:
                    continue
                seen.add(full)
                yield full, rel.as_posix()


def os_walk(root):
    import os
    for dp, dn, fn in os.walk(root):
        yield dp, dn, fn


def _preview(s, n=36):
    s = s.strip()
    if len(s) > n:
        s = s[:n] + '...'
    return s.encode('unicode_escape').decode('ascii')


class TestEncodingUtf8(unittest.TestCase):
    """[1][2] BOM va to'g'ri UTF-8"""

    def test_01_no_utf8_bom(self):
        """Hech qanday matn faylda UTF-8 BOM (EF BB BF) bo'lmasligi kerak."""
        bad = []
        for full, rel in _iter_files():
            if full.read_bytes().startswith(b'\xef\xbb\xbf'):
                bad.append(rel)
        self.assertEqual(bad, [], 'UTF-8 BOM topildi: %s' % bad)

    def test_02_files_are_valid_utf8(self):
        """Barcha matn fayllar strict UTF-8 da ochilishi kerak."""
        bad = []
        for full, rel in _iter_files():
            raw = full.read_bytes()
            if raw.startswith(b'\xef\xbb\xbf'):
                raw = raw[3:]
            try:
                raw.decode('utf-8')
            except UnicodeDecodeError as e:
                bad.append('%s: %s' % (rel, e))
        self.assertEqual(bad, [], 'UTF-8 decode xatosi: %s' % bad)

    def test_03_no_utf16(self):
        """UTF-16 fayl bo'lmasligi kerak (Git "binary" deb aniqlaydi)."""
        bad = [rel for full, rel in _iter_files()
               if full.read_bytes()[:2] in (b'\xff\xfe', b'\xfe\xff')]
        self.assertEqual(bad, [], 'UTF-16 fayl topildi: %s' % bad)


class TestEncodingMojibake(unittest.TestCase):
    """[3][4] Mojibake va yo'qolgan belgilar"""

    def _scan(self):
        problems = []
        for full, rel in _iter_files():
            text = full.read_bytes().decode('utf-8')
            if text.startswith('﻿'):
                text = text[1:]
            ext = full.suffix.lower()
            if ext in SEGMENTED_EXT:
                chunks = [text[s:e] for _k, s, e in segments(text)]
            else:
                chunks = [text]
            for chunk in chunks:
                for _s, _e, _fx in find_mojibake(chunk):
                    problems.append((rel, 'mojibake'))
        return problems

    def test_04_no_mojibake(self):
        """UTF-8 -> CP1251/Latin-1 -> UTF-8 (double-encoding) belgisi bo'lmasin."""
        bad = []
        for full, rel in _iter_files():
            text = full.read_bytes().decode('utf-8')
            if text.startswith('﻿'):
                text = text[1:]
            ext = full.suffix.lower()
            chunks = ([text[s:e] for _k, s, e in segments(text)]
                      if ext in SEGMENTED_EXT else [text])
            for chunk in chunks:
                for s, e, _fx in find_mojibake(chunk):
                    bad.append('%s: %s' % (rel, _preview(chunk[s:e])))
        self.assertEqual(bad, [],
                         'MOJIBAKE topildi (%d):\n  %s' % (len(bad), '\n  '.join(bad[:25])))

    def test_05_no_replacement_char(self):
        """U+FFFD (butilmay buzilgan belgi) fayllarda ishlatilmasin."""
        bad = []
        for full, rel in _iter_files():
            # bu test vositalarning o'z regex manbalarini tekshirmaydi
            if full.name in ('tools_fix_encoding.py',
                             'tools_check_encoding.py',
                             'test_encoding.py'):
                continue
            text = full.read_bytes().decode('utf-8')
            if text.startswith('﻿'):
                text = text[1:]
            m = REPL_CHR.search(text)
            if m:
                ln = text.count('\n', 0, m.start()) + 1
                bad.append('%s:%d' % (rel, ln))
        self.assertEqual(bad, [], 'U+FFFD topildi: %s' % bad)


class TestEncodingGuardConfig(unittest.TestCase):
    """[5][6][7] Oldini olish vositalari"""

    def test_06_editorconfig_requires_utf8(self):
        p = ROOT / '.editorconfig'
        self.assertTrue(p.exists(), '.editorconfig yo\'q')
        txt = p.read_text(encoding='utf-8')
        self.assertIn('charset = utf-8', txt,
                      '.editorconfig da `charset = utf-8` yo\'q')
        self.assertIn('root = true', txt,
                      '.editorconfig da `root = true` yo\'q')

    def test_07_gitattributes_exists(self):
        p = ROOT / '.gitattributes'
        self.assertTrue(p.exists(), '.gitattributes yo\'q')
        txt = p.read_text(encoding='utf-8')
        self.assertIn('text=auto', txt)
        for pat in ('*.js    text', '*.py    text', '*.html  text'):
            self.assertIn(pat, txt, '.gitattributes da %s yo\'q' % pat)

    def test_08_html_meta_charset_first_in_head(self):
        """<meta charset="UTF-8"> <head> ichida eng birinchi teglardan biri."""
        for name in ('index.html', 'login-redesign.html'):
            p = ROOT / 'web' / name
            if not p.exists():
                continue
            txt = p.read_bytes().decode('utf-8')
            self.assertFalse(txt.startswith('﻿'),
                             '%s BOM bilan boshlanmoqda' % name)
            m = re.search(r'(?is)<head[^>]*>', txt)
            self.assertIsNotNone(m, '%s da <head> topilmadi' % name)
            head = txt[m.end():]
            first = re.search(r'<!--.*?-->|<meta[^>]*>|<script|<link|<title|<style',
                              head, re.S)
            self.assertIsNotNone(first, '%s: <head> bo\'sh' % name)
            self.assertTrue(
                first.group(0).lower().startswith(('<meta', '<!--')),
                '%s: <head> da birinchi teg <meta charset> emas (%s)'
                % (name, first.group(0)[:40]))
            cm = re.search(r'(?i)<meta[^>]*charset\s*=\s*["\']?([\w-]+)', head)
            self.assertIsNotNone(cm, '%s da meta charset yo\'q' % name)
            self.assertEqual(cm.group(1).lower(), 'utf-8',
                             '%s: charset=%s (utf-8 bo\'lishi kerak)'
                             % (name, cm.group(1)))

    def test_09_backend_sends_charset(self):
        """Backend JSON/HTML/JS/CSS uchun `charset=utf-8` yuborishi kerak."""
        txt = (ROOT / 'server.py').read_text(encoding='utf-8')
        for needle in ('text/html; charset=utf-8',
                       'text/css; charset=utf-8',
                       'application/javascript; charset=utf-8',
                       'application/json; charset=utf-8'):
            self.assertIn(needle, txt,
                          'server.py da "%s" yo\'q' % needle)
        self.assertIn('ensure_ascii=False', txt,
                      'server.py da ensure_ascii=False yo\'q - '
                      'ru/uz harflari JSON\'da \\uXXXX bo\'lib chiqadi')
        self.assertIn('X-Content-Type-Options', txt)


class TestEncodingEscapedSymbols(unittest.TestCase):
    """[8] Emoji/beglar Unicode escape ko'rinishida (kodirovka-dan himoyalangan)"""

    RISKY = re.compile('[\u2000-\U0010ffff]')

    def _js_string_chunks(self, text):
        return [text[s:e] for k, s, e in segments(text) if k in ('string', 'template')]

    def test_10_no_raw_emoji_in_js_strings(self):
        r"""JS matnlarida xom emoji/tipografik belgi qolmasin - escape bo'lsin.

        Sabab: agar belgi faylda xom saqlansa, fayl noto'g'ri kodirovkada
        saqlanganda yana "mojibake"ga aylanadi (2026-yil oktyabrda shunday
        buzilish sodir bo'lgandi).
        """
        bad = []
        for p in sorted((ROOT / 'web' / 'js').glob('*.js')):
            text = p.read_bytes().decode('utf-8')
            for chunk in self._js_string_chunks(text):
                for m in self.RISKY.finditer(chunk):
                    bad.append('%s: %s' % (p.name,
                                           _preview(chunk[max(0, m.start() - 6):
                                                          m.end() + 6])))
        self.assertEqual(bad, [],
                         'xom belgi JS matnida qoldi (%d):\n  %s'
                         % (len(bad), '\n  '.join(bad[:20])))

    def test_11_emoji_actually_preserved(self):
        r"""Escape qilingandan KEYIN ham belgilar runtime'da to'g'ri chiqishi
        SHART - ya'ni \u{1f4c8} -> \U0001F4C8 (📈), \u2014 -> — va h.k."""
        src = (ROOT / 'web' / 'js' / 'views-student.js').read_bytes().decode('utf-8')
        self.assertIn(r'text: "\u{1f4c8} " + t("home.overall_progress")', src,
                      'Umumiy progress sarlavhasidagi \U0001F4CA (📈) topilmadi')
        # bo'sh qiymat belgisi
        self.assertIn(r'"\u2014"', src, 'bo\'sh qiymat uchun "—" topilmadi')
        # so'rovlar / bildirishnoma sarlavhalari
        for esc, ch in [(r'"\u{1f4e8}"', '\U0001F4E8'),    # 📨
                        (r'"\u{1f697}"', '\U0001F697'),    # 🚗
                        (r'" \u00b7 "', '\u00b7')]:          # ·
            self.assertIn(esc, src, '%s topilmadi' % ch)

    def test_12_known_icons_render_as_escape(self):
        """Sarlavha ikonkalari: escape'ga aylangan va ASCII lotin/kirill o'qiladi."""
        src = (ROOT / 'web' / 'js' / 'views-student.js').read_bytes().decode('utf-8')
        for esc, name in [(r'\u{1f4c8}', '📈 Umumiy progress'),
                          (r'\u23ed\ufe0f', '⏭ Keyingi dars'),
                          (r'\u{1f4c5}', '📅 Sana'),
                          (r'\u{1f4cd}', '📍 Manzil'),
                          (r'\u{1f4e8}', '📨 So\'rov/Bildirishnoma')]:
            self.assertIn(esc, src, '%s sarlavha ikonkasi topilmadi' % name)


# =====================================================================
#  i18n MATN KALITLARI — "ko'rinib qolgan placeholder" ga qarshi
# =====================================================================
# Bug: `t("week.remaining_lessons")` `{n}` PARAMETRSIZ chaqirilganda
# ekranda "Qolgan: {n} 30" ko'rinardi (o'rniga "Qolgan 30" bo'lishi
# kerak edi). Kelajakda shu xato TIKILMASLIGI uchun:
#   1. har bir kalitda faqat 3 til ham bor (paritet)
#   2. placeholder'li kalit `t(...)` da paramsiz CHAQIRILMAGAN
#      (emoji-placeholder va qo'lda `.replace("{x}", ...)` hisobga olinadi)


def _i18n_blocks():
    """i18n.js dan (kalit -> tana) juftliklarini qaytaradi (qobiq-aware)."""
    import re as _re
    src = (ROOT / 'web' / 'js' / 'i18n.js').read_text(encoding='utf-8')
    out = []
    i = 0
    pat = _re.compile(r'"([\w.]+)"\s*:\s*\{')
    while True:
        m = pat.search(src, i)
        if not m:
            return out
        j = m.end() - 1
        depth, in_str, quote, esc = 0, False, '', False
        while j < len(src):
            ch = src[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == quote:
                    in_str = False
            else:
                if ch in '"\'':
                    in_str, quote = True, ch
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        out.append((m.group(1), src[m.end():j]))
        i = j + 1


class TestI18nText(unittest.TestCase):
    """Matn kalitlarining to'g'riligi (3 til + placeholder)."""

    LANGS = ('uz', 'ru', 'en')

    def test_13_all_keys_have_three_languages(self):
        """PARITET: har bir kalitda uz + ru + en bo'lishi SHART."""
        import re as _re
        bad = []
        for key, body in _i18n_blocks():
            for lang in self.LANGS:
                if not _re.search(r'(?:^|[,{\s])' + lang + r'\s*:\s*"', body):
                    bad.append('%s -> %s yo\'q' % (key, lang))
        self.assertEqual(bad, [], 'i18n paritet buzilgan:\n  ' + '\n  '.join(bad))

    def test_14_no_placeholder_left_in_ui(self):
        """Placeholder'li kalit `paramsiz` chaqirilmasin.

        Aks holda ekranda "Qolgan: {n} 30" kabi matn chiqadi.
        Emoji-placeholder (`{1f4e8}`) va qo'lda `.replace("{s}", ...)`
        bilan almashtirilgan holatlar hisobga olinadi.
        """
        import re as _re
        emoji = _re.compile(r'^(1f[0-9a-f]{3}|2[0-9a-f]{4}|23[0-9a-f]{2})$')
        placeholders = {}
        for key, body in _i18n_blocks():
            ph = sorted({p for p in _re.findall(r'\{(\w+)\}', body)
                         if not emoji.match(p)})
            if ph:
                placeholders[key] = ph
        self.assertTrue(placeholders, 'placeholder topilmadi — skaner buzilgan')

        bad = []
        for js in sorted((ROOT / 'web' / 'js').glob('*.js')):
            if js.name == 'i18n.js':
                continue
            text = js.read_text(encoding='utf-8')
            for ln, line in enumerate(text.split('\n'), 1):
                for m in _re.finditer(r'\bt\(\s*"([\w.]+)"\s*([,)])', line):
                    key, tail = m.group(1), m.group(2)
                    if key not in placeholders:
                        continue
                    seg = line[m.end(1):]
                    # qo'lda `.replace("{x}", ...)` bilan almashtirilgan — OK
                    if all(('{%s}' % p) in seg for p in placeholders[key]):
                        continue
                    if tail == ')':
                        bad.append('%s:%d t("%s") -> %s'
                                   % (js.name, ln, key, placeholders[key]))
                    else:
                        for p in placeholders[key]:
                            if not _re.search(r'\b' + p + r'\s*:', seg):
                                bad.append('%s:%d t("%s") -> {%s} berilmagan'
                                           % (js.name, ln, key, p))
        self.assertEqual(bad, [], 'ekranda ko\'rinib qoladigan placeholder:\n  '
                                   + '\n  '.join(bad))


if __name__ == '__main__':
    unittest.main(verbosity=2)