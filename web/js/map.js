/* ============================================================================
   MODUL 4 — XARITA (Yandex Maps JS API)

   AVVALGI HOLAT: OpenStreetMap havolasi + "lat"/"lng" yozuvli bo'sh maydonlar.
   Foydalanuvchi koordinatani qo'lda kiritishi kerak edi, xarita esa
   platformada umuman ko'rinmasdi.

   HOZIRGI HOLAT:
     * Xarita — Yandex Maps JS API (https://yandex.ru/dev/js/).
       API kaliti `.env` dagi `YANDEX_MAPS_API_KEY` dan olinadi va
       `GET /api/config` orqali brauzerga beriladi (bu kalit OMMAVIY —
       Yandex uni DOMAIN bo'yicha cheklaydi, kodga QATTIQ yozilmaydi).
     * Xarita markazi — TOSHKENT (server `.env` dan o'qib beradi).
     * Talaba "Olish manzili" modalida xaritada nuqta bosadi -> kenglik
       (Kenglik / latitude) va uzunlik (Uzunlik / longitude) avtomatik
       to'ldiriladi. Qo'lda kiritish ham saqlanib qoladi.
     * "🗺️ Xaritada ko'rish" havolasi Yandex xaritasiga olib boradi.

   QOIDA: xato HECH QACHON jim qolmaydi. Kalit yo'q bo'lsa, skript
   yuklanmasa yoki sozlamani olib bo'lmasa — aniq, tushunarli xabar
   ko'rsatiladi (tuzatish yo'lini aytib berib).
   ============================================================================ */
