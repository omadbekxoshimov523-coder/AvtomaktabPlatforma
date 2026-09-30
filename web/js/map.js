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
      return el("span", { class: "muted", text: label || "—" });
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

    return map;
  }

  /* ------------------------------------------------------------------ tashqi API */
  return { config, mount, link, linkUrl, center, isNum, loadScript, SCRIPT_ID };
})();
