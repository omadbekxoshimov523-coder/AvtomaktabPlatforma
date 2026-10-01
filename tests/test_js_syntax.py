# -*- coding: utf-8 -*-
"""HAQIQIY JavaScript sintaksis + bog'lanish (binding) tekshiruvi (esprima).

Nima uchun bu test kerak:
  `tools_js_check.py` — qo'lda yozilgan lekser; u faqat qavs/ketak muvozanatini
  tekshiradi. `x : null` kabi YARIM qolgan shartli operator qavsni muvozanatda
  saqlab qoladi va lekser uni ko'rmaydi — lekin brauzer butun faylni
  "Unexpected token ':'" bilan rad etadi (butun bo'lim ishlamay qoladi).

  Xuddi shuningdek, sintaksis to'g'ri bo'lsa ham `stat(...)` yoki
  `toggleSwitch(...)` kabi ANIQLANMAGAN yordamchilar chaqirilishi mumkin —
  bu holda brauzerda "X is not defined" chiqadi va bo'lim yana ishlamaydi.

Shuning uchun:
  1) har bir `web/js/*.js` haqiqiy JS parser orqali PARSE qilinadi;
  2) AST bo'yicha barcha chaqirilayotgan nomlar ANIQLANGAN yoki global
     bo'lishi tekshiriladi.

`esprima` o'rnatilmagan bo'lsa 1-bosqich `skip` bo'ladi:
    pip install -r requirements-dev.txt
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_JS = ROOT / "web" / "js"

try:
    import esprima
    HAVE_ESPRIMA = True
except ImportError:                                   # pragma: no cover
    esprima = None
    HAVE_ESPRIMA = False

# index.html'da yuklanadigan fayllar
EXPECTED_FILES = [
    "api.js", "app.js", "i18n.js", "map.js", "shared.js", "ui.js",
    "views-admin.js", "views-instructor.js", "views-student.js",
]

# brauzer/JS standarti global'lari — kodda aniqlanmaydi, xato ham emas
GLOBALS = {
    "window", "document", "console", "globalThis", "self", "top", "parent",
    "Math", "JSON", "Object", "Array", "String", "Number", "Boolean", "Date",
    "RegExp", "Error", "TypeError", "Promise", "Set", "Map", "WeakMap",
    "Symbol", "Proxy", "Reflect", "Intl", "Uint8Array", "Int8Array",
    "ArrayBuffer", "DataView", "FormData", "FileReader", "Blob", "File",
    "Image", "URL", "URLSearchParams", "fetch", "Headers", "Request",
    "Response", "AbortController", "localStorage", "sessionStorage",
    "location", "history", "navigator", "alert", "confirm", "prompt",
    "setTimeout", "clearTimeout", "setInterval", "clearInterval",
    "requestAnimationFrame", "cancelAnimationFrame",
    "parseInt", "parseFloat", "isNaN", "isFinite", "encodeURIComponent",
    "decodeURIComponent", "structuredClone", "undefined", "NaN", "Infinity",
    "require", "module", "exports",
    # brauzer API'lari
    "matchMedia", "getComputedStyle", "scrollTo", "open", "print", "close",
    "MutationObserver", "ResizeObserver", "IntersectionObserver", "Event",
    "CustomEvent", "HTMLElement", "Node", "Element", "DOMParser", "Option",
    "ClipboardEvent", "CustomEvent", "Text", "CanvasRenderingContext2D",
    "ImageData", "crypto", "performance", "atob", "btoa", "queueMicrotask",
    "addEventListener", "removeEventListener", "dispatchEvent", "postMessage",
}


def as_plain(node):
    """esprima `Syntax` obyektini oddiy `dict`/`list` ga aylantiradi."""
    if hasattr(node, "toDict"):
        return node.toDict()
    return node


def walk(node):
    """AST bo'yicha rekursiv yuruvchi (har bir node bir marta)."""
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                if isinstance(v, (dict, list)):
                    stack.append(v)


def pattern_names(node):
    """Destructuring shakli (`const { a, b: c } = ...`) dan olingan nomlar."""
    names = []
    if not isinstance(node, dict):
        return names
    t = node.get("type")
    if t == "Identifier":
        names.append(node.get("name"))
    elif t == "ObjectPattern":
        for p in node.get("properties", []):
            names += pattern_names(p.get("value") or p.get("argument"))
    elif t == "ArrayPattern":
        for e in node.get("elements", []):
            names += pattern_names(e)
    elif t in ("AssignmentPattern", "RestElement"):
        names += pattern_names(node.get("left") or node.get("argument"))
    elif t == "Property":
        names += pattern_names(node.get("value"))
    return [n for n in names if n]


def bindings_of(ast):
    """Faylda ANIQLANGAN barcha nomlar (funksiya, o'zgaruvchi, destrukturing, metod)."""
    out = set()
    for n in walk(ast):
        t = n.get("type")
        if t in ("FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"):
            # funksiya nomi + PARAMETRLAR (callback'lar `onYes(...)` shaklida
            # to'g'ridan-to'g'ri chaqirilishi mumkin)
            for a in n.get("params", []):
                out |= set(pattern_names(a))
            if n.get("id"):
                out.add(n["id"]["name"])
        elif t == "VariableDeclarator":
            out |= set(pattern_names(n.get("id")))
        elif t == "AssignmentExpression":
            left = n.get("left")
            if isinstance(left, dict) and left.get("type") == "Identifier":
                out.add(left["name"])
        elif t == "Property" and (n.get("method") or
                                  (n.get("value") or {}).get("type", "").startswith("Function")):
            key = n.get("key")
            if isinstance(key, dict) and key.get("type") == "Identifier":
                out.add(key["name"])
    return {x for x in out if x and x not in GLOBALS}