const MapView = (function () {
  const SCRIPT_ID = "yandex-maps-js";

  /* Toshkent — server sozlamasi kelmasa ham xarita JOYNI bo'sh qolmasligi uchun. */
  const FALLBACK_CENTER = { lat: 41.311081, lng: 69.240562, zoom: 12 };

  let cfg = null;          /* serverdan kelgan sozlamalar */
  let cfgPromise = null;   /* /api/config so'rovi (bir marta) */
  let loadPromise = null;  /* Yandex skripti (bir marta) */

  function txt(key, params) {
    try { return I18N.t(key, params); } catch (e) { return key; }
  }

  /* Yandex xarita tili — interfeys tilimiz bilan bir xil bo'lsin. */
  function yandexLang() {
    let l = "uz";
    try { l = (I18N.getLang && I18N.getLang()) || "uz"; } catch (e) { /* bo'sh */ }
    if (l === "ru") return "ru_RU";
    if (l === "en") return "en_US";
    return "uz_UZ";
  }

  function center() {
    const c = cfg && cfg.center;
    if (c && typeof c.lat === "number" && typeof c.lng === "number" &&
        isFinite(c.lat) && isFinite(c.lng)) {
      return { lat: c.lat, lng: c.lng, zoom: (typeof c.zoom === "number" ? c.zoom : FALLBACK_CENTER.zoom) };
    }
    return FALLBACK_CENTER;
  }

  /* ------------------------------------------------------------------ sozlamalar */
  async function config(force) {
    if (cfg && !force) return cfg;
    if (cfgPromise && !force) return cfgPromise;
    cfgPromise = API.get("config").then(function (d) {
      cfg = (d && d.config && d.config.maps) || { provider: "yandex", api_key: "", enabled: false };
      return cfg;
    }).catch(function (e) {
      /* Sozlamani olib bo'lmasa — jim qolmaymiz, sababni saqlaymiz. */
      cfg = { provider: "yandex", api_key: "", enabled: false, error: (e && e.code) || "map.config_error" };
      return cfg;
    });
    return cfgPromise;
  }

  /* ------------------------------------------------------------------ skriptni yuklash */
  function loadScript(apiKey) {
    if (loadPromise) return loadPromise;
    loadPromise = new Promise(function (resolve, reject) {
      if (window.ymaps && typeof window.ymaps.ready === "function") {
        window.ymaps.ready(function () { resolve(window.ymaps); });
        return;
      }
      const url = "https://api-maps.yandex.ru/2.1/?apikey=" +
        encodeURIComponent(apiKey) + "&lang=" + yandexLang();
      const old = document.getElementById(SCRIPT_ID);
      if (old) {
        old.addEventListener("load", function () { window.ymaps ? resolve(window.ymaps) : reject(new Error("map.no_ymaps")); });
        old.addEventListener("error", function () { reject(new Error("map.script_failed")); });
        return;
      }
      const s = document.createElement("script");
      s.id = SCRIPT_ID;
      s.async = true;
      s.defer = true;
      s.src = url;
      s.onload = function () {
        if (window.ymaps && typeof window.ymaps.ready === "function") {
          window.ymaps.ready(function () { resolve(window.ymaps); });
        } else {
          reject(new Error("map.no_ymaps"));
        }
      };
      s.onerror = function () { reject(new Error("map.script_failed")); };
      document.head.appendChild(s);
    });
    return loadPromise;
  }

  /* ------------------------------------------------------------------ havola */
  function isNum(v) {
    if (v === null || v === undefined || v === "") return false;
    const n = Number(v);
    return isFinite(n);
  }

  /* Yandex `ll`/`pt` — UZUNLIK birinchi, kenglik ikkinchi */
  function linkUrl(lat, lng, zoom) {
    const la = Number(lat), ln = Number(lng);
    const pt = ln + "%2C" + la;
    return "https://yandex.uz/maps/?ll=" + pt + "&z=" + (zoom || 17) + "&pt=" + pt + "%2Cpm2rdm";
  }

  /* Xaritada ochish havolasi (DOM element). Koordinata yo'q bo'lsa —
     "—" qaytariladi (bo'sh havola emas, chindan ko'rinmaydi). */
  function link(lat, lng, label, zoom) {
    const { el } = UI;
    if (!isNum(lat) || !isNum(lng)) {
      return el("span", { class: "muted", text: label || "\u2014" });
    }
    return el("a", {
      class: "link", href: linkUrl(lat, lng, zoom), target: "_blank", rel: "noopener",
      text: label || txt("map.open"),
    });
  }

  /* ------------------------------------------------------------------ xato bloki */
  function errorBox(code, detail) {
    const { el } = UI;
    const box = el("div", { class: "map-msg map-msg-err" }, [
      el("div", { class: "map-msg-title", icon: "map", text: txt(code) }),
    ]);
    if (detail) box.append(el("div", { class: "map-msg-sub", text: detail }));
    if (code === "map.no_key") {
      box.append(el("div", { class: "map-msg-sub mono", text: "YANDEX_MAPS_API_KEY" }));
      box.append(el("div", { class: "map-msg-sub", text: txt("map.no_key_fix") }));
    }
    if (code === "map.load_error" || code === "map.script_failed") {
      box.append(el("button", { class: "btn btn-light btn-sm mt", text: txt("common.retry") || "Retry",
        onclick: function () { mount(box, box.__opts || {}); } }));
    }
    return box;
  }

  /* ------------------------------------------------------------------ asosiy funksiya
     `container` ichiga xarita o'rnashadi.
       opts.lat / opts.lng — boshlang'ich nuqta (bo'lsa shu markazga yaqinlashadi)
       opts.zoom        — masshtab
       opts.onChange(lat, lng) — nuqta tanlanganda chaqiriladi
  */
  async function mount(container, opts) {
    const o = opts || {};
    container.__opts = o;
    const { el } = UI;

    /* Modal yopilganda xarita DOM'dan chiqadi; kechikish natijasida
       "not a constructor" xatosi chiqmasligi uchun tekshiramiz. */
    if (!container || !container.isConnected) return null;

    container.innerHTML = "";
    container.append(el("div", { class: "map-box" }, [
      el("div", { class: "map-loading", text: txt("map.loading") }),
    ]));

    const c = await config();
    if (!container.isConnected) return null;

    if (c && c.error) {
      container.innerHTML = "";
      container.append(errorBox("map.config_error", c.error));
      return null;
    }
    if (!c || !c.api_key || c.enabled === false) {
      container.innerHTML = "";
      container.append(errorBox("map.no_key"));
      return null;
    }

    let ymaps;
    try {
      ymaps = await loadScript(c.api_key);
    } catch (e) {
      if (!container.isConnected) return null;
      container.innerHTML = "";
      container.append(errorBox("map.load_error", (e && e.message) || ""));
      return null;
    }
    if (!container.isConnected) return null;

    const mid = center();
    const startLat = isNum(o.lat) ? Number(o.lat) : mid.lat;
    const startLng = isNum(o.lng) ? Number(o.lng) : mid.lng;
    const hasPoint = isNum(o.lat) && isNum(o.lng);
    const zoom = typeof o.zoom === "number" ? o.zoom : (hasPoint ? 16 : mid.zoom);

    const box = el("div", { class: "map-box" });
    container.innerHTML = "";
    container.append(box);

    let map;
    try {
      map = new ymaps.Map(box, {
        center: [startLat, startLng],
        zoom: zoom,
        controls: ["zoomControl", "fullscreenControl", "typeSelector"],
        /* Toshkent atrofida boshqarishni cheklash — xarita "uzilib"
           ketmasligi uchun. Ko'rsatkich yana kengaytirilishi mumkin. */
        bounds: [[mid.lat - 12, mid.lng - 12], [mid.lat + 12, mid.lng + 12]],
      }, { suppressMapOpenBlock: true });
    } catch (e) {
      container.innerHTML = "";
      container.append(errorBox("map.init_error", (e && e.message) || ""));
      return null;
    }

    let placemark = null;
    function setPoint(lat, lng, notify) {
      const c2 = [Number(lat), Number(lng)];
      if (!isFinite(c2[0]) || !isFinite(c2[1])) return;
      if (placemark) {
        placemark.geometry.setCoordinates(c2);
      } else {
        placemark = new ymaps.Placemark(c2, { preset: "islands#redDotIcon" }, { draggable: true });
        map.geoObjects.add(placemark);
        placemark.events.add("dragend", function () {
          const p = placemark.geometry.getCoordinates();
          if (typeof o.onChange === "function") o.onChange(p[0], p[1]);
        });
      }
      if (notify && typeof o.onChange === "function") o.onChange(Number(lat), Number(lng));
    }

    map.events.add("click", function (e) {
      const p = e.get("coords");
      if (p) setPoint(p[0], p[1], true);
    });

    if (hasPoint) setPoint(startLat, startLng, false);

    /* BAND 1: autocomplete tanlangach xaritada nuqta shu manzilga ko'chiriladi.
       `setPoint(lat, lng, notify)` — `notify=false` bo'lsa `onChange` chaqirilmaydi
       (biz manzilni allaqachon inputga yozganmiz). */
    return {
      map: map,
      ymaps: ymaps,
      setPoint: setPoint,
      getPoint: function () {
        if (!placemark) return null;
        const p = placemark.geometry.getCoordinates();
        return { lat: p[0], lng: p[1] };
      },
      /** Kenglik/uzunlikni UI'da ko'rsatmasdan, faqat xarita markazini o'zgartirish. */
      panTo: function (lat, lng, z) {
        try { map.panTo([Number(lat), Number(lng)], { checkValidity: true, duration: 300 }); } catch (e) { /* bo'sh */ }
        if (typeof z === "number") setTimeout(function () { try { map.setZoom(z, { duration: 300 }); } catch (e) { /* bo'sh */ } }, 320);
      },
    };
  }

  /* ================================================================== AUTOCOMPLETE
     BAND 1 — "Uchrashuv joyi" uchun manzil AUTOCOMPLETE.
     (XARITA VAQTINCHA O'CHIRILGAN: bu modul `shared.js` dan chaqirilmaydi,
      lekin to'liq saqlangan — API kaliti tayyor bo'lgach qayta yoqiladi.)

     Yandex Go tajribasi: foydalanuvchi "Beshariq" deb yozadi → variantlar
     (Beshariq tumani, Beshariq MFY, Beshariq ko'chasi, ...) pastda ochiladi →
     birini tanlaydi → manzil inputiga to'liq nom yoziladi va xaritada nuqta
     qo'yiladi.

     NIMA UCHUN `ymaps.geocoder` ishlatiladi (qo'shimcha so'rov emas):
       * `suggest()` — Yandex serveri tomonidan variantlar ro'yxati (tez, bepul);
       * `find()`   — tanlangan variantning ANIQ koordinatasini beradi;
       * `geocode()` — shu sxema bilan, `reverse: true` orqali NUQTANI MANZILGA
         aylantiradi (xaritada nuqta bosilganda).

     Kalit: `GET /api/config` -> `config.maps.geocoder_api_key` (`.env` dan).
     Kalit YO'Q bo'lsa — `geocoder_enabled: false`; funksiyalar `null` qaytaradi
     va interfeys aniq xabar ko'rsatadi (soxta kalit QO'YILMAYDI).
  */
  const GEO_READY_MS = 300;   /* har bir bosilgan harfdan keyin kutish */

  function geocoderAvailable() {
    return !!(cfg && cfg.geocoder_enabled && cfg.geocoder_api_key);
  }

  /* `ymaps.geocoder` moduli yuklangan bo'lishi shart. Kalit bo'lmasa — null. */
  async function geocoder() {
    const c = cfg || (await config());
    if (!c || !c.geocoder_enabled || !c.geocoder_api_key) return null;
    let ymaps;
    try { ymaps = await loadScript(c.geocoder_api_key || c.api_key); }
    catch (e) { return null; }
    if (!ymaps || !ymaps.geocoder) return null;
    /* Modulni bir marta yuklaymiz (2-qariya — serverga murojaat qaytariladi). */
    if (!ymaps.geocoder.__loaded) {
      await new Promise(function (resolve) {
        try {
          ymaps.geocoder.load(ymaps.geocoder.API_COORDINATES, {
            /* Yandex tilimiz bilan bir xil bo'lsin. */
            lang: yandexLang()
          }, resolve);
        } catch (e) { resolve(); }
      });
      ymaps.geocoder.__loaded = true;
    }
    return ymaps.geocoder;
  }

  /** `ymaps.GeoObject` yoki oddiy JSON -> `{name, short, lat, lng, kind}`. */
  function toSuggestion(item) {
    const g = pickGeo(item);
    if (!g) return null;
    /* Yandex `displayName` "O'zbekiston, Toshkent shahri, Beshariq tumani, ..."
       shaklida — biz faqat eng muhim 3 qismni ko'rsatamiz (Yandex Go uslubi:
       qisqa variant ro'yxatda, to'liq nom inputda). */
    const full = g.displayName || g.name || "";
    return {
      name: full,
      short: full.split(",").slice(0, 3).join(",").trim(),
      lat: g.lat, lng: g.lng,
      kind: g.kind || "",
    };
  }

  /** Yandex API kalitidan qiymat (`.get()` yoki oddiy maydon). */
  function gVal(g, key) {
    if (!g) return "";
    try { if (typeof g.get === "function") { const v = g.get(key); if (v != null) return v; } }
    catch (e) { /* oddiy ob'ektga o'tamiz */ }
    return g[key] != null ? g[key] : "";
  }

  function pickGeo(item) {
    if (!item) return null;
    const g = item.GeoObject || item.geoObject || item;
    if (!g) return null;
    /* Koordinata: `ymaps.GeoObject.geometry.getCoordinates()` -> [UZUNLIK, KENGLIK]
       (yoki oddiy JSON shaklida `coordinates` / `geometry.coordinates`). */
    let coords = null;
    try {
      if (g.geometry && typeof g.geometry.getCoordinates === "function") {
        coords = g.geometry.getCoordinates();
      }
    } catch (e) { /* davom etamiz */ }
    if (!coords && g.coordinates) coords = g.coordinates;
    if (!coords && g.geometry && g.geometry.coordinates) coords = g.geometry.coordinates;
    if (!coords || coords.length < 2) return null;
    const lng = Number(coords[0]), lat = Number(coords[1]);
    if (!isFinite(lat) || !isFinite(lng)) return null;
    return {
      displayName: String(gVal(g, "displayName") || ""),
      name: String(gVal(g, "name") || ""),
      kind: String(gVal(g, "kind") || item.kind || ""),
      lat: lat, lng: lng,
    };
  }

  /**
   * AUTOCOMPLETE: matndan variantlar ro'yxati.
   * @param {string} query — foydalanuvchi yozgan matn (kamida 2 belgi)
   * @param {object} opts  — { bounds } (xarita ko'rsatgan hudud)
   * @returns {Promise<Array<{name,short,lat,lng}>>}
   */
  async function suggest(query, opts) {
    const q = String(query || "").trim();
    if (q.length < 2) return [];
    const gc = await geocoder();
    if (!gc) return [];
    /* Yandex geocoder API_COORDINATES rejimida `suggest()` GET so'rovi qiladi —
       klaviatura bosilganda har safar yubormaslik uchun KEDAJI. */
    const cache = (opts && opts.__cache) || (suggest.cache = suggest.cache || new Map());
    const ck = q.toLowerCase();
    if (cache.has(ck)) return cache.get(ck);
    try {
      const res = await gc.suggest(q, {
        /* Boshlang'ich nuqtaga yaqin natijalar oldinga — Yandex Go xabari. */
        ...((opts && opts.bounds) ? { bounds: opts.bounds } : {}),
      });
      const list = (res && res.GeoObjectCollection && res.GeoObjectCollection.metaDataProperty
        && res.GeoObjectCollection.metaDataProperty.GeocoderResponseMetaData
        && res.GeoObjectCollection.metaDataProperty.GeocoderResponseMetaData.result
        ? res.GeoObjectCollection.metaDataProperty.GeocoderResponseMetaData.result : []
      ).map(toSuggestion).filter(Boolean).slice(0, 8);
      if (cache.size > 60) cache.clear();
      cache.set(ck, list);
      return list;
    } catch (e) {
      return [];
    }
  }

  /**
   * ANIQ MANZIL + KOORDINATA (autocomplete tanlanganda).
   * @returns {Promise<{name,lat,lng}|null>}
   */
  async function geocode(query, opts) {
    const q = String(query || "").trim();
    if (!q) return null;
    const gc = await geocoder();
    if (!gc) return null;
    try {
      const res = await gc.find(gc.createSearchQuery(q));
      const first = res && res.GeoObjectCollection && res.GeoObjectCollection.items &&
                    res.GeoObjectCollection.items[0];
      return toSuggestion(first);
    } catch (e) { return null; }
  }

  /**
   * NUQTANI MANZILGA AYLANTIRISH (xaritada nuqta bosilganda — BAND 1).
   * @param {number} lat @param {number} lng
   * @returns {Promise<string>} — topilmasa "" (xato emas!)
   */
  async function reverseGeocode(lat, lng) {
    const gc = await geocoder();
    if (!gc || !isNum(lat) || !isNum(lng)) return "";
    try {
      const res = await gc.find(gc.createSearchQuery([Number(lng), Number(lat)]), {
        kind: "coordinates", results: 1
      });
      const g = pickGeo(res && res.GeoObjectCollection && res.GeoObjectCollection.items &&
                        res.GeoObjectCollection.items[0]);
      return g ? (g.displayName || g.name || "") : "";
    } catch (e) { return ""; }
  }

  /* ------------------------------------------------------------------ UI: takliflar
     `attachAutocomplete(input, opts)` — inputga ulanadigan kichik, mustaqil
     dropdown. `opts.onPick({name, short, lat, lng})` chaqiriladi.
     Koordinata inputlari yo'q — hammasi shu orqali.
  */
  function attachAutocomplete(input, opts) {
    const o = opts || {};
    const { el } = UI;
    if (!input) return null;

    const wrap = input.closest(".ac-wrap") || input.parentElement;
    if (!wrap) return null;
    if (!wrap.classList.contains("ac-wrap")) wrap.classList.add("ac-wrap");

    let listEl = wrap.querySelector(".ac-list");
    if (!listEl) {
      listEl = el("div", { class: "ac-list", role: "listbox" });
      wrap.append(listEl);
    }
    listEl.hidden = true;

    let timer = null;
    let items = [];
    let activeIdx = -1;
    let lastValue = "";

    function close() {
      listEl.hidden = true;
      listEl.innerHTML = "";
      items = [];
      activeIdx = -1;
      input.setAttribute("aria-expanded", "false");
    }

    function choose(item) {
      if (!item) return;
      input.value = item.name;
      lastValue = item.name;
      close();
      input.dispatchEvent(new Event("input", { bubbles: true }));
      if (typeof o.onPick === "function") o.onPick(item);
    }

    function render(list) {
      items = list || [];
      activeIdx = -1;
      if (!items.length) { close(); return; }
      listEl.innerHTML = "";
      items.forEach(function (it, i) {
        const btn = el("button", {
          type: "button", class: "ac-item", role: "option", tabindex: "-1",
          onclick: function () { choose(it); },
          onmousedown: function (e) { e.preventDefault(); choose(it); },
        }, [
          el("span", { class: "ac-item-icon", icon: "map" }),
          el("span", { class: "ac-item-text" }, [
            el("span", { class: "ac-item-name", text: it.short || it.name }),
          ]),
        ]);
        listEl.append(btn);
      });
      listEl.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }

    function highlight(i) {
      const nodes = listEl.querySelectorAll(".ac-item");
      nodes.forEach(function (n, k) { n.classList.toggle("is-active", k === i); });
      activeIdx = i;
    }

    function onInput() {
      const v = input.value;
      if (v === lastValue) return;
      clearTimeout(timer);
      if (!geocoderAvailable()) {
        if (typeof o.onUnavailable === "function") o.onUnavailable();
        return;
      }
      timer = setTimeout(async function () {
        const list = await suggest(v, o);
        /* Foydalanuvchi yozuv tugallamagan bo'lsa — natijani ko'rsatmaymiz. */
        if (input.value !== v) return;
        render(list);
        if (typeof o.onNoResult === "function" && (!list || !list.length)) o.onNoResult(v);
      }, GEO_READY_MS);
    }

    function onKeyDown(e) {
      if (listEl.hidden || !items.length) {
        if (e.key === "ArrowDown" && typeof o.onEnter === "function") o.onEnter(input.value);
        return;
      }
      if (e.key === "ArrowDown") { e.preventDefault(); highlight((activeIdx + 1) % items.length); }
      else if (e.key === "ArrowUp") { e.preventDefault(); highlight((activeIdx - 1 + items.length) % items.length); }
      else if (e.key === "Enter") {
        if (activeIdx >= 0) { e.preventDefault(); choose(items[activeIdx]); }
        else { close(); if (typeof o.onEnter === "function") o.onEnter(input.value); }
      }
      else if (e.key === "Escape") { close(); }
    }

    input.addEventListener("input", onInput);
    input.addEventListener("keydown", onKeyDown);
    input.addEventListener("blur", function () { setTimeout(close, 180); });
    input.setAttribute("autocomplete", "off");
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-autocomplete", "list");
    input.classList.add("ac-input");

    /* Dastlabki qiymat bo'lsa — dropdown ko'rsatilmaydi, faqat xarita nuqtasi. */
    lastValue = input.value || "";

    return {
      close,
      /** Dastlabki manzilni (DB'dan kelgan) autocomplete ro'yxatiga kiritish. */
      setValue(v) { lastValue = v || ""; input.value = v || ""; },
      /** Tanlangan variantni "serverdan kelgandek" qo'yish (marker ham yangilanadi). */
      pickExternal(item) { if (item) { input.value = item.name; lastValue = item.name; } },
    };
  }

  /* ------------------------------------------------------------------ tashqi API */
  return {
    config, mount, link, linkUrl, center, isNum, loadScript, SCRIPT_ID,
    /* BAND 1: autocomplete */
    suggest, geocode, reverseGeocode, attachAutocomplete, geocoderAvailable,
  };
})();
