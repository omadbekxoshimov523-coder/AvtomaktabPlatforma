/* UI yordamchilari: DOM yaratish, modal, toast, skeleton, bo'sh holatlar */
const UI = (function () {
  const { t } = I18N;

  /* ============================================================
     IKONKA REYESTRI (Lucide uslubi, 24x24 viewBox, stroke outline)
     ICONS: nom -> SVG ichki kontent (path d atributlari yoki ichki elem)
     ============================================================ */
  const ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    dashboard: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
    calendar: '<rect x="3" y="4" width="18" height="17" rx="2.5"/><path d="M8 2v4M16 2v4M3 9h18"/>',
    lessons: '<rect x="3" y="3" width="18" height="18" rx="2.5"/><path d="M3 9h18M9 3v18"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M17.5 14a6.5 6.5 0 0 1 4 6"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    student: '<circle cx="10" cy="7.5" r="3.5"/><path d="M3 20a7 7 0 0 1 14 0H3Z"/>',
    instructor: '<rect x="4" y="3" width="16" height="18" rx="2.5"/><path d="M9 8h6M9 12h6M9 16h3"/>',
    shield: '<path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/>',
    bell: '<path d="M18 9a6 6 0 0 0-12 0c0 6-2.5 7-2.5 7h17S18 15 18 9"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 2.7h-4l-.5 2.9a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12a7 7 0 0 0 .1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2l.5 2.9h4l.5-2.9a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6A7 7 0 0 0 19 12z"/>',
    logout: '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3"/><path d="M10 17l-5-5 5-5M5 12h10"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    minus: '<path d="M5 12h14"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>',
    check: '<path d="M4 12.5l5 5L20 6.5"/>',
    check_circle: '<circle cx="12" cy="12" r="9"/><path d="M8.5 12.2l2.3 2.3L15.6 9.4"/>',
    alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v4M12 17.5v.01"/>',
    alert_circle: '<circle cx="12" cy="12" r="9"/><path d="M12 8v4.5M12 16v.01"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.01"/>',
    file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    file_text: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    download: '<path d="M12 4v11M7 11l5 5 5-5"/><path d="M4 19h16"/>',
    upload: '<path d="M12 15V4M7 9l5-5 5 5"/><path d="M4 19h16"/>',
    edit: '<path d="M4 20h4L19.5 8.5a2.1 2.1 0 0 0-3-3L5 17z"/><path d="M13 6l3 3"/>',
    trash: '<path d="M4 6h16M9 6V4h6v2M6 6l1 14h10l1-14"/><path d="M10 10v6M14 10v6"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l5 5"/>',
    filter: '<path d="M3 5h18M6 12h12M10 19h4"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>',
    phone: '<path d="M6 3h4l1.5 4.5L9 9.5a12 12 0 0 0 5.5 5.5l2-2.5L21 14v4a2 2 0 0 1-2 2A16 16 0 0 1 4 5a2 2 0 0 1 2-2z"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3.5 7.5 12 13l8.5-5.5"/>',
    map: '<path d="M9 3 3.5 5.2v15L9 18l6 2.2 5.5-2.2v-15L15 5.2z"/><path d="M9 3v15M15 5.2V20"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20"/>',
    key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l8-8M15 6l3 3M13 8l2 2"/>',
    lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    tools: '<path d="M14.5 6.5a4 4 0 0 0-5.5 5.5L4 17v3h3l5-5a4 4 0 0 0 5.5-5.5l-2.6 2.6-2.1-.8-.8-2.1z"/>',
    car: '<rect x="2" y="8" width="20" height="8" rx="2"/><path d="M4 11l1.5-4h13L21 11"/><path d="M7 16a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM17 16a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z"/>',
    undo: '<path d="M9 6 4 11l5 5"/><path d="M4 11h11a5 5 0 0 1 0 10h-2"/>',
    camera: '<path d="M4 7h3l2-2.5h6L17 7h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="3.5"/>',
    save: '<path d="M5 3h11l4 4v14H4V3z"/><path d="M8 3v6h8V3M8 21v-7h8v7"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    message: '<path d="M4 5h16v11H9l-5 4z"/>',
    play: '<path d="M7 5v14l11-7z"/>',
    pause: '<path d="M7 5h3v14H7zM14 5h3v14h-3z"/>',
    chart: '<path d="M4 20V10M10 20V4M16 20v-7M21 20H3"/>',
    graduation: '<path d="M2.5 9 12 4l9.5 5L12 14z"/><path d="M6.5 11.5V16c0 1.5 2.5 3 5.5 3s5.5-1.5 5.5-3v-4.5"/><path d="M21.5 9v5"/>',
    star: '<path d="M12 3l2.7 5.8 6.3.8-4.6 4.4 1.2 6.2L12 17.4 6.4 20.2l1.2-6.2L3 9.6l6.3-.8z"/>',
    wallet: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M15.5 14.5h.01"/>',
    checkup: '<path d="M13 3 4 14h6l-1 7 9-11h-6z"/>',
    warn: '<path d="M12 3l10 18H2z"/>',
    arrow_left: '<path d="M15 5l-7 7 7 7"/>',
    arrow_right: '<path d="M9 5l7 7-7 7"/>',
    dot: '<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>',
    inbox: '<path d="M3 4h18v13H3z"/><path d="M3 10h5.5l2 2.5h3l2-2.5H21"/>',
    pie: '<path d="M12 3a9 9 0 1 0 9 9h-9z"/><path d="M12 3v9h9"/>',
    list: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h.01M4 12h.01M4 18h.01"/>',
    building: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 8h1M14 8h1M9 12h1M14 12h1M9 16h1M14 16h1"/><path d="M8 21v-2.5h8V21"/>',
  };

  /* SVG ikonka elementini qaytaradi: ic("calendar", 18) */
  function ic(name, size = 18, { stroke = 1.8 } = {}) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", size);
    svg.setAttribute("height", size);
    svg.setAttribute("class", "ico");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", stroke);
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    const inner = ICONS[name] || ICONS.dot;
    if (inner.indexOf("<") === 0) {
      const tmp = document.createElementNS(ns, "g");
      tmp.setAttribute("dangerouslySetInnerHTML", "");
      // ichki path'larni qo'lda quramiz
      const g = document.createElementNS(ns, "g");
      svg.appendChild(g);
      // pixie: inner XML stringni parse qilamiz
      const xml = "<svg xmlns='" + ns + "'>" + inner + "</svg>";
      const parser = new DOMParser();
      const doc = parser.parseFromString(xml, "image/svg+xml");
      const src = doc.documentElement;
      for (const child of Array.from(src.childNodes)) {
        if (child.nodeType === 1) svg.appendChild(svg.ownerDocument.adoptNode(child.cloneNode(true)));
      }
    }
    return svg;
  }

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    let ico = null;
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") node.className = v;
      else if (k === "dataset") Object.assign(node.dataset, v);
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else if (k === "text") node.textContent = v;
      else if (k === "icon") ico = v; /* Task 1: emoji -> SVG */
      else if (v !== undefined && v !== null && k !== "html") node.setAttribute(k, v);
    }
    const kids = Array.isArray(children) ? children : [children];
    for (const c of kids) {
      if (c === null || c === undefined) continue;
      if (typeof c === "string") node.appendChild(document.createTextNode(c));
      else if (Array.isArray(c)) node.append(...c.filter(Boolean));
      else node.appendChild(c);
    }
    if (ico) node.prepend(ic(ico)); /* ikonkadan so'ng matn */
    return node;
  }

  function toast(message, type = "success") {
    let host = document.getElementById("toast-host");
    if (!host) {
      host = el("div", { id: "toast-host", class: "toast-host" });
      document.body.appendChild(host);
    }
    const box = el("div", { class: `toast toast-${type}`, text: message });
    host.appendChild(box);
    requestAnimationFrame(() => box.classList.add("show"));
    // Uzun (ko'p qatorli) xabarlar — masalan tasdiqlashda qaysi qoida
    // bloklagani — 3.2 soniyada o'qib bo'lmaydi, vaqtni matn uzunligiga bog'laymiz.
    const ttl = Math.min(9000, 3200 + String(message || "").length * 45);
    setTimeout(() => {
      box.classList.remove("show");
      setTimeout(() => box.remove(), 300);
    }, ttl);
  }

  function errToast(e) {
    const code = e && e.code;
    let msg = I18N.errorText(code) || I18N.t("err.generic");
    // Backend ko'p qoidali xatolarda aniq sabablarni `params.errors` da yuboradi
    // (masalan session.rules_violated -> ["intersects_break"]). Ularni ham
    // ko'rsatmasak, admin "Mashg'ulot yaratib bo'lmaydi" deb umumiy xabarni
    // ko'rib, tugma buzilgan deb o'ylaydi — aslida qaysi qoida bloklagani
    // ko'rinmay qoladi. Har bir sababni alohida qatorga chiqaramiz.
    const params = (e && e.params) || {};
    const reasons = [].concat(params.errors || []).filter(Boolean);
    if (reasons.length) {
      const lines = [];
      for (const r of reasons) {
        const d = I18N.errorText(r);
        if (d) lines.push("• " + d);
      }
      if (lines.length) msg += "\n" + lines.join("\n");
    }
    toast(msg, "error");
  }

  function modal(title, content, { wide = false, onClose } = {}) {
    const overlay = el("div", { class: "modal-overlay" });
    const card = el("div", { class: "modal" + (wide ? " modal-wide" : "") });
    const head = el("div", { class: "modal-head" },
      [el("h3", { text: title }),
       el("button", { class: "btn-ghost", text: "✕", onclick: () => close() })]);
    const body = el("div", { class: "modal-body" });
    body.append(...(Array.isArray(content) ? content.filter(Boolean) : [content]));
    card.append(head, body);
    overlay.append(card);
    overlay.addEventListener("click", (ev) => { if (ev.target === overlay) close(); });
    document.body.appendChild(overlay);
    document.body.classList.add("modal-open");
    function close() {
      overlay.remove();
      document.body.classList.remove("modal-open");
      if (onClose) onClose();
    }
    overlay.close = close;
    overlay.body = body;
    return overlay;
  }

  function confirmDialog(message, onYes, { danger = false, yesText, title, noText } = {}) {
    const m = modal("—", [
      el("p", { class: "confirm-text", text: message }),
      el("div", { class: "row gap end" }, [
        el("button", { class: "btn btn-light", text: noText || t("common.cancel"), onclick: () => m.close() }),
        el("button", {
          class: "btn " + (danger ? "btn-danger" : "btn-primary"),
          text: yesText || t("common.confirm"),
          onclick: () => { m.close(); onYes && onYes(); },
        }),
      ]),
    ]);
    m.querySelector(".modal-head h3").textContent = title || (danger ? "⚠️" : t("common.confirm"));
    return m;
  }

  function spinner() {
    return el("div", { class: "spinner-wrap" }, [el("div", { class: "spinner" })]);
  }

  function emptyState(icon, text, sub) {
    return el("div", { class: "empty-state" }, [
      el("div", { class: "empty-icon", text: icon }),
      el("p", { text }),
      sub ? el("p", { class: "empty-sub", text: sub }) : null,
    ]);
  }

  function skeleton(count = 3) {
    const items = [];
    for (let i = 0; i < count; i++) items.push(el("div", { class: "skeleton-line" }));
    return el("div", { class: "skeleton", children: items });
  }

  function badge(status, text) {
    const map = {
      active: "b-green", repair: "b-orange", checkup: "b-yellow", inactive: "b-red",
      scheduled: "b-blue", ongoing: "b-cyan", completed: "b-green", cancelled: "b-red",
      present: "b-green", late: "b-orange", absent: "b-red", unmarked: "b-gray",
      pending: "b-yellow", approved: "b-green", rejected: "b-red", cancelled: "b-gray",
      rescheduled: "b-blue", blocked: "b-red", archived: "b-gray", blue: "b-blue",
    };
    return el("span", { class: "badge " + (map[status] || "b-gray"), text: text || status });
  }

  function statusText(status) {
    const tMap = {
      active: t("car.status.active"), repair: t("car.status.repair"),
      checkup: t("car.status.checkup"), inactive: t("car.status.inactive"),
      scheduled: t("lesson.status.scheduled"), ongoing: t("lesson.status.ongoing"),
      completed: t("lesson.status.completed"), cancelled: t("lesson.status.cancelled"),
      present: t("lesson.present"), late: t("lesson.late"), absent: t("lesson.absent"),
      unmarked: t("lesson.unmarked"), pending: t("req.pending"), approved: t("req.approved"),
      rejected: t("req.rejected"), rescheduled: t("req.rescheduled"),
    };
    return tMap[status] || status;
  }

  function avatar(user, size = 40) {
    const initials = ((user.first_name || "?")[0] + (user.last_name || "")[0] || "?");
    const base = `width:${size}px;height:${size}px;font-size:${Math.round(size * 0.4)}px`;
    // Profil rasmi yoki bosh harfli avatar (Modul 2)
    if (user && user.profile_image) {
      const wrap = el("div", { class: "avatar", style: `${base};background:var(--surface-2);overflow:hidden` });
      const img = el("img", {
        class: "avatar-img", src: user.profile_image, alt: initials.toUpperCase(),
        style: "width:100%;height:100%;object-fit:cover;display:block",
      });
      img.addEventListener("error", () => {
        img.remove();
        wrap.textContent = initials.toUpperCase();
        wrap.style.background = "";
      });
      wrap.append(img);
      return wrap;
    }
    return el("div", { class: "avatar", style: base, text: initials.toUpperCase() });
  }

  function carPhoto(src, size = 120) {
    // M5: avtomobil fotosurati (yo'q bo'lsa 🚗 belgili fallback)
    const style = `width:${size}px;height:${size}px;font-size:${Math.round(size * 0.45)}px`;
    if (!src) return el("div", { class: "car-photo car-photo-empty", style, text: "🚗" });
    const wrap = el("div", { class: "car-photo", style: `${style};overflow:hidden` });
    const img = el("img", {
      class: "car-photo-img", src, alt: "",
      style: "width:100%;height:100%;object-fit:cover;display:block",
    });
    img.addEventListener("error", () => {
      img.remove();
      wrap.classList.add("car-photo-empty");
      wrap.textContent = "🚗";
    });
    wrap.append(img);
    return wrap;
  }

  function field(label, control, opts = {}) {
    const wrap = el("label", { class: "field" + (opts.class ? " " + opts.class : "") }, [
      el("span", { class: "field-label", text: label, dataset: opts.i18n ? { i18n: label } : {} }),
      control,
    ]);
    if (opts.hint) wrap.append(el("small", { class: "field-hint", text: opts.hint }));
    return wrap;
  }

  function input(attrs = {}) {
    return el("input", { class: "input", ...attrs });
  }

  function select(options, selected = "", attrs = {}) {
    const sel = el("select", { class: "input", ...attrs });
    for (const [val, label] of Object.entries(options)) {
      sel.append(el("option", { value: val, text: label, selected: String(val) === String(selected) ? "selected" : undefined }));
    }
    return sel;
  }

  /* ============================================================
     M13-M9: Toggle-switch (yoqish/o'chirish) — qayta ishlatiladigan
     komponent. Platformadagi BARCHA yoqish/o'chirish elementlari
     shu komponentdan foydalanadi (checkbox o'rniga).
     ============================================================ */
  function toggleSwitch(checked, onChange, label = "") {
    const sw = el("button", {
      type: "button",
      class: "toggle" + (checked ? " on" : ""),
      role: "switch",
      "aria-checked": checked ? "true" : "false",
      onclick: () => {
        const next = sw.getAttribute("aria-checked") !== "true";
        sw.setAttribute("aria-checked", next ? "true" : "false");
        sw.classList.toggle("on", next);
        if (onChange) onChange(next);
      },
    }, [el("span", { class: "knob" })]);
    if (label) sw.setAttribute("aria-label", label);
    return sw;
  }

  /* Bir qatorga joylashgan toggle: chapda nom+tavsif, o'ngda switch. */
  function toggleRow({ title, desc, checked, onChange } = {}) {
    const sw = toggleSwitch(checked, onChange, title);
    return el("div", { class: "toggle-row" }, [
      el("div", { class: "t-info" }, [
        el("div", { class: "t-title", text: title }),
        desc ? el("div", { class: "t-desc", text: desc }) : null,
      ]),
      sw,
    ]);
  }

  // OSM xarita havolasi
  function mapLink(lat, lng, label) {
    if (!lat || !lng) return el("span", { class: "muted", text: label || "—" });
    return el("a", {
      class: "link", href: `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=17/${lat}/${lng}`,
      target: "_blank", rel: "noopener", text: label || "🗺️",
    });
  }

  function callLink(phone) {
    if (!phone) return el("span", { class: "muted", text: "—" });
    return el("a", { class: "btn btn-primary btn-sm", href: `tel:${phone.replace(/[^+0-9]/g, "")}`, icon: "phone", text: "" + t("lesson.call") });
  }

  /* ============================================================
     M6: Bosh sahifa / Bugun — timeline, checklist, quick links, bildirishnomalar
     ============================================================ */
  function _hm(t) {
    if (!t) return 0;
    const [h, m] = String(t).split(":").map(Number);
    return (h || 0) * 60 + (m || 0);
  }

  /* Vertikal soatlik timeline + joriy vaqt chizig'i. sessions: [{id,start_time,end_time,status,...}] */
  function timeline(sessions, { onOpen, dayStart = 8 * 60, dayEnd = 22 * 60 } = {}) {
    const total = Math.max(dayEnd - dayStart, 60);
    const now = new Date();
    const nowMin = now.getHours() * 60 + now.getMinutes();
    const wrap = el("div", { class: "timeline" });
    for (let h = Math.ceil(dayStart / 60); h <= Math.floor(dayEnd / 60); h++) {
      const p = (((h * 60) - dayStart) / total) * 100;
      wrap.append(el("div", { class: "tl-hour", style: "top:" + p + "%" }, [
        el("span", { class: "tl-hour-label", text: String(h).padStart(2, "0") + ":00" }),
      ]));
    }
    if (nowMin >= dayStart && nowMin <= dayEnd) {
      const p = ((nowMin - dayStart) / total) * 100;
      wrap.append(el("div", { class: "now-line", style: "top:" + p + "%" }, [
        el("span", { class: "now-line-label", text: t("today.now") + " " + String(now.getHours()).padStart(2, "0") + ":" + String(now.getMinutes()).padStart(2, "0") }),
      ]));
    }
    (sessions || []).forEach((s) => {
      const sm = _hm(s.start_time);
      const em = _hm(s.end_time) || sm + 60;
      let top = ((sm - dayStart) / total) * 100;
      let height = ((em - sm) / total) * 100;
      if (top < 0) { height += top; top = 0; }
      if (top > 100 || height <= 0) return;
      height = Math.min(height, 100 - top);
      height = Math.max(height, 2.5);
      const meta = [];
      if (s.instructor_name) meta.push(s.instructor_name);
      if (s.car_plate_snapshot) meta.push(s.car_plate_snapshot);
      if (s.student_count != null) meta.push(s.student_count + "/" + (s.capacity_snapshot != null ? s.capacity_snapshot : "?"));
      wrap.append(el("div", {
        class: "tl-session st-" + (s.status || ""),
        style: "top:" + top + "%;height:" + height + "%",
        onclick: () => onOpen && onOpen(s),
        title: (s.start_time || "") + "–" + (s.end_time || "") + " " + (meta.join(" · ") || ""),
      }, [
        el("div", { class: "tl-time", text: (s.start_time || "—") + "–" + (s.end_time || "—") }),
        el("div", { class: "tl-meta", icon: "car", text: meta.join(" · ") || t("lesson.lesson") }),
      ]));
    });
    return wrap;
  }

  /* Checklist: [ {done, text, sub?, badge?:[status,label], onclick?} ] */
  function checklist(items) {
    const list = el("div", { class: "checklist" });
    let any = false;
    (items || []).forEach((it) => {
      if (!it) return;
      any = true;
      const right = it.badge ? badge(it.badge[0], it.badge[1]) : null;
      list.append(el("div", { class: "cl-item" + (it.done ? " done" : ""), onclick: it.onclick }, [
        el("span", { class: "cl-box", text: it.done ? "✓" : "" }),
        el("div", { class: "f1" }, [
          el("div", { class: "cl-text", text: it.text }),
          it.sub ? el("div", { class: "cl-sub", text: it.sub }) : null,
        ]),
        right,
      ]));
    });
    if (!any) list.append(emptyState("✅", t("today.nothing"), t("today.nothing_sub")));
    return list;
  }

  /* Tezkor havolalar: [ {icon, label, onclick} ] */
  function quickLinks(items) {
    const row = el("div", { class: "quick-links" });
    (items || []).forEach((it) => {
      row.append(el("button", { class: "ql-btn", onclick: it.onclick }, [
        el("span", { class: "ql-icon", text: it.icon }),
        el("span", { class: "ql-label", text: it.label }),
      ]));
    });
    return row;
  }

  /* So'nggi bildirishnomalar (kabinetdagilari): onOpen(n, dataJson) */
  function notifMini(notifs, { onOpen, limit = 5 } = {}) {
    const list = el("div", { class: "notif-mini" });
    const items = (notifs || []).slice(0, limit);
    if (!items.length) {
      list.append(emptyState("🔔", t("notif.empty")));
      return list;
    }
    items.forEach((n) => {
      let data = {};
      try { data = JSON.parse(n.data || "{}") || {}; } catch (e) {}
      const roleLabel = (r) => r === "student" ? t("auth.role_student") : r === "instructor" ? t("auth.role_instructor") : r === "admin" ? t("auth.role_admin") : t("notif.system");
      const senderName = n.sender_id
        ? [n.sender_first_name, n.sender_last_name].filter(Boolean).join(" ") || t("notif.unknown")
        : t("notif.system");
      const senderRole = n.sender_role || (n.sender_id ? "user" : "") || "system";
      const senderAvatar = n.sender_id
        ? avatar({ first_name: n.sender_first_name || "?", last_name: n.sender_last_name || "",
                   profile_image: n.sender_profile_image || "" }, 26)
        : el("div", { class: "avatar notif-sys-avatar", style: "width:26px;height:26px;font-size:12px", text: "⚙" });
      list.append(el("div", {
        class: "notif-item" + (n.is_read ? "" : " unread"),
        onclick: () => onOpen && onOpen(n, data),
      }, [
        el("div", { class: "notif-item-row" }, [
          senderAvatar,
          el("div", { class: "f1" }, [
            el("div", { class: "notif-title", text: I18N.notifLabel(n.title) }),
            el("div", { class: "notif-meta" }, [
              el("span", { class: "notif-sender", text: senderName }),
              el("span", { class: "notif-role " + senderRole, text: roleLabel(senderRole) }),
            ]),
          ]),
        ]),
        el("div", { class: "notif-body", text: I18N.notifText(n, data) }),
        el("div", { class: "notif-time", icon: "clock", text: "" + I18N.fmtDateTime(n.created_at) }),
      ]));
    });
    return list;
  }

  return { el, toast, errToast, modal, confirmDialog, spinner, emptyState, skeleton, badge, statusText, avatar, carPhoto, field, input, select, mapLink, callLink, timeline, checklist, quickLinks, notifMini, toggleSwitch, toggleRow };
})();

/* `const UI` global leksik o'zgaruvchi bo'lgani uchun window.UI da ko'rinmaydi.
   Boshqa fayllar (app.js, shared.js, views-*.js) window.UI dan o'qiydi — shuning
   uchun uni window ga ham yozamiz. */
window.UI = UI;