def calls_of(ast):
    """`foo(...)` shaklida chaqirilayotgan nomlar (usul emas — `a.foo(...)` hisobga olmaydi)."""
    out = set()
    for n in walk(ast):
        if n.get("type") != "CallExpression":
            continue
        c = n.get("callee")
        if isinstance(c, dict) and c.get("type") == "Identifier":
            out.add(c["name"])
    return out


class TestJsSyntax(unittest.TestCase):
    """`web/js` — sintaksis to'g'ri va aniqlanmagan nom ishlatilmaydi."""

    @unittest.skipUnless(HAVE_ESPRIMA, "esprima o'rnatilmagan (pip install -r requirements-dev.txt)")
    def test_all_js_files_parse(self):
        """Hech bir JS faylida sintaksis xatosi YO'Q bo'lishi kerak.

        Aks holda brauzer butun faylni yuklamaydi -> butun bo'lim ishlamaydi.
        """
        bad = []
        for f in sorted(WEB_JS.glob("*.js")):
            try:
                esprima.parseScript(f.read_text(encoding="utf-8"), tolerant=False)
            except Exception as e:                      # noqa: BLE001
                bad.append("%s: %s" % (f.name, str(e).split("\n")[0][:130]))
        self.assertEqual(bad, [], "sintaksis xatolari:\n  " + "\n  ".join(bad))

    def test_expected_js_files_present(self):
        """Yuklanadigan fayllar o'z o'rnida (yo'qotilsa brauzer yuklay olmaydi)."""
        missing = [n for n in EXPECTED_FILES if not (WEB_JS / n).is_file()]
        self.assertEqual(missing, [], "yo'q JS fayllar: %s" % missing)

    @unittest.skipUnless(HAVE_ESPRIMA, "esprima o'rnatilmagan")
    def test_no_undefined_helpers(self):
        """CHAQIRILAYOTGAN har bir funksiya fayl ichida ANIQLANGAN bo'lishi shart.

        Bu — brauzerdagi "X is not defined" oldini oladi. Shu sababdan
        `toggleSwitch`/`toggleRow` ni `const {...} = UI` ro'yxatiga kiritish
        va `stat()` yordamchisini qayta yozish shart edi.
        """
        problems = []
        for f in sorted(WEB_JS.glob("*.js")):
            src = f.read_text(encoding="utf-8")
            try:
                ast = as_plain(esprima.parseScript(src, tolerant=False))
            except Exception as e:                      # noqa: BLE001
                problems.append("%s: PARSE xatosi — %s" % (f.name, str(e)[:90]))
                continue
            known = bindings_of(ast)
            for name in sorted(calls_of(ast)):
                if name in known or name in GLOBALS:
                    continue
                problems.append("%s: %s(...) — aniqlanmagan" % (f.name, name))
        self.assertEqual(problems, [], "aniqlanmagan yordamchilar:\n  " + "\n  ".join(problems))

    @unittest.skipUnless(HAVE_ESPRIMA, "esprima o'rnatilmagan")
    def test_views_helpers_imported_from_ui(self):
        """`const {...} = UI` ro'yxati faqat UI.da HAQIQATAN bor nomlardan iborat."""
        ui_src = (WEB_JS / "ui.js").read_text(encoding="utf-8")
        ui_ast = as_plain(esprima.parseScript(ui_src, tolerant=False))
        exported = set()
        for n in walk(ui_ast):
            if n.get("type") != "ReturnStatement":
                continue
            arg = n.get("argument")
            if isinstance(arg, dict) and arg.get("type") == "ObjectExpression":
                for p in arg.get("properties", []):
                    k = p.get("key")
                    if isinstance(k, dict) and k.get("type") == "Identifier":
                        exported.add(k["name"])
        self.assertIn("el", exported, "ui.js eksportlari topilmadi")
        self.assertIn("toggleSwitch", exported, "ui.js toggleSwitch'ni eksport qilmaydi")

        problems = []
        for name in ("views-admin.js", "views-instructor.js", "views-student.js"):
            src = (WEB_JS / name).read_text(encoding="utf-8")
            ast = as_plain(esprima.parseScript(src, tolerant=False))
            for n in walk(ast):
                if n.get("type") != "VariableDeclarator":
                    continue
                init = n.get("init") or {}
                txt = init.get("type")
                if txt not in ("Identifier", "MemberExpression"):
                    continue
                if init.get("name") != "UI" and \
                        (init.get("property") or {}).get("name") != "UI":
                    continue
                for fn in pattern_names(n.get("id")):
                    # `const UI = window.UI` — bu import emas, shuning uchun
                    # faqat DESTRUKTURING (`const { a, b } = UI`) tekshiriladi
                    if (n.get("id") or {}).get("type") == "Identifier":
                        continue
                    if fn not in exported:
                        problems.append("%s: UI.%s — ui.js da yo'q" % (name, fn))
        self.assertEqual(problems, [], "UI dan olingan nomlar:\n  " + "\n  ".join(problems))


if __name__ == "__main__":
    unittest.main(verbosity=2)