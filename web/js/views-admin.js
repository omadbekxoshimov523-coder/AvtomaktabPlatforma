/* ADMIN ko'rinishlari: Dashboard, Yangi baza, Talabalar, Instruktorlar,
   Avtomobillar, Mashg'ulotlar, Kalendar, So'rovlar, Hisobotlar, Audit,
   Bildirishnomalar, Sozlamalar, Backup */
window.AdminViews = (function () {
  const { t, fmtDate, fmtDateTime, errorText, monthShort } = I18N;
  const UI = window.UI;
  const { el, toast, errToast, badge, statusText, avatar, carPhoto, field, input, select, modal, emptyState, spinner, confirmDialog, callLink, mapLink, timeline, checklist, notifMini, toggleRow } = UI;

  /* Rol nomini tarjima qilish (BAND 22: profil kartochkasida ishlatiladi). */
  function roleName(role) {
    const map = { student: "auth.role_student", instructor: "auth.role_instructor", admin: "auth.role_admin" };
    const key = map[role];
    return (key ? t(key) : "") || String(role || "");
  }

  /* M9: vaqtga daqiqa qo'shish — "15:00" + 90 -> "16:30" */
  function addMinutesTo(time, minutes) {
    try {
      const [h, m] = String(time || "").split(":").map(Number);
      if (isNaN(h) || isNaN(m)) return time || "";
      const d = new Date(2000, 0, 1, h, m + minutes);
      return d.toTimeString().slice(0, 5);
    } catch (e) {
      return time || "";
    }
  }

  /* M9: platforma standartini (mashg'ulot davomiyligi) settings'dan oladi */
  async function platformDuration() {
    try {
      const r = await API.get("admin/settings");
      return Math.max(15, parseInt((r.settings && r.settings.lesson_duration_min), 10) || 90);
    } catch (e) {
      return 90;
    }
  }

  /* ============================ DASHBOARD / BOSH SAHIFA ============================ */
  async function dashboard() {
    const data = (await API.get("admin/dashboard")).dashboard;
    const cards = [
      ["student", t("stat.students"), data.students],
      ["instructor", t("stat.instructors"), data.instructors],
      ["car", t("stat.cars"), data.cars],
      ["calendar", t("stat.today_sessions"), data.today_sessions],
      ["inbox", t("stat.pending_requests"), data.pending_requests],
      ["check_circle", t("stat.active_instructors"), data.active_instructors],
      ["tools", t("stat.cars_repair"), data.cars_repair],
      ["users", t("stat.total_users"), data.total_users],
    ];
    const grid = el("div", { class: "grid-stats" });
    cards.forEach(([icon, label, val]) => grid.append(
      el("div", { class: "stat-card" }, [
        el("div", { class: "stat-icon", icon }),
        el("div", {}, [el("div", { class: "stat-value", text: String(val) }), el("div", { class: "stat-label", text: label })]),
      ])));

    // M6: haftalik statistika (umumiy holat)
    const weekly = el("div", { class: "grid-stats grid-stats-compact mt" });
    [
      ["calendar", t("week.sessions"), data.week_sessions],
      ["check_circle", t("week.done"), data.week_done],
      ["clock", t("week.hours"), data.week_hours],
      ["inbox", t("week.requests"), data.week_requests],
      ["user", t("week.new_users"), data.week_new_users],
    ].forEach(([icon, label, val]) => weekly.append(el("div", { class: "stat-card" }, [
      el("div", { class: "stat-icon", icon }),
      el("div", {}, [el("div", { class: "stat-value", text: String(val) }), el("div", { class: "stat-label", text: label })]),
    ])));

    // So'nggi bildirishnomalar + tezkor havolalar
    const notifRes = await API.get("me/notifications");
    const notifCard = el("div", { class: "card" }, [
      el("div", { class: "row between mb" }, [
        el("h3", { class: "card-title", icon: "bell", text: " " + t("home.recent_notifications") }),
        el("button", { class: "link-btn", text: t("home.mark_read"), onclick: async () => {
          await API.post("me/notifications/read", {});
          await App.refreshMe();
          App.refreshView();
        } }),
      ]),
      notifMini(notifRes.notifications, { onOpen: async (n, data) => {
        if (!n.is_read) { await API.post("me/notifications/read", { id: n.id }); await App.refreshMe(); App.refreshView(); }
        Shared.openNotif(n, data);
      } }),
    ]);
    // M1: Tezkor havolalar kartasi olib tashlandi

    // M8: haftalik faollik grafiki (dizayn tizimiga mos) — kunlar bo'yicha darslar
    const byDay = data.week_sessions_by_day || [];
    const maxC = Math.max(1, ...byDay.map((b) => b.count));
    const wdShort = ["week.day_mon", "week.day_tue", "week.day_wed", "week.day_thu", "week.day_fri", "week.day_sat", "week.day_sun"];
    const chartCard = el("div", { class: "card" }, [
      el("div", { class: "row between mb" }, [
        el("h3", { class: "card-title", text: "\u{1f4ca} " + t("week.chart_title") }),
        el("span", { class: "muted sm", text: String(data.week_sessions) + " " + t("week.sessions").toLowerCase() }),
      ]),
      el("div", { class: "bar-chart" }, byDay.map((b, i) => {
        const h = Math.max(6, Math.round((b.count / maxC) * 150));
        return el("div", {
          class: "chart-col" + (b.date === Shared.todayISO() ? " today" : ""),
          title: fmtDate(b.date) + ": " + b.count,
        }, [
          el("div", { class: "chart-val", text: String(b.count) }),
          el("div", { class: "chart-bar", style: "height:" + h + "px" }),
          el("div", { class: "chart-label", text: t(wdShort[i] || "week.day_mon") }),
        ]);
      })),
    ]);

    // M8: bugungi mashg'ulotlar jadvali (matn aniq o'qilishi uchun .tbl)
    const sessList = data.today_sessions_list || [];
    const sessCard = el("div", { class: "card" }, [
      el("h3", { class: "card-title", text: "\u{1f4c5} " + t("dash.today_sessions_title") }),
    ]);
    if (!sessList.length) {
      sessCard.append(emptyState("\u{1f4ed}", t("today.no_sessions")));
    } else {
      const tbl = el("table", { class: "tbl" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "\u{1f552}" }), el("th", { text: t("lesson.instructor") }),
          el("th", { text: "\u{1f697} " + t("lesson.car") }), el("th", { text: "\u{1f465} " + t("car.capacity") }), el("th", { text: t("common.status") }),
        ])]),
        el("tbody", {}, sessList.map((s) => el("tr", { class: "row-click", onclick: () => Shared.openSession(s.id, "admin") }, [
          el("td", { text: `${s.start_time}\u2013${s.end_time}` }),
          el("td", { text: s.instructor_name || "\u2014" }),
          el("td", { class: "muted", text: (s.car_name_snapshot || "\u2014") + (s.car_plate_snapshot ? " \u00b7 " + s.car_plate_snapshot : "") }),
          el("td", { text: (s.student_count || 0) + "/" + (s.capacity_snapshot || 0) }),
          el("td", {}, [badge(s.status, statusText(s.status))]),
        ]))),
      ]);
      sessCard.append(el("div", { class: "table-wrap" }, [tbl]));
    }

    return el("div", {}, [grid, weekly, el("div", { class: "grid-2 mt" }, [chartCard, sessCard]), notifCard]);
  }

  function sessionCard(s) {
    return el("div", {
      class: "session-card " + s.status, dataset: { sid: s.id },
      onclick: () => Shared.openSession(s.id, "admin"),
    }, [
      el("div", { class: "row between" }, [
        el("div", { class: "session-time", text: `${s.start_time}\u2013${s.end_time}` }),
        badge(s.status, statusText(s.status)),
      ]),
      el("div", { class: "session-meta" }, [
        el("div", { icon: "instructor", text: "" + (s.instructor_name || "") }),
        el("div", { icon: "car", text: "" + (s.car_name_snapshot || "\u2014") + " \u00b7 " + (s.car_plate_snapshot || "") }),
        el("div", { class: "session-count", icon: "users", text: "" + (s.student_count || 0) + "/" + s.capacity_snapshot }),
      ]),
    ]);
  }

  /* ============================ YANGI BAZA ============================ */
  async function base() {
    const wrap = el("div", {}, []);
    const searchI = input({ type: "search", placeholder: t("common.search") + "..." });
    const roleSel = select({ "": t("common.all"), student: t("auth.role_student"), instructor: t("auth.role_instructor"), admin: t("auth.role_admin") });
    const statusSel = select({ "": t("common.all"), active: t("student.status.active"), blocked: t("stat.blocked"), archived: t("stat.archived") });

    const toolbar = el("div", { class: "row wrap between mb" }, [
      el("div", { class: "row wrap gap-sm" }, [searchI, roleSel, statusSel]),
      el("div", { class: "row wrap gap-sm" }, [
        el("button", { class: "btn btn-primary", icon: "plus", text: "" + t("nav.students"),
          onclick: () => Shared.openUserForm("student") }),
        el("button", { class: "btn btn-cyan", icon: "plus", text: "" + t("nav.instructors"),
          onclick: () => Shared.openUserForm("instructor") }),
        el("button", { class: "btn btn-light", text: "\u26a1 " + t("student.bulk"),
          onclick: () => bulkModal() }),
        /* MODUL 3: "Import CSV" BUTUNLAY OLIB TASHLANDI — endi faqat
           "Hisobotlar" bo'limida (Hisobotlar > Import tab). */
        el("button", { class: "btn btn-light", icon: "chart",
          title: t("base.go_reports_hint"), text: "" + t("base.go_reports"),
          onclick: () => goReportsFor("") }),
      ]),
    ]);
    const tblHost = el("div", { id: "users-table", });
    tblHost.append(UI.spinner());
    wrap.append(toolbar, tblHost);

    async function load() {
      const q = new URLSearchParams({ role: roleSel.value, status: statusSel.value, q: searchI.value });
      const res = await API.get("admin/users?" + q.toString());
      fill(res.users);
    }
    function fill(users) {
      const host = document.getElementById("users-table");
      host.innerHTML = "";
      if (!users.length) { host.append(emptyState("\u{1f465}", t("instructor.students_empty"))); return; }
      const tbl = el("table", { class: "tbl" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("common.name") }), el("th", { text: t("common.role") }),
          el("th", { text: t("common.phone") }), el("th", { text: t("common.filter") }),
          el("th", { text: t("common.status") }), el("th", { text: t("common.actions") }),
        ])]),
        el("tbody", {}, users.map((u) => {
          const info = [];
          if (u.role === "student" && u.student) info.push(u.student.group_name);
          if (u.role === "instructor" && u.instructor) {
            info.push(u.car ? u.car.brand + " " + u.car.model : t("car.not_assigned"));
          }
          return el("tr", {}, [
            el("td", {}, [el("div", { class: "user-cell" }, [avatar(u, 34), el("div", {}, [
              el("div", { class: "cell-strong", text: `${u.first_name} ${u.last_name}` }),
              el("div", { class: "muted", text: u.login })])])]),
            el("td", { text: roleName(u.role) }),
            el("td", { text: u.phone || "\u2014" }),
            el("td", { text: info.join(", ") || "\u2014" }),
            el("td", {}, [statusBadge(u)]),
            el("td", {}, [el("div", { class: "actions" }, [
              el("button", { class: "btn btn-light btn-sm", text: "\u{1f464}", title: "" + t("users.view_profile"),
                onclick: () => openUserProfile(u.id, load) }),
              el("button", { class: "btn btn-light btn-sm", text: "\u270f\ufe0f", onclick: () => editUser(u) }),
              el("button", { class: "btn btn-light btn-sm", text: "\u{1f511}", title: "" + t("users.cred_title"),
                onclick: () => Shared.openUserCredentialsManager(u, load) }),
              u.role === "instructor" && u.instructor ? el("button", { class: "btn btn-light btn-sm", text: "\u{1f697}", onclick: () => Shared.openUserForm("instructor", u) }) : null,
              /* MODUL 2/3: bloklash/blokdan chiqarish + arxivlash/arxivdan
                 chiqarish — talaba, instruktor va admin uchun BIR XIL. */
              ...userStatusActions(u, load),
            ])]),
          ]);
        })),
      ]);
      host.append(tbl);
    }
    function statusBadge(u) {
      /* `statusText("archived")` tarjima jadvalida YO'Q edi — nishon
         "archived" (inglizcha so'z) deb chiqardi. Umumiy yordamchiga
         ko'chirildi: uchala rol jadvali ham bir xil nishonni ishlatadi. */
      return userStatusBadge(u);
    }
    function editUser(u) { Shared.openUserForm(u.role, u); }
    /* MODUL 5: 🔑 enda "Yangi parol o'rnatish" emas, balki LOGIN+PAROLNI
       KO'RISH va birga o'zgartirish oynasi (`openUserCredentialsManager`).
       Parol avtomatik generatsiya qilish esa oyna ichidagi
       "Yangi parol" tugmasi orqali bajariladi. */
    [searchI, roleSel, statusSel].forEach((c) => c.addEventListener("change", load));
    let timer;
    searchI.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(load, 350); });
    load();
    return wrap;
  }

  function bulkModal() {
    const countI = select({ "10": "10", "50": "50", "100": "100", "500": "500", "1000": "1000" }, "10");
    const m = modal("\u26a1 " + t("student.bulk"), [
      field(t("student.bulk") + " \u2014 " + t("common.count"), countI),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: t("common.create"),
          onclick: async () => {
            m.close();
            try {
              const res = await API.post("admin/users/bulk", { count: parseInt(countI.value) });
              const list = el("div", {});
              res.created.forEach((cr, i) => list.append(el("div", { class: "kv" }, [
                el("span", { class: "k", text: `#${i + 1}` }), el("span", { class: "v", text: cr.login + " / " + cr.password }),
              ])));
              modal("\u2705 " + t("misc.success") + ` (${res.count})`, [list, el("div", { class: "row end mt" }, [el("button", { class: "btn btn-primary", text: t("common.close"), onclick: () => App.refreshView() })]), ], { wide: true });
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  function importModal() {
    const ta = el("textarea", {
      class: "input", style: "min-height:190px;font-family:monospace;font-size:13px",
      text: "first_name;last_name;middle_name;birth_date;phone;group_name;license_category;address;notes\nBekzod;Raimov;Akmalovich;2005-03-12;+998901112233;B-24;B;Farg'ona shahar;import",
    });
    const m = modal("\u{1f4e5} " + t("student.import"), [
      el("p", { class: "field-hint", text: "CSV: first_name;last_name;middle_name;birth_date;phone;group_name;license_category;address;notes" }),
      ta,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: t("common.create"),
          onclick: async () => {
            m.close();
            try {
              const res = await API.post("admin/students/import", { csv: ta.value });
              const r = res.results;
              const rows = [
                ["\u{1f4c4}", t("common.all") + ":", r.total],
                ["\u2705", t("import.created"), r.created],
                ["\u26a0\ufe0f", t("import.duplicates"), r.duplicates],
                ["\u274c", t("import.errors"), r.errors.length],
              ];
              const box = el("div", {});
              rows.forEach(([a, b, c]) => box.append(el("div", { class: "kv" }, [el("span", { class: "k", text: a + " " + b }), el("span", { class: "v", text: String(c) })])));
              if (r.credentials.length) {
                box.append(el("h4", { class: "card-title mt", text: "\u{1f511} Login/Parol" }));
                r.credentials.slice(0, 20).forEach((cr, i) => box.append(el("div", { class: "kv" }, [
                  el("span", { class: "k", text: `#${i + 1}` }), el("span", { class: "v", text: cr.login + " / " + cr.password })])));
                /* MODUL 5: "bir marta ko'rsatish" cheklovi yo'q — har bir
                   foydalanuvchining 🔑 tugmasi orqali paroli keyin ham
                   ko'riladi va o'zgartiriladi. */
                box.append(el("p", { class: "field-hint", icon: "info", text: "" + t("users.cred_visible_note") }));
              }
              // xatolar
              modal("\u{1f4e5} " + t("student.import"), [box,
                el("div", { class: "row end mt" }, [el("button", { class: "btn btn-primary", text: t("common.close"), onclick: (ev) => ev.target.closest(".modal-overlay").close() })]),
              ], { wide: true });
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* =====================================================================
     MODUL 6 — OMMAVIY (BULK) AMALLAR uchun umumiy yordamchilar.

     ---------------------------------------------------------------------
     VAZIFA 2 — tuzatilgan uchta xato:
     ---------------------------------------------------------------------
     1) "N ta tanlandi" HISOBLAGICH CHIQMAYDI.
        Sabab: eski kodda `const n = sel.size` — bu panel YARATILGANDA bir
        marta o'qlanardi. Keyin `Set` o'zgarsa ham mahalliy `n` eski
        qiymatda (0) qolardi. Endi har render'da `state.size` QAYTA O'QILADI.

     2) "HAMMASINI TANLASH" HECH KIMNI BELGILAMAYDI.
        Sabab: `sel` ga ID qo'shilardi, lekin QATOR checkbox'larining
        `checked` holati yangilanmasdi — tanlangan qatorlar ko'rinmay qolardi.
        Endi `paint()` barcha qator checkbox'ini, qator fonini va sarlavha
        checkbox'ini (`checked` + `indeterminate`) BIR VAQTDA yangilaydi.

     3) STATE TO'G'RI YANGILANMASDI.
        Sabab: `Set` to'g'ridan-to'g'ri mutatsiya qilinardi (`.add()`) —
        yangi obyekt yaratilmasdi, shuning uchun render ishonchli emasdi.
        Endi `ids` — IMMUTABIl massiv: har o'zgarishda `concat`/`filter`
        bilan YANGI massiv yaratiladi va obyekt bo'yicha obunalar xabardor
        qilinadi (`.subscribe`).

     Tuzilma: `createSelection()` — immutabil tanlov holati.
              `createBulkStore()` — jadval + panel + sarlavha checkbox'ini
              BIR obyektda birlashtiradi (yagona manba: `state`).
     ===================================================================== */

  /* ---------------------------------------------------------------------
     1) Tanlov holati — immutabil `ids` + obyekt bo'yicha obuna.
        `ids` hech qachon to'g'ridan-to'g'ri o'zgartirilmaydi: har bir
        o'zgarish `concat`/`filter` bilan YANGI massiv yaratadi.
     --------------------------------------------------------------------- */
  function createSelection() {
    let ids = [];
    const subs = [];
    function notify() {
      subs.slice().forEach((f) => {
        try { f(ids); }
        catch (e) {
          /* Bitta obuna xatosi qolganlarini to'xtatmasin — lekin YASHIRILMAYdi:
             konsolga chiqariladi (jim qoldirish xatolarni topib bo'lmaydi). */
          if (typeof console !== "undefined" && console.error) console.error("[bulk] obuna xatosi:", e);
        }
      });
    }
    return {
      /* YANGI massiv qaytariladi (mutation yo'q) */
      get ids() { return ids; },
      get size() { return ids.length; },
      has(id) { return ids.indexOf(id) !== -1; },
      subscribe(fn) { subs.push(fn); return fn; },
      /* YANGI obyekt yaratib yangilash + bildirishnoma */
      set(next) {
        const a = Array.from(new Set(next));
        if (a.length === ids.length && a.every((x, k) => x === ids[k])) return false;
        ids = a;
        notify();
        return true;
      },
      add(id) { return this.set(ids.concat([id])); },
      remove(id) { return this.set(ids.filter((x) => x !== id)); },
      toggle(id) { return this.has(id) ? this.remove(id) : this.add(id); },
      clear() { return this.set([]); },
      /* joriy ro'yxatning BARCHASI */
      allOf(list) { return this.set((list || []).map((u) => u.id)); },
      /* berilgan ro'yxatdagilarni tanlovdan OLIB TASHLAYDI
         ("hammasini tanlash"ni bekor qilish uchun) */
      except(list) { return this.set(ids.filter((x) => !(list || []).some((u) => u.id === x))); },
      /* faqat berilgan ro'yxatdagilarni SAQLAB QOLADI, qolganini chiqaradi
         (filtr o'zgarganda ishlatiladi — aks holda panel yolg'on son ko'rsatadi) */
      only(list) {
        const inList = (list || []).map((u) => u.id);
        return this.set(ids.filter((x) => inList.indexOf(x) !== -1));
      },
    };
  }

  /* ---------------------------------------------------------------------
     2) Omma-viy ammalar "do'koni" — jadval, panel va sarlavha checkbox'ini
        bitta obyektda birlashtiradi.

        `roleKey` — student|instructor|admin (modal ogohlantirishi uchun)
        `onReload` — ro'yxatni qayta yuklash
        --------------------------------------------------------------------- */
  function createBulkStore(roleKey, onReload) {
    const state = createSelection();
    const rowCbs = new Map();   /* id -> checkbox element (registry) */
    const subs = [];            /* qayta chizishni xohlaydigan komponentlar */
    let list = [];              /* joriy filtrlangan ro'yxat */
    let total = 0;              /* server javobidagi umumiy son */
    let head = null;            /* sarlavhadagi "Hammasini tanlash" checkbox */

    /* --- birinchi manba: tanlanganlar o'zgarganda BUTUN DOM yangilanadi --- */
    function paint() {
      let inList = 0;
      list.forEach((u) => {
        const on = state.has(u.id);
        if (on) inList++;
        const cb = rowCbs.get(u.id);
        if (cb) {
          cb.checked = on;
          const tr = cb.closest ? cb.closest("tr") : null;
          if (tr) tr.classList.toggle("bulk-row-sel", on);
        }
      });
      if (head) {
        /* hammasi tanlangan / hech biri / qisman (chiziqcha) */
        const all = list.length > 0 && inList === list.length;
        head.checked = all;
        head.indeterminate = inList > 0 && !all;
        head.setAttribute("aria-checked", all ? "true" : "false");
      }
      subs.slice().forEach((f) => {
        try { f(state); }
        catch (e) { if (typeof console !== "undefined" && console.error) console.error("[bulk] panel xatosi:", e); }
      });
    }
    state.subscribe(paint);

    /* --- sarlavhadagi "Hammasini tanlash" --- */
    function toggleAll() {
      const all = list.length > 0 && list.every((u) => state.has(u.id));
      /* TOGGLE: hammasi tanlangan bo'lsa -> hammasi bekor; aks holda -> hammasi tanla.
         `head.checked` ga emas shu holatga qaraymiz — u har doim `paint()`
         dan keyin to'g'ri qiymatga ega. */
      if (all) { state.except(list); return; }
      if (total > list.length) {
        /* Server chegarasidan uzun ro'yxat — foydalanuvchi onayini olamiz. */
        confirmDialog(t("bulk.confirm_all", { n: total }), () => { state.allOf(list); },
          { danger: false, title: t("bulk.select_all") });
        return;
      }
      state.allOf(list);
    }

    const api = {
      state: state,
      /* Jadval qayta qurilganda ro'yxatni ulaydi (render dan oldin) */
      attach(next, serverTotal) {
        list = next || [];
        total = typeof serverTotal === "number" ? serverTotal : list.length;
        /* Endi ko'rinmaydigan qatorlar tanlangan bo'lsa — chiqariladi
           (aks holda panel yalg'on son ko'rsatadi).
           `only` ishlatiladi, `except` EMAS: `except` — ko'rsatilganlarni
           olib tashlaydi (teskari ma'no) va butun tanlovni bo'shatib yuborardi. */
        state.only(list);
        paint();
        return api;
      },
      /* Sarlavha checkbox'i */
      headerNode() {
        head = el("input", { type: "checkbox", class: "bulk-cb bulk-cb-head", "aria-label": t("bulk.select_all") });
        head.addEventListener("change", toggleAll);
        return el("label", { class: "bulk-cb-wrap bulk-cb-head", title: t("bulk.select_all") }, [head]);
      },
      /* Bir qator checkbox'i (registry'ga yoziladi) */
      rowNode(u) {
        const cb = el("input", { type: "checkbox", class: "bulk-cb", "aria-label": t("bulk.pick") });
        cb.checked = state.has(u.id);
        cb.addEventListener("change", () => {
          /* immutabil o'zgarish -> paint() -> panel + qator + sarlavha */
          state.toggle(u.id);
          cb.checked = state.has(u.id);   /* yagona manbadan qayta o'rnatish */
        });
        rowCbs.set(u.id, cb);
        return el("label", { class: "bulk-cb-wrap" }, [cb]);
      },
      /* Ammalar paneli — "N ta tanlandi" + o'chirish/tahrirlash/bekor */
      actionsNode() {
        const bar = el("div", { class: "bulk-bar" });
        subs.push((st) => {
          const n = st.size;      /* <<< HAR RENDER'DA QAYTA O'QILADI */
          bar.innerHTML = "";
          if (n === 0) {
            bar.classList.remove("hidden");
            bar.append(el("span", { class: "muted sm", text: t("bulk.none") }));
            return;
          }
          bar.classList.remove("hidden");
          bar.append(el("strong", { class: "bulk-bar-n", text: t("bulk.count", { n: n }) }));
          /* --- ommaviy o'chirish (tasdiqlash bilan) --- */
          bar.append(el("button", {
            class: "btn btn-danger btn-sm", icon: "trash", text: "" + t("bulk.delete"),
            onclick: () => confirmDialog(t("bulk.confirm_delete", { n: n }), async () => {
              try {
                const r = await API.post("admin/users/bulk-delete", { ids: st.ids });
                state.clear();
                toast(t("bulk.deleted", { n: (r && r.deleted != null) ? r.deleted : n }));
                onReload();
              } catch (e) { errToast(e); }
            }, { danger: true }),
          }));
          /* --- ommaviy tahrirlash (umumiy maydonlar) --- */
          bar.append(el("button", {
            class: "btn btn-cyan btn-sm", icon: "edit", text: "" + t("bulk.edit"),
            onclick: () => bulkEditModal(st.ids, list, onReload, roleKey),
          }));
          /* --- hammasini bekor qilish --- */
          bar.append(el("button", {
            class: "btn btn-light btn-sm", text: "" + t("bulk.deselect_all"),
            onclick: () => { state.clear(); },
          }));
        });
        paint();
        return bar;
      },
      /* Faqat o'qish uchun: hozirgi ro'yxat */
      get list() { return list; },
    };
    return api;
  }

  /* MODUL 2 — "Jami: N ta <rol>" hisoblagichi.
     `res` = backend javobi ({total, shown, filtered, limited}).
     `roleKey` = "student"|"instructor"|"admin" (birlik so'zi uchun). */
  function countBar(res, roleKey, unitKey) {
    const n = (res && typeof res.total === "number") ? res.total
      : ((res && res.users && res.users.length) || 0);
    const what = t(unitKey);
    const bar = el("div", { class: "count-bar" }, [
      el("span", { class: "count-bar-n", text: t("base.count", { n: n, what: what }) }),
    ]);
    if (res && res.filtered) {
      bar.append(el("span", { class: "count-bar-f muted sm", text: t("base.count_filtered", { n: n }) }));
    }
    return bar;
  }

  /* MODUL 6 — ommaviy tahrirlash modali (umumiy maydonlar). */
  function bulkEditModal(ids, list, onDone, roleOf) {
    /* Rol aniqlanadi: tanlanganlar bitta rolda bo'lishi SHART (chunki
       turli rolli aralashsa maydonlar mos kelmaydi). */
    const roles = {};
    ids.forEach((id) => { const u = list.find((x) => x.id === id); if (u) roles[u.role] = 1; });
    const roleKeys = Object.keys(roles);
    if (roleKeys.length !== 1) {
      return errToast({ code: "bulk.mixed_roles" });
    }
    const role = roleKeys[0];
    const f = {
      status: select({
        "": t("common.all"),
        active: t("student.status.active"),
        blocked: t("stat.blocked"),
      }),
      group_name: input({ placeholder: t("bulk.edit_group") }),
      license_category: input({ placeholder: t("bulk.edit_category") }),
      notes: input({ placeholder: t("bulk.edit_notes") }),
    };
    const hint = el("p", { class: "field-hint", text: t("bulk.edit_hint") });
    const m = modal(t("bulk.edit_title") + " \u2014 " + t("bulk.count", { n: ids.length }), [
      el("p", { class: "muted sm", text: t("bulk.pick") + ": " + t("rep.type." + (role === "student" ? "students" : role === "instructor" ? "instructors" : "admins")) }),
      field(t("bulk.edit_status"), f.status),
      /* Guruh va toifa faqat talaba/instruktor uchun mantiqli. */
      role === "student" ? field(t("bulk.edit_group"), f.group_name) : null,
      role === "student" ? field(t("bulk.edit_category"), f.license_category) : null,
      role !== "admin" ? field(t("bulk.edit_notes"), f.notes) : null,
      hint,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: "" + t("common.save"),
          onclick: async () => {
            const payload = { ids: ids };
            if (f.status.value) payload.status = f.status.value;
            if (f.group_name.value) payload.group_name = f.group_name.value;
            if (f.license_category.value) payload.license_category = f.license_category.value;
            if (f.notes.value) payload.notes = f.notes.value;
            if (Object.keys(payload).length === 1) { m.close(); return; }
            try {
              const r = await API.post("admin/users/bulk-update", payload);
              toast(t("bulk.done", { n: r.updated != null ? r.updated : ids.length }));
              m.close(); onDone();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* =====================================================================
     MODUL 3 — "Hisobot" tugmasi: Baza bo'limidan Hisobotlar bo'limiga
     o'tadi va ochiq toifa (tab) oldindan tanlangan holda ochiladi.
     ===================================================================== */
  function goReportsFor(role) {
    App.go("reports", { tab: role === "student" ? "students" : role === "instructor" ? "instructors" : "admins" });
  }

  /* ============================ TALABALAR ============================ */
  /* =====================================================================
     MODUL 6 — FOYDALANUVCHILAR: rol bo'yicha uchta alohida bo'lim (tab)
     Talabalar | Instruktorlar | Adminlar
     Har birida qidiruv + o'z ustunlari. Backend `role=` orqali filtrlaydi,
     shuning uchun ro'yxatlar aralashmaydi.
     ===================================================================== */
  const USER_TABS = [
    { role: "student", icon: "student", key: "nav.students" },
    { role: "instructor", icon: "instructor", key: "nav.instructors" },
    { role: "admin", icon: "shield", key: "nav.admins" },
  ];

  async function users(params) {
    const active = (params && params.tab && USER_TABS.some((x) => x.role === params.tab))
      ? params.tab : "student";
    const wrap = el("div", {}, []);

    // --- Tablar (sidebar'dan oson o'tish uchun) ---
    wrap.append(el("div", { class: "tabs mb" }, USER_TABS.map((tb) =>
      el("button", {
        class: "tab" + (tb.role === active ? " active" : ""),
        icon: tb.icon, text: t(tb.key),
        onclick: () => App.go("users", { tab: tb.role }),
      })
    )));

    const host = el("div", {});
    wrap.append(host);
    host.append(USER_TABLE[active](host));
    return wrap;
  }

/* =====================================================================
     BAND 3 — "Jami amaliy mashg'ulotlar sonini o'zgartirish"

     Modal sarlavhasi: "Jami amaliy mashg'ulotlar sonini o'zgartirish"
     Tanlov (radio): [Bitta talaba] | [Barcha talabalar]
     Maydon: jami mashg'ulotlar soni (1..999)
     Tugma: Saqlash

     QOIDALAR:
       * Yangi jami < BAJARILGAN bo'lsa — backend RAD ETADI
         (`user.total_lessons_below_done`) va modal ogohlantirish ko'rsatadi.
       * Bajarilgan mashg'ulotlar, tarix va booking O'CHIRILMAYDI — faqat
         maqsadli son o'zgaradi.
       * Bo'sh qiymat = individual maqsadni bekor qilish (platforma
         umumiy soniga qaytish).

     ===================================================================== */
  function totalLessonsModal(u, pr, onDone) {
    let scope = u ? "user" : "all";
    let value = (pr && pr.individual_target) ? String(pr.individual_target) : ((pr && pr.target) ? String(pr.target) : "");
    const doneN = (pr && pr.done) || 0;

    const errBox = el("div", { class: "map-msg map-msg-err hidden" });
    const numI = input({ type: "number", min: "1", max: "999", step: "1", value: value,
                         placeholder: String((pr && pr.target) || 30) });
    /* "O'chirish" — individual maqsadni bekor qilish, umumiy songa qaytish. */
    const clearBtn = el("button", { class: "btn btn-light btn-sm", text: "" + t("users.total_clear"),
      onclick: () => { numI.value = ""; } });

    const scopeRow = el("div", { class: "scope-row" });
    const scopeBtns = {};
    [["user", t("users.scope_single")], ["all", t("users.scope_all")]].forEach(([k, label]) => {
      /* Bitta talaba tanlangan bo'lsa, "Barcha talabalar" tanlovi ham
         ko'rsatiladi (masshtabli o'zgarish mumkin). */
      if (k === "user" && !u) return;
      const b = el("button", {
        class: "scope-btn" + (scope === k ? " on" : ""), type: "button", text: label,
        onclick: () => {
          scope = k;
          Object.keys(scopeBtns).forEach((x) => scopeBtns[x].classList.toggle("on", x === k));
          infoBox.textContent = scope === "all" ? t("users.total_all_hint") : t("users.total_one_hint", { n: doneN });
        },
      });
      scopeBtns[k] = b;
      scopeRow.append(b);
    });
    const infoBox = el("p", { class: "field-hint",
      text: scope === "all" ? t("users.total_all_hint") : t("users.total_one_hint", { n: doneN }) });

    function showErr(code) {
      /* BAND 3: aniq ogohlantirish — "bajarilgan darslardan kam qilib
         bo'lmaydi (hozir N ta bajarilgan)". */
      const code2 = String(code || "");
      const e = I18N.errorText(code2, { n: doneN, done: doneN, min: doneN });
      errBox.textContent = (e && e !== code2) ? e : t("users.total_below_done", { n: doneN });
      errBox.classList.remove("hidden");
    }
    function clearErr() { errBox.textContent = ""; errBox.classList.add("hidden"); }

    const m = modal(t("users.total_title"), [
      field(t("users.total_lessons"), numI, { hint: t("users.total_hint", { n: doneN }) }),
      clearBtn,
      el("div", { class: "field mt" }, [el("label", { class: "lbl", text: t("users.total_scope") }), scopeRow]),
      infoBox, errBox,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: "" + t("common.save"),
          onclick: async () => {
            clearErr();
            const raw = String(numI.value || "").trim();
            if (raw !== "") {
              const n = Number(raw);
              if (!Number.isInteger(n) || n < 1 || n > 999) { showErr("user.bad_total_lessons"); return; }
              /* BAND 3: oldindan tekshirish — foydalanuvchi tezroq xatoni ko'radi. */
              if (scope === "user" && n < doneN) { showErr("user.total_lessons_below_done"); return; }
            }
            try {
              const payload = scope === "all"
                ? { scope: "all", total_lessons: raw === "" ? null : Number(raw) }
                : { scope: "user", user_id: u.id, total_lessons: raw === "" ? null : Number(raw) };
              const r = await API.post("admin/users/total-lessons", payload);
              toast(scope === "all"
                ? t("users.total_saved_all", { n: r.updated != null ? r.updated : 0 })
                : t("users.total_saved_one"));
              m.close();
              if (typeof onDone === "function") onDone();
            } catch (e) {
              if (e && (e.code === "user.total_lessons_below_done" || e.code === "user.bad_total_lessons")) showErr(e.code);
              else errToast(e);
            }
          } }),
      ]),
    ]);
  }

  /* =====================================================================
     BAND 22 — FOYDALANUVCHI PROFILI (admin uchun to'liq kartochka)

     Ko'rsatiladigan ma'lumot: Talaba (ism), Login, Telefon, Guruh,
     Haydovchilik toifasi, Jami darslar, Bajarilgan, Qolgan, Progress.
     Tugmalar:
       * "Jami mashg'ulotlar sonini o'zgartirish"  -> totalLessonsModal()
       * "Ma'lumotni tahrirlash"                     -> Shared.openUserForm()
       * "Yangi parol yaratish"                      -> random parol (BAND 5/6)
     BAND 16: "Ro'yxatga olingan sana" FAQAT shu yerdan ko'rinadi.
     ===================================================================== */
  async function openUserProfile(userId, onDone) {
    const body = el("div", {}, [spinner()]);
    const m = modal(t("users.profile_title"), [body]);
    let data;
    try {
      data = (await API.get(`admin/users/${userId}`)).user;
    } catch (e) {
      body.innerHTML = "";
      body.append(emptyState("\u26a0\ufe0f", errorText(e && e.code)));
      return;
    }
    const u = data || {};
    const stu = u.student || {};
    const pr = u.progress;

    function kv(k, v) {
      return el("div", { class: "kv" }, [el("span", { class: "k", text: k }), el("span", { class: "v", text: v })]);
    }

    body.innerHTML = "";
    body.append(el("div", { class: "profile-head mb" }, [
      avatar(u, 56),
      el("div", { class: "f1" }, [
        el("div", { class: "profile-name", text: `${u.first_name || ""} ${u.last_name || ""}`.trim() || "\u2014" }),
        el("div", { class: "muted", text: roleName(u.role) + " \u00b7 " + u.login }),
      ]),
    ]));

    /* --- Asosiy ma'lumotlar --- */
    body.append(el("div", { class: "card-flat" }, [
      kv(t("users.field_name"), `${u.first_name || ""} ${u.last_name || ""}`.trim() || "\u2014"),
      kv(t("common.login"), u.login || "\u2014"),
      kv(t("common.phone"), u.phone || "\u2014"),
      /* Holat: arxivlangan foydalanuvchi "bloklangan" deb ko'rinmasin —
         ayniqsa "Arxivdan chiqarish" tugmasini izlashda yordam beradi. */
      kv(t("common.status"), isArchived(u) ? t("stat.archived")
        : (u.status === "active" ? t("student.status.active") : t("stat.blocked"))),
      u.role === "student" ? kv(t("student.group"), stu.group_name || "\u2014") : null,
      u.role === "student" ? kv(t("student.category"), stu.license_category || "\u2014") : null,
      u.role === "instructor" && u.car ? kv(t("users.car"), `${u.car.brand || ""} ${u.car.model || ""} \u00b7 ${u.car.plate_number || ""}`.trim() || "\u2014") : null,
      u.role === "instructor" ? kv(t("users.students_count"), String(u.students_count != null ? u.students_count : 0)) : null,
      /* BAND 16: "Ro'yxatga olingan sana" — faqat admin ko'radi. */
      stu.enrolled_at ? kv(t("student.enrolled"), fmtDate(stu.enrolled_at)) : null,
    ]));

    /* --- BAND 3/2: progress bloki (jami / bajarilgan / qolgan / %) --- */
    if (pr) {
      body.append(el("div", { class: "card-flat mt" }, [
        el("div", { class: "row between" }, [
          el("strong", { text: t("users.progress") }),
          badge(pr.mode === "individual" ? "b-cyan" : "b-gray",
                pr.mode === "individual" ? t("users.mode_individual") : t("users.mode_group")),
        ]),
        el("div", { class: "prog-mini mt" }, [
          el("div", { class: "prog-mini-bar" }, [el("i", { style: `width:${pr.pct}%` })]),
          el("span", { class: "muted sm", text: `${pr.done}/${pr.target} \u00b7 ${pr.pct}%` }),
        ]),
        el("div", { class: "grid-3 mt" }, [
          el("div", {}, [el("div", { class: "muted sm", text: t("week.total_lessons") }), el("div", { class: "cell-strong", text: String(pr.target) })]),
          el("div", {}, [el("div", { class: "muted sm", text: t("week.done_lessons") }), el("div", { class: "cell-strong", text: String(pr.done) })]),
          el("div", {}, [el("div", { class: "muted sm", text: t("week.remaining_lessons") }), el("div", { class: "cell-strong", text: String(pr.remaining) })]),
        ]),
      ]));
    }

    /* --- Amallar --- */
    const acts = el("div", { class: "row wrap gap-sm mt" }, [
      /* "Jami mashg'ulotlar" — faqat talabaga tegishli (progress talabada). */
      pr ? el("button", { class: "btn btn-cyan", icon: "target", text: "" + t("users.total_btn"),
        onclick: () => {
          /* Progress endi "jami" sifatida individual maqsad bo'lib ketadi. */
          totalLessonsModal(u, pr, async () => {
            m.close();
            if (typeof onDone === "function") onDone();
          });
        } }) : null,
      el("button", { class: "btn btn-light", icon: "edit", text: "" + t("users.edit_btn"),
        onclick: () => { m.close(); Shared.openUserForm(u.role, u); } }),
      el("button", { class: "btn btn-primary", icon: "key", text: "" + t("users.cred_title"),
        onclick: () => {
          m.close();
          Shared.openUserCredentialsManager(u, () => {
            openUserProfile(u.id, onDone);
          });
        } }),
    ]);
    /* MODUL 2/3: bloklash/blokdan chiqarish + arxivlash/arxivdan chiqarish
       — profil oynasida ham, jadval qatorida ham bir xil ishlaydi. */
    acts.append(el("div", { class: "row wrap gap-sm mt" }, userStatusActions(u, () => {
      m.close();
      if (typeof onDone === "function") onDone();
    })));
    body.append(acts);
    /* "Jami mashg'ulotlar sonini o'zgartirish" — barcha talabalar uchun
       (tanlov modal ichida ham bor). */
    if (u.role === "student") {
      body.append(el("div", { class: "row mt" }, [
        el("button", { class: "btn btn-light btn-sm", icon: "users", text: "" + t("users.total_btn_all"),
          onclick: () => totalLessonsModal(null, pr, async () => { m.close(); if (typeof onDone === "function") onDone(); }) }),
      ]));
    }
  }

  /* Ommaviy rejim uchun umumiy statistikani olish (modal ochilganda). */
  async function openTotalLessonsAll(onDone) {
    try {
      const res = await API.get("admin/users?role=student");
      const users = res.users.filter((x) => !x.deleted_at);
      const maxDone = users.reduce((m, x) => Math.max(m, (x.progress && x.progress.done) || 0), 0);
      totalLessonsModal(null, { done: maxDone, target: null, individual_target: null }, onDone);
    } catch (e) { errToast(e); }
  }
  // Eski havolalar (kichik o'zgarish uchun saqlanadi)
  function students(params) { return users({ tab: "student" }); }
  function instructors(params) { return users({ tab: "instructor" }); }

  function userSearchBox(placeholder) {
    return input({ type: "search", placeholder: placeholder || (t("common.search") + "...") });
  }

  /* MODUL 2/3 — foydalanuvchi holati amallari (bitta manba).
     Talaba, instruktor va admin — uchala rolda ham XUDDI SHUNDAY
     ishlaydi: bloklash/blokdan chiqarish + arxivlash/arxivdan chiqarish.
     Har biri TASDIQLANISHI shart (xavfli amal). */
  function isArchived(u) {
    return u.status === "archived" || !!u.deleted_at;
  }

  async function setUserStatus(u, act, onDone) {
    try {
      await API.post(`admin/users/${u.id}/status`, { status: act });
      toast(t("misc.saved"));
      if (typeof onDone === "function") onDone();
      return true;
    } catch (e) { errToast(e); return false; }
  }

  function userStatusActions(u, onDone) {
    const aAct = isArchived(u) ? "unarchive" : "archive";
    const aKey = aAct === "archive" ? "users.archive" : "users.unarchive";
    /* MODUL 2.2: arxivlangan foydalanuvchida faqat "arxivdan chiqarish"
       ko'rinadi — bloklash arxiv ma'lumotiga tegmasligi kerak. */
    if (aAct === "unarchive") {
      return [el("button", {
        class: "btn btn-light btn-sm", icon: "refresh", title: "" + t(aKey), text: "" + t(aKey),
        onclick: () => confirmDialog("" + t("users.unarchive_confirm"),
          () => setUserStatus(u, aAct, onDone)),
      })];
    }
    const bAct = u.status === "blocked" ? "unblock" : "block";
    const bKey = bAct === "unblock" ? "users.unblock" : "users.block";
    return [
      el("button", {
        class: "btn btn-light btn-sm", icon: bAct === "block" ? "shield" : "unlock",
        title: "" + t(bKey), text: "" + t(bKey),
        onclick: () => confirmDialog("" + t(bAct === "block" ? "users.block_confirm" : "users.unblock_confirm"),
          () => setUserStatus(u, bAct, onDone), { danger: bAct === "block" }),
      }),
      el("button", {
        class: "btn btn-light btn-sm", icon: "archive", title: "" + t(aKey), text: "" + t(aKey),
        onclick: () => confirmDialog("" + t("users.archive_confirm"),
          () => setUserStatus(u, aAct, onDone), { danger: true }),
      }),
    ];
  }
  function debounce(fn, ms) {
    let tm;
    return () => { clearTimeout(tm); tm = setTimeout(fn, ms || 300); };
  }

  /* MODUL 2.2/3.2 — arxivlangan foydalanuvchi rolda ham KO'RINISHI kerak.
     Oldin royxat `deleted_at` bo'lganlarni JS da to'liq YASHIRARDI va
     "Arxivlash" tugmasi esa hech qanday filtr ham bo'lmagan joyda yo'q edi —
     natijada arxivlangan admin/talaba/instruktorni qaytarib (arxivdan
     chiqarib) BO'LMAY qolardi. Endi uchala rol jadvalida ham bitta xil
     holat filtri bor: Barchasi / Faol / Bloklangan / Arxivlanganlar. */
  function userStatusFilter(onChange) {
    const sel = select({
      "": t("common.all"),
      active: t("student.status.active"),
      blocked: t("stat.blocked"),
      archived: t("stat.archived"),
    });
    sel.addEventListener("change", onChange);
    return sel;
  }

  function userListQuery(role, q, status) {
    return "admin/users?role=" + encodeURIComponent(role)
      + "&status=" + encodeURIComponent(status || "")
      + "&q=" + encodeURIComponent(q || "");
  }

  /* `status=archived` — backend `deleted_at IS NULL` shartini ataylab
     OLMAYDI (arxivlangan + bloklangan foydalanuvchi ham ko'rinishi uchun),
     shuning uchun JS da qayta filtrlashMAYmiz. Boshqa holatlarda
     `deleted_at` bo'lgan yozuvlar arxivlangan hisoblanadi va yashiriladi. */
  function visibleUsers(res, status) {
    const list = (res && res.users) || [];
    return status === "archived" ? list : list.filter((u) => !u.deleted_at);
  }

  /* Holat nishoni — arxivlangan foydalanuvchi "Bloklangan" deb
     ko'rinmasligi kerak (eskida students/instructors jadvalidagi xato). */
  function userStatusBadge(u) {
    if (isArchived(u)) return badge("archived", t("stat.archived"));
    return badge(u.status, u.status === "active" ? t("student.status.active") : t("stat.blocked"));
  }

  /* ------------------------------ TALABALAR ------------------------------ */
  /* BAND 22: jami / bajarilgan / qolgan — ustunlar aniq ko'rsatiladi. */
  function studentsTable(host) {
    const searchI = userSearchBox(t("users.search_student"));
    const addB = el("button", {
      class: "btn btn-primary", icon: "plus", text: "" + t("student.add"),
      onclick: () => Shared.openUserForm("student"),
    });
    /* MODUL 3: "Import CSV" Baza bo'limidan OLIB TASHLANGAN, o'rniga
       "Hisobot" — Hisobotlar bo'limiga o'tadi (toifa tanlangan holda). */
    const repB = el("button", {
      class: "btn btn-light", icon: "chart", title: t("base.go_reports_hint"),
      text: "" + t("base.go_reports"),
      onclick: () => goReportsFor("student"),
    });
    /* MODUL 6: tanlangan foydalanuvchilar (Set) + panel. */
    /* VAZIFA 2: yangi store — immutabil state + avtomatik DOM yangilanishi */
    const bulk = createBulkStore("student", load);
    const bulkBar = bulk.actionsNode();
    /* MODUL 2.2: arxivlangan talabalarni ko'rish / qaytarish uchun filtr. */
    const statusSel = userStatusFilter(() => load());

    async function load() {
      host.innerHTML = "";
      host.append(spinner());
      const res = await API.get(userListQuery("student", searchI.value, statusSel.value));
      const list = visibleUsers(res, statusSel.value);
      host.innerHTML = "";
      /* MODUL 2: "Jami: N ta talaba" — filtrga mos yangilanadi. */
      host.append(countBar(res, "student", "base.unit.student"));
      host.append(el("div", { class: "row between mb wrap gap-sm" }, [
        el("div", { class: "row wrap gap-sm" }, [searchI, statusSel]),
        el("div", { class: "row gap-sm" }, [repB, addB]),
      ]));
      host.append(bulkBar);
      if (!list.length) { host.append(emptyState("\u{1f468}\u200d\u{1f393}", t("users.empty_student"))); return; }
      /* MODUL 6: panelga joriy ro'yxatni beramiz (modal topish uchun). */
      bulk.attach(list, res.total);

      const tbl = el("table", { class: "tbl" }, [el("thead", {}, [el("tr", {}, [
        el("th", { class: "bulk-th" }, [bulk.headerNode()]),
        el("th", { text: t("common.name") }),
        el("th", { text: t("student.group") }),
        el("th", { text: t("student.category") }),
        el("th", { text: t("users.instructor") }),
        /* BAND 22: jami / bajarilgan / qolgan alohida, progress bar bilan. */
        el("th", { text: t("users.progress") }),
        el("th", { text: t("common.phone") }),
        el("th", { text: t("common.status") }),
        el("th", { text: t("common.actions") }),
      ])]), el("tbody", {}, list.map((u) => {
        /* BAND 3/22: `target` = jami (maqsad), `done` = bajarilgan,
           `remaining` = qolgan — hammasi DB'dan. */
        const pr = u.progress || { done: 0, total: 0, target: 0, remaining: 0, pct: 0, mode: "group" };
        const names = (u.instructors || []).map((x) => x.name);
        return el("tr", { "data-uid": String(u.id) }, [
          /* MODUL 6: qator checkbox */
          el("td", { class: "bulk-td" }, [bulk.rowNode(u)]),
          el("td", {}, [el("div", { class: "user-cell row-click", onclick: () => openUserProfile(u.id, load) }, [avatar(u, 34), el("div", {}, [
            el("div", { class: "cell-strong", text: `${u.first_name} ${u.last_name}` }),
            el("div", { class: "muted", text: u.login })])])]),
          el("td", { text: (u.student && u.student.group_name) || "\u2014" }),
          el("td", { text: (u.student && u.student.license_category) || "\u2014" }),
          el("td", {}, [names.length
            ? el("span", { text: names.length > 2 ? names.slice(0, 2).join(", ") + ` +${names.length - 2}` : names.join(", ") })
            : el("span", { class: "muted", text: "\u2014" })]),
          el("td", {}, [el("div", { class: "prog-mini" }, [
            el("div", { class: "prog-mini-bar" }, [el("i", { style: `width:${pr.pct}%` })]),
            /* BAND 22: "bajarilgan / jami · qolgan" */
            el("span", { class: "muted sm", text: `${pr.done}/${pr.target} \u00b7 ${t("week.remaining_lessons")} ${pr.remaining}` }),
          ])]),
          el("td", { text: u.phone || "\u2014" }),
          el("td", {}, [userStatusBadge(u)]),
          el("td", {}, [el("div", { class: "actions" }, [
            /* BAND 22: profil kartasi (ma'lumot + 3 amal) */
            el("button", { class: "btn btn-light btn-sm", title: t("users.profile_title"), text: "\u{1f464}",
              onclick: () => openUserProfile(u.id, load) }),
            /* BAND 3: jami mashg'ulotlar sonini o'zgartirish */
            el("button", { class: "btn btn-cyan btn-sm", title: t("users.total_btn"), text: "\u{1f3af}",
              onclick: () => totalLessonsModal(u, pr, load) }),
            el("button", { class: "btn btn-light btn-sm", text: "\u270f\ufe0f", onclick: () => Shared.openUserForm("student", u) }),
            /* MODUL 5: login+parolni ko'rish va birga o'zgartirish */
            el("button", { class: "btn btn-light btn-sm", text: "\u{1f511}", title: t("users.cred_title"),
              onclick: () => Shared.openUserCredentialsManager(u, load) }),
            /* MODUL 2: bloklash/blokdan chiqarish + arxivlash/arxivdan chiqarish */
            ...userStatusActions(u, load),
          ])]),
        ]);
      }))]);
      host.append(tbl);
    }
    searchI.addEventListener("input", debounce(load, 300));
    load();
  }

  /* ---------------------------- INSTRUKTORLAR ---------------------------- */
  function instructorsTable(host) {
    const searchI = userSearchBox(t("users.search_instructor"));
    const addB = el("button", {
      class: "btn btn-primary", icon: "plus", text: "" + t("instructor.add"),
      onclick: () => Shared.openUserForm("instructor"),
    });
    const repB = el("button", {
      class: "btn btn-light", icon: "chart", title: t("base.go_reports_hint"),
      text: "" + t("base.go_reports"),
      onclick: () => goReportsFor("instructor"),
    });
    /* VAZIFA 2: yangi store — immutabil state + avtomatik DOM yangilanishi */
    const bulk = createBulkStore("instructor", load);
    const bulkBar = bulk.actionsNode();
    /* MODUL 2.2: arxivlangan instruktorlarni ko'rish / qaytarish uchun filtr. */
    const statusSel = userStatusFilter(() => load());

    async function load() {
      host.innerHTML = "";
      host.append(spinner());
      const res = await API.get(userListQuery("instructor", searchI.value, statusSel.value));
      const list = visibleUsers(res, statusSel.value);
      host.innerHTML = "";
      host.append(countBar(res, "instructor", "base.unit.instructor"));
      host.append(el("div", { class: "row between mb wrap gap-sm" }, [
        el("div", { class: "row wrap gap-sm" }, [searchI, statusSel]),
        el("div", { class: "row gap-sm" }, [repB, addB]),
      ]));
      host.append(bulkBar);
      if (!list.length) { host.append(emptyState("\u{1f697}", t("users.empty_instructor"))); return; }
      bulk.attach(list, res.total);

      const tbl = el("table", { class: "tbl" }, [el("thead", {}, [el("tr", {}, [
        el("th", { class: "bulk-th" }, [bulk.headerNode()]),
        el("th", { text: t("common.name") }),
        el("th", { text: t("users.students_count") }),
        el("th", { text: t("users.car") }),
        el("th", { text: t("users.work_hours") }),
        el("th", { text: t("common.phone") }),
        el("th", { text: t("common.status") }),
        el("th", { text: t("common.actions") }),
      ])]), el("tbody", {}, list.map((u) => {
        const car = u.car || null;
        const inst = u.instructor || {};
        return el("tr", { "data-uid": String(u.id) }, [
          el("td", { class: "bulk-td" }, [bulk.rowNode(u)]),
          el("td", {}, [el("div", { class: "user-cell" }, [avatar(u, 34), el("div", {}, [
            el("div", { class: "cell-strong", text: `${u.first_name} ${u.last_name}` }),
            el("div", { class: "muted", text: u.login })])])]),
          el("td", {}, [el("span", { icon: "student", text: ` ${u.students_count || 0}` })]),
          el("td", {}, [car
            ? el("div", {}, [
                el("div", { class: "cell-strong", text: `${car.brand} ${car.model}` }),
                el("div", { class: "muted", text: car.plate_number }),
              ])
            : el("span", { class: "muted", text: t("err.car_not_assigned") })]),
          el("td", { text: (inst.work_start ? `${inst.work_start}\u2013${inst.work_end}` : "\u2014") }),
          el("td", { text: u.phone || "\u2014" }),
          el("td", {}, [userStatusBadge(u)]),
          el("td", {}, [el("div", { class: "actions" }, [
            el("button", { class: "btn btn-light btn-sm", text: "\u270f\ufe0f", onclick: () => Shared.openUserForm("instructor", u) }),
            el("button", { class: "btn btn-cyan btn-sm", icon: "car", text: "" + t("car.reassign"), onclick: () => assignCarModal(u) }),
            /* MODUL 5: login+parolni ko'rish va birga o'zgartirish */
            el("button", { class: "btn btn-light btn-sm", text: "\u{1f511}", title: t("users.cred_title"),
              onclick: () => Shared.openUserCredentialsManager(u, load) }),
            /* MODUL 2: instruktor ham xuddi shunday boshqariladi. */
            ...userStatusActions(u, load),
          ])]),
        ]);
      }))]);
      host.append(tbl);
    }
    searchI.addEventListener("input", debounce(load, 300));
    load();
  }

  /* ------------------------------ ADMINLAR ------------------------------ */
  function adminsTable(host) {
    const searchI = userSearchBox(t("users.search_admin"));
    const repB = el("button", {
      class: "btn btn-light", icon: "chart", title: t("base.go_reports_hint"),
      text: "" + t("base.go_reports"),
      onclick: () => goReportsFor("admin"),
    });
    /* VAZIFA 2: yangi store — immutabil state + avtomatik DOM yangilanishi */
    const bulk = createBulkStore("admin", load);
    const bulkBar = bulk.actionsNode();
    const addA = el("button", {
      class: "btn btn-primary", icon: "plus", text: "" + t("users.add_admin"),
      onclick: () => Shared.openUserForm("admin"),
    });
    /* MODUL 2.2/3.2: arxivlangan adminni ko'rish / qaytarish uchun filtr.
       Aks holda arxivlashdan keyin admin ro'yxatdan BUTUNLAY yo'qolib
       qolardi va "Arxivdan chiqarish" tugmasi hech qaerda chiqmasdi. */
    const statusSel = userStatusFilter(() => load());
    const bar = el("div", { class: "row between mb wrap gap-sm" }, [
      el("div", { class: "row wrap gap-sm" }, [searchI, statusSel]),
      el("div", { class: "row wrap gap-sm" }, [
        addA,
        repB,
        el("span", { class: "muted sm", text: t("users.admins_hint") }),
      ]),
    ]);

    async function load() {
      host.innerHTML = "";
      host.append(spinner());
      const res = await API.get(userListQuery("admin", searchI.value, statusSel.value));
      const list = visibleUsers(res, statusSel.value);
      host.innerHTML = "";
      host.append(countBar(res, "admin", "base.unit.admin"));
      host.append(bar);
      host.append(bulkBar);
      if (!list.length) { host.append(emptyState("\u{1f6e1}\ufe0f", t("users.empty_admin"))); return; }
      bulk.attach(list, res.total);

      const tbl = el("table", { class: "tbl" }, [el("thead", {}, [el("tr", {}, [
        el("th", { class: "bulk-th" }, [bulk.headerNode()]),
        el("th", { text: t("common.name") }),
        el("th", { text: t("users.perms") }),
        el("th", { text: t("users.last_login") }),
        el("th", { text: t("common.phone") }),
        el("th", { text: t("common.status") }),
        /* Amallar ustuni — `<tbody>` da 7 ta `<td>` bor, sarlavha esa 6 ta
           edi (jadval ustunlari qator bilan mos kelmasdi). */
        el("th", { text: t("common.actions") }),
      ])]), el("tbody", {}, list.map((u) => el("tr", { "data-uid": String(u.id) }, [
        el("td", { class: "bulk-td" }, [bulk.rowNode(u)]),
        el("td", {}, [el("div", { class: "user-cell row-click", onclick: () => openUserProfile(u.id, load) }, [avatar(u, 34), el("div", {}, [
          el("div", { class: "cell-strong", text: `${u.first_name} ${u.last_name}` }),
          el("div", { class: "muted", text: u.login })])])]),
        el("td", {}, [el("span", { class: "badge badge-cyan", text: t("auth.role_admin") })]),
        el("td", { text: u.last_login_at || "\u2014" }),
        el("td", { text: u.phone || "\u2014" }),
        el("td", {}, [userStatusBadge(u)]),
        el("td", {}, [el("div", { class: "actions" }, [
          el("button", { class: "btn btn-light btn-sm", icon: "eye", text: "", title: t("users.view_profile"),
            onclick: () => openUserProfile(u.id, load) }),
          el("button", { class: "btn btn-light btn-sm", icon: "edit", text: "", title: t("common.edit"),
            onclick: () => Shared.openUserForm("admin", u) }),
          el("button", { class: "btn btn-light btn-sm", icon: "key", text: "", title: t("users.cred_title"),
            onclick: () => Shared.openUserCredentialsManager(u, load) }),
          /* MODUL 3: admin ham xuddi shunday bloklanadi/arxivlanadi
             (o'zini va oxirgi faol adminni — backend qat'iy tekshiradi). */
          ...userStatusActions(u, load),
        ])]),
      ])))]);
      host.append(tbl);
    }
    searchI.addEventListener("input", debounce(load, 300));
    load();
  }

  const USER_TABLE = {
    student: studentsTable,
    instructor: instructorsTable,
    admin: adminsTable,
  };

  async function assignCarModal(instructor) {
    const cars = (await API.get("admin/cars")).cars.filter((c) => c.status !== "inactive");
    const sel = select({ "": "\u2014 " + t("car.not_assigned") + " \u2014" }, instructor.assigned_car_id || "", {});
    cars.forEach((c) => sel.append(el("option", { value: c.id, text: `${c.brand} ${c.model} \u2014 ${c.plate_number} (${statusText(c.status)})`, selected: instructor.assigned_car_id === c.id ? "selected" : "" })));
    const m = modal("\u{1f697} " + t("car.reassign") + " \u2014 " + instructor.first_name + " " + instructor.last_name, [
      el("p", { class: "field-hint", text: t("instructor.car_note") }),
      field(t("lesson.car"), sel),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: t("common.save"),
          onclick: async () => {
            try {
              await API.post(`admin/instructors/${instructor.instructor.id}/car`, { car_id: sel.value || null });
              toast(t("misc.saved")); m.close(); App.refreshView();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* ============================ AVTOMOBILLAR ============================ */
  async function cars() {
    const res = await API.get("admin/cars");
    const wrap = el("div", {}, []);
    wrap.append(el("div", { class: "row between mb" }, [
      el("h3", { icon: "car", text: "" + t("nav.cars") }),
      el("button", { class: "btn btn-primary", icon: "plus", text: "" + t("car.add"), onclick: () => carModal() }),
    ]));
    const statuses = [{ v: "", l: t("common.all") }, ...["active", "repair", "checkup", "inactive"].map((s) => ({ v: s, l: statusText(s) }))];
    const statusF = select(Object.fromEntries(statuses.map((s) => [s.v, s.l])));
    const searchI = input({ type: "search", placeholder: t("common.search") + "..." });
    wrap.append(el("div", { class: "row mb" }, [statusF, searchI]));
    const host = el("div", {});
    wrap.append(host);
    async function load() {
      host.innerHTML = ""; host.append(spinner());
      const q = new URLSearchParams({ status: statusF.value, q: searchI.value });
      const r2 = await API.get("admin/cars?" + q.toString());
      host.innerHTML = "";
      if (!r2.cars.length) { host.append(emptyState("\u{1f697}", t("car.not_assigned"))); return; }
      const grid = el("div", { class: "grid-3 cars-grid" });
      r2.cars.forEach((c) => {
        const photos = r2.photos[c.id] || [];
        const quickStatus = Object.fromEntries(statuses.filter((s) => s.v).map((s) => [s.v, s.l]));
        const stSel = select(quickStatus, c.status, { class: "input car-status-select", title: t("car.status") });
        stSel.addEventListener("change", () => {
          if (stSel.value === c.status) return;
          confirmDialog((t("car.confirm_status") || "Statusni o'zgartirasizmi?").replace("{s}", statusText(stSel.value)), async () => {
            try {
              await API.put(`admin/cars/${c.id}/status`, { status: stSel.value });
              toast(t("car.status_changed")); load();
            } catch (e) { errToast(e); stSel.value = c.status; }
          }, { danger: stSel.value !== "active" });
        });
        grid.append(el("div", { class: "card" }, [
          el("div", { class: "car-big mb" }, [
            carPhoto(photos[0] ? photos[0].path : "", 92),
            el("div", {}, [
              el("div", { class: "car-model", text: `${c.brand} ${c.model || c.custom_model_name}` }),
              el("div", { class: "car-plate", text: c.plate_number }),
            ]),
          ]),
          el("div", { class: "sm card-body-grow" }, [
            el("div", { text: `\u{1f4c5} ${c.year || "\u2014"} \u00b7 ${c.color || ""}` }),
            el("div", { text: `\u{1f465} ${t("car.capacity")}: ${c.practice_capacity}` }),
            el("div", { text: `\u{1fa7a} ${t("car.inspection")}: ${c.technical_inspection_date || "\u2014"}` }),
            el("div", { text: `\u{1f6e1}\ufe0f ${t("car.insurance")}: ${c.insurance_expiry || "\u2014"}` }),
            el("div", { text: `${t("car.assigned_to")}: ${r2.assigned_to[c.id] || "\u2014"}` }),
            el("div", { text: `\u{1f4f7} ${photos.length ? photos.length + " " + t("car.photo_count") : t("car.no_photos")}` }),
          ]),
          el("div", { class: "row between mt car-actions" }, [
            stSel,
            el("div", { class: "actions" }, [
              el("button", { class: "btn btn-light btn-sm", title: t("car.photos"), text: "\u{1f4f7}",
                onclick: () => carPhotosModal(c) }),
              el("button", { class: "btn btn-light btn-sm", text: "\u270f\ufe0f", onclick: () => carModal(c) }),
              el("button", { class: "btn btn-danger btn-sm", text: "\u{1f5d1}", onclick: () => confirmDialog("Delete?", async () => {
                try { await API.del(`admin/cars/${c.id}`); toast(t("misc.saved")); load(); } catch (e) { errToast(e); }
              }, { danger: true }) }),
            ]),
          ]),
        ]));
      });
      host.append(grid);
    }
    statusF.addEventListener("change", load);
    searchI.addEventListener("input", (() => { let tm; return () => { clearTimeout(tm); tm = setTimeout(load, 300); }; })());
    load();
    return wrap;
  }

  function carModal(car) {
    const f = {
      brand: input({ value: car ? car.brand : "Chevrolet" }),
      model: input({ value: car ? car.model : "" }),
      plate: input({ value: car ? car.plate_number : "", placeholder: "01 A 123 AA" }),
      year: input({ type: "number", value: car ? car.year : 2022 }),
      color: input({ value: car ? car.color : "Oq" }),
      seats: input({ type: "number", value: car ? car.seat_count : 4 }),
      capacity: input({ type: "number", value: car ? car.practice_capacity : 4 }),
      inspection: input({ type: "date", value: car ? car.technical_inspection_date : "" }),
      insurance: input({ type: "date", value: car ? car.insurance_expiry : "" }),
      status: select({ active: statusText("active"), repair: statusText("repair"), checkup: statusText("checkup"), inactive: statusText("inactive") }, car ? car.status : "active"),
    };
    const notes = el("textarea", { class: "input", text: car ? car.notes : "" });
    const m = modal(car ? t("common.edit") : t("car.add"), [
      el("div", { class: "grid-2" }, [
        field(t("car.brand"), f.brand), field(t("car.model"), f.model),
        field("\u{1f522} " + t("car.plate"), f.plate), field(t("car.year"), f.year),
        field(t("car.color"), f.color), field(t("car.seats"), f.seats),
        field("\u{1f465} " + t("car.capacity"), f.capacity), field(t("car.status"), f.status),
        field(t("car.inspection"), f.inspection), field(t("car.insurance"), f.insurance),
      ]),
      field(t("common.notes"), notes),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: t("common.save"),
          onclick: async () => {
            const payload = {
              brand: f.brand.value, model: f.model.value, plate_number: f.plate.value,
              year: parseInt(f.year.value || 0), color: f.color.value, seat_count: parseInt(f.seats.value || 4),
              practice_capacity: parseInt(f.capacity.value || 4), status: f.status.value,
              technical_inspection_date: f.inspection.value, insurance_expiry: f.insurance.value, notes: notes.value,
            };
            try {
              if (car) await API.put(`admin/cars/${car.id}`, payload);
              else await API.post("admin/cars", payload);
              toast(t("misc.saved")); m.close(); App.refreshView();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* ---- M5: avtomobil fotosuratlari galereyasi ---- */
  function pickCarPhoto(car, onDone) {
    const fi = el("input", { type: "file", accept: "image/jpeg,image/png,image/webp", style: "display:none" });
    document.body.appendChild(fi);
    fi.addEventListener("change", () => {
      const file = fi.files && fi.files[0];
      fi.remove();
      if (!file) return;
      if (!/^image\/(jpeg|png|webp)$/.test(file.type)) return errToast({ code: "img.format" });
      if (file.size > 5 * 1024 * 1024) return errToast({ code: "img.size" });
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = async () => {
          // Katta rasmni ≤1280px gacha siqamiz (yuklash yengil bo'lsin)
          const MAX = 1280;
          const scale = Math.min(1, MAX / Math.max(img.naturalWidth, img.naturalHeight));
          const cv = el("canvas", { width: Math.round(img.naturalWidth * scale), height: Math.round(img.naturalHeight * scale) });
          cv.getContext("2d").drawImage(img, 0, 0, cv.width, cv.height);
          let dataUrl;
          try { dataUrl = cv.toDataURL("image/jpeg", 0.85); }
          catch (e) { return errToast({ code: "img.format" }); }
          try {
            await API.post(`admin/cars/${car.id}/photos`, { image: dataUrl });
            toast(t("car.photo_added")); onDone && onDone();
          } catch (e) { errToast(e); }
        };
        img.onerror = () => errToast({ code: "img.format" });
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
    fi.click();
  }

  function carPhotosModal(car) {
    const grid = el("div", { class: "car-photos-grid" }, []);
    const addBtn = el("button", { class: "btn btn-cyan", icon: "plus", text: "" + t("car.add_photo"),
      onclick: () => pickCarPhoto(car, refresh) });
    const m = modal("\u{1f4f7} " + car.plate_number + " \u00b7 " + t("car.photos"), [
      el("p", { class: "field-hint mb", text: "" + t("car.photo_hint") }),
      grid,
      el("div", { class: "row end mt" }, [
        addBtn,
        el("button", { class: "btn btn-light", text: t("common.close"), onclick: () => m.close() }),
      ]),
    ], { wide: true });
    async function refresh() {
      let photos = [];
      try {
        const r = await API.get("admin/cars");
        photos = r.photos[car.id] || [];
      } catch (e) { errToast(e); return; }
      grid.innerHTML = "";
      if (!photos.length) { grid.append(emptyState("\u{1f4f7}", t("car.no_photos"))); return; }
      photos.forEach((p) => {
        const del = el("button", { class: "btn btn-danger btn-sm photo-del", text: "\u2715",
          title: t("car.remove_photo"), onclick: () => confirmDialog(t("car.remove_photo") + "?", async () => {
            try {
              await API.del(`admin/cars/${car.id}/photos/${p.id}`);
              toast(t("car.photo_removed")); refresh();
            } catch (e) { errToast(e); }
          }, { danger: true }) });
        grid.append(el("div", { class: "car-photo-thumb" }, [carPhoto(p.path, 150), del]));
      });
    }
    refresh();
  }

  /* ============================ MASHG'ULOTLAR (SESSIONS) ============================ */
  async function lessons() {
    const wrap = el("div", {}, []);
    const dateI = input({ type: "date", value: Shared.todayISO() });
    const instSel = select({ "": t("common.all") });
    const instructors = (await API.get("admin/instructors")).instructors;
    instructors.forEach((i) => instSel.append(el("option", { value: i.id, text: `${i.first_name} ${i.last_name}` })));
    const statusSel = select({ "": t("common.all"), scheduled: statusText("scheduled"), ongoing: statusText("ongoing"), completed: statusText("completed"), cancelled: statusText("cancelled") });
    const addB = el("button", { class: "btn btn-primary", icon: "plus", text: "" + t("lesson.add"), onclick: () => newSessionModal() });
    wrap.append(el("div", { class: "row between mb wrap" }, [
      el("div", { class: "row wrap gap-sm" }, [dateI, instSel, statusSel]),
      addB,
    ]));
    const host = el("div", {});
    wrap.append(host);
    async function load() {
      host.innerHTML = ""; host.append(spinner());
      const q = new URLSearchParams({ date: dateI.value, instructor_id: instSel.value, status: statusSel.value });
      const res = await API.get("admin/sessions?" + q.toString());
      host.innerHTML = "";
      const list = el("div", { class: "grid-3" });
      res.sessions.forEach((s) => list.append(sessionCard(s)));
      if (!res.sessions.length) list.append(emptyState("\u{1f4da}", t("lesson.empty_today")));
      host.append(list);
    }
    [dateI, instSel, statusSel].forEach((c) => c.addEventListener("change", load));
    load();
    return wrap;
  }

  async function newSessionModal() {
    const instructors = (await API.get("admin/instructors")).instructors;
    const dur = await platformDuration();
    const f = {};
    f.date = input({ type: "date", value: Shared.todayISO() });
    f.start = input({ type: "time", value: "15:00" });
    f.end = input({ type: "time", value: addMinutesTo("15:00", dur) });
    // M9: boshlanish o'zgarganida end avtomatik to'ldiriladi (tahrirlab bo'ladi)
    f.start.addEventListener("change", () => { f.end.value = addMinutesTo(f.start.value, dur); });
    f.instructor = select({}, "");
    instructors.forEach((i) => f.instructor.append(el("option", { value: i.id, text: `${i.first_name} ${i.last_name}` })));
    f.car = el("div", { class: "input readonly", text: "\u2014" });
    f.cap = el("div", { class: "input readonly", text: "\u2014" });
    const studSelWrap = el("div", {});
    const addedList = el("div", { class: "mt" });
    const added = [];

    const studentsRes = await API.get("admin/users?role=student&status=active");
    const allStudents = studentsRes.users.filter((u) => u.student && !u.deleted_at);

    function renderStudents() {
      studSelWrap.innerHTML = "";
      const opts = [];
      allStudents.forEach((u) => {
        if (!added.includes(String(u.student.id))) opts.push({ value: u.student.id, text: `${u.first_name} ${u.last_name} (${u.student.group_name || ""})` });
      });
      const combo = UI.combobox({ options: opts, placeholder: t("lesson.search_student"), onChange: (val) => { if (val && !added.includes(String(val))) { added.push(String(val)); } renderStudents(); } });
      const addBtn = el("button", { class: "btn btn-cyan btn-sm", icon: "plus", text: "" + t("lesson.add_student"),
        onclick: () => { const v = combo.value(); if (v && !added.includes(String(v))) { added.push(String(v)); renderStudents(); } } });
      studSelWrap.append(el("div", { class: "row" }, [el("div", { class: "f1" }, [combo]), addBtn]));
      addedList.innerHTML = "";
      // f.cap div elementi — sig'im "🔒 N" shaklida textContent'da turadi
      const capNum = f.cap.textContent !== "\u2014" ? parseInt(String(f.cap.textContent).replace("\u{1f512} ", "") || "0") : 0;
      if (capNum && added.length > capNum) {
        addedList.append(el("div", { class: "muted mt", icon: "alert", text: "" + t("lesson.capacity_full_warn") }));
      }
      added.forEach((sid) => {
        const u = allStudents.find((x) => String(x.student.id) === String(sid));
        const line = el("div", { class: "kv" }, [
          el("span", { class: "k", icon: "graduation", text: " \u{1f468}" + (u ? `${u.first_name} ${u.last_name}` : sid) }),
          el("button", { class: "btn btn-ghost", text: "\u2715", onclick: () => { added.splice(added.indexOf(sid), 1); renderStudents(); } }),
        ]);
        addedList.append(line);
      });
    }

    async function onInstructor() {
      const inst = instructors.find((i) => String(i.id) === String(f.instructor.value));
      if (inst && inst.car) {
        f.car.textContent = "\u{1f512} " + inst.car.brand + " " + inst.car.model + " \u2014 " + inst.car.plate_number;
        f.cap.textContent = "\u{1f512} " + inst.car.practice_capacity;
        renderStudents();
      } else {
        f.car.textContent = "\u2014";
        f.cap.textContent = "\u2014";
        addedList.innerHTML = "";
      }
    }

    const m = modal(t("lesson.create_title"), [
      el("div", { class: "grid-2" }, [
        field("\u{1f4c5} " + t("lesson.date"), f.date),
        el("div", { class: "row" }, [field("\u{1f552} " + t("lesson.start"), f.start, { class: "f1" }), field("\u{1f552} " + t("lesson.end"), f.end, { class: "f1" })]),
        field("\u{1f468}\u200d\u{1f3eb} " + t("lesson.instructor"), f.instructor),
        field("\u{1f697} " + t("lesson.car"), f.car),
        field("\u{1f465} " + t("lesson.capacity"), f.cap),
      ]),
      el("div", { class: "mt" }, [
        el("div", { class: "field-label", icon: "graduation", text: " \u{1f468}" + t("lesson.students") + " " + (f.cap.textContent !== "\u2014" ? `(${added.length}/${f.cap.textContent.replace("\u{1f512} ", "")})` : "") }),
        studSelWrap, addedList,
      ]),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: t("common.create"),
          onclick: async () => {
            try {
              const res = await API.post("admin/sessions", {
                date: f.date.value, start_time: f.start.value, end_time: f.end.value,
                instructor_id: parseInt(f.instructor.value), student_ids: added,
              });
              toast(t("misc.saved") + " \u{1f697} " + res.auto.car);
              m.close(); App.refreshView();
            } catch (e) {
              const errors = e.params && e.params.errors;
              if (errors) {
                errToast(e);
                Shared.rulesList(errors);
              } else errToast(e);
            }
          } }),
      ]),
    ], { wide: true });
    f.instructor.addEventListener("change", onInstructor);
  }

  /* ============================ KALENDAR ============================ */
  async function calendar(params) {
    const wrap = el("div", {}, []);
    let view = params && params.view || "week";
    let anchor = params && params.date || Shared.todayISO();
    const navB = el("div", { class: "row gap-sm" }, []);
    const prevB = el("button", { class: "btn btn-light btn-sm", text: "\u2190", onclick: () => { anchor = shift(anchor, -1); load(); } });
    const nextB = el("button", { class: "btn btn-light btn-sm", text: "\u2192", onclick: () => { anchor = shift(anchor, 1); load(); } });
    const todayB = el("button", { class: "btn btn-light btn-sm", text: t("misc.today"), onclick: () => { anchor = Shared.todayISO(); load(); } });
    const viewBtns = el("div", { class: "cal-toolbar" }, []);
    const host = el("div", {});
    wrap.append(navB, viewBtns, host);

    function shift(d, dir) {
      const dt = new Date(d + "T12:00:00");
      if (view === "day") dt.setDate(dt.getDate() + dir);
      else if (view === "week") dt.setDate(dt.getDate() + dir * 7);
      else dt.setMonth(dt.getMonth() + dir);
      const y = dt.getFullYear(), m2 = String(dt.getMonth() + 1).padStart(2, "0"), dd = String(dt.getDate()).padStart(2, "0");
      return `${y}-${m2}-${dd}`;
    }

    function buildViews() {
      viewBtns.innerHTML = "";
      ["day", "week", "month"].forEach((v) => {
        const b = el("button", { class: "cal-view-btn" + (v === view ? " active" : ""), text: v === "day" ? t("report.period.daily") : v === "week" ? t("report.period.weekly") : t("report.period.monthly"),
          onclick: () => { view = v; buildViews(); load(); } });
        viewBtns.append(b);
      });
    }

    async function load() {
      navB.innerHTML = "";
      navB.append(prevB, todayB, nextB,
        el("strong", { text: fmtDate(anchor) + (view !== "day" ? ` \u2013 ${fmtDate(shift(anchor, 1))}` : "") }));
      host.innerHTML = ""; host.append(spinner());
      const res = await API.get(`admin/calendar?view=${view}&date=${anchor}`);
      host.innerHTML = "";
      // guruhlash
      const byDay = {};
      res.events.forEach((e) => { (byDay[e.date] = byDay[e.date] || []).push(e); });
      const grid = el("div", { class: view === "month" ? "grid-3" : "grid-2" });
      const days = [];
      if (view === "day") days.push(res.start);
      else if (view === "week") {
        const s = new Date(res.start + "T12:00:00");
        for (let i = 0; i < 7; i++) { const d = new Date(s); d.setDate(s.getDate() + i); days.push(d.toISOString().slice(0, 10)); }
      } else {
        const s = new Date(res.start + "T12:00:00");
        const daysInMonth = new Date(s.getFullYear(), s.getMonth() + 1, 0).getDate();
        for (let i = 1; i <= daysInMonth; i++) days.push(`${res.start.slice(0, 8)}${String(i).padStart(2, "0")}`);
      }
      days.forEach((d) => {
        const evts = byDay[d] || [];
        grid.append(el("div", { class: "day-card" }, [
          el("div", { class: "day-head", text: fmtDate(d) + (evts.length ? ` \u00b7 ${evts.length}` : "") }),
          ...(evts.length ? evts.slice(0, 8).map((e) => sessionMini(e)) : [el("div", { class: "muted", text: "\u2014" })]),
        ]));
      });
      host.append(grid);
    }
    function sessionMini(s) {
      return el("div", { class: "cal-evt " + s.status, dataset: { sid: s.id }, onclick: () => Shared.openSession(s.id, "admin") }, [
        el("strong", { text: `${s.start_time}\u2013${s.end_time}` }),
        el("div", { icon: "instructor", text: "" + s.instructor_name }),
        el("div", { class: "muted sm", icon: "car", text: "" + (s.car_name_snapshot || "") + " \u00b7 \u{1f465} " + s.student_count + "/" + s.capacity_snapshot }),
      ]);
    }
    buildViews();
    load();
    return wrap;
  }

  /* ============================ SO'ROVLAR ============================ */
  /* MODUL 5B: uchta bo'lim — Faol / Eskirgan / Tarix.
     * `Faol`    — mashg'ulot sanasi kelajakda (yoki bugun) va hali tasdiqlanmagan;
     * `Eskirgan`— mashg'ulot sanasi o'tib, 1 kun o'tgan, hali tasdiqlanmagan;
     * `Tarix`   — tasdiqlangan / rad etilgan / bekor qilingan. */
  function requestTabs(active, counts, onPick) {
    const tabs = [
      ["active", t("req.filter_active")],
      ["expired", t("req.filter_expired")],
      ["history", t("req.filter_history")],
    ];
    return el("div", { class: "row gap-sm wrap mb" }, tabs.map(([k, label]) =>
      el("button", {
        class: "btn btn-sm " + (k === active ? "btn-primary" : "btn-light"),
        icon: k === "active" ? "inbox" : (k === "expired" ? "clock" : "list"),
        text: "" + label + " (" + ((counts && counts[k]) || 0) + ")",
        onclick: () => onPick(k),
      })
    ));
  }

  async function requests() {
    const wrap = el("div", {});
    const head = el("h3", { class: "mb", text: "\u{1f4e8} " + t("nav.requests") });
    const tabsHost = el("div", {});
    const listHost = el("div", {});
    wrap.append(head, el("p", { class: "field-hint mb", text: t("req.auto_hidden") }), tabsHost, listHost);
    let mode = "active";

    async function load(m) {
      mode = m;
      listHost.innerHTML = ""; listHost.append(spinner());
      const res = await API.get("admin/requests?filter=" + encodeURIComponent(m));
      const counts = res.counts || {};
      tabsHost.innerHTML = "";
      tabsHost.append(requestTabs(mode, counts, load));
      listHost.innerHTML = "";
      const items = res.requests || [];
      if (!items.length) { listHost.append(emptyState("\u{1f4e8}", t("req.title"))); return; }
      const list = el("div", { class: "grid-2" });
      items.forEach((r) => {
        list.append(el("div", { class: "card" }, [
          el("div", { class: "row between mb" }, [
            el("div", { class: "user-cell" }, [avatar(r, 34), el("div", {}, [
              el("strong", { text: `${r.first_name} ${r.last_name}` }),
              el("div", { class: "muted sm", text: r.group_name || "" }),
            ])]),
            el("div", { class: "row gap-sm" }, [
              r.is_expired ? badge("late", t("req.expired")) : null,
              badge(r.status, statusText(r.status)),
            ]),
          ]),
          el("div", { class: "muted sm" }, [
            el("div", { icon: "calendar", text: "" + t("req.preferred") + ": " + (r.preferred_date ? fmtDate(r.preferred_date) : "\u2014") + " " + (r.preferred_start_time ? r.preferred_start_time + "\u2013" + r.preferred_end_time : "") }),
            el("div", { icon: "message", text: "" + (r.message || "\u2014") }),
          ]),
          r.is_expired ? el("div", { class: "field-hint", text: t("req.expired_hint") }) : null,
          r.status === "pending" ? el("div", { class: "row mt" }, [
            el("button", { class: "btn btn-primary btn-sm f1", icon: "check_circle", text: "" + t("req.approve"), onclick: () => approveModal(r) }),
            el("button", { class: "btn btn-danger btn-sm f1", icon: "checkup", text: "" + t("req.reject"), onclick: () => rejectModal(r) }),
          ]) : null,
        ]));
      });
      listHost.append(list);
    }

    await load(mode);
    return wrap;
  }

  async function approveModal(r) {
    const m = modal(t("req.choose_schedule"), [], { wide: true });
    m.body.innerHTML = "";
    m.body.append(spinner());
    const instructors = (await API.get("admin/instructors")).instructors;
    const dur = await platformDuration();
    m.body.innerHTML = "";
    const hasPrefEnd = !!r.preferred_end_time;
    const f = {
      date: input({ type: "date", value: r.preferred_date || Shared.todayISO() }),
      start: input({ type: "time", value: r.preferred_start_time || "15:00" }),
      end: input({ type: "time", value: hasPrefEnd ? r.preferred_end_time : addMinutesTo(r.preferred_start_time || "15:00", dur) }),
      instructor: select({}, ""),
    };
    // M9: preferred end bo'lmasa — platforma standartini qo'llaymiz (start o'zgarganda ham)
    if (!hasPrefEnd) {
      f.start.addEventListener("change", () => { f.end.value = addMinutesTo(f.start.value, dur); });
    }
    instructors.forEach((i) => f.instructor.append(el("option", { value: i.id, text: i.first_name + " " + i.last_name + (i.car ? ` \u{1f697} ${i.car.brand} ${i.car.model}` : "") })));
    m.body.append(
      el("p", { class: "muted mb", text: `\u{1f4e8} ${r.first_name} ${r.last_name} \u2014 ${fmtDate(r.preferred_date || "\u2014")} ${r.preferred_start_time || ""}` }),
      el("div", { class: "grid-2" }, [
        field("\u{1f4c5} " + t("lesson.date"), f.date),
        el("div", { class: "row" }, [field("\u{1f552} " + t("lesson.start"), f.start, { class: "f1" }), field("\u{1f552} " + t("lesson.end"), f.end, { class: "f1" })]),
        field("\u{1f468}\u200d\u{1f3eb} " + t("lesson.instructor"), f.instructor),
      ]),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", icon: "check_circle", text: "" + t("req.approve"),
          onclick: async () => {
            try {
              await API.post(`admin/requests/${r.id}/approve`, {
                date: f.date.value, start_time: f.start.value, end_time: f.end.value, instructor_id: parseInt(f.instructor.value),
              });
              toast(t("misc.saved")); m.close(); App.refreshView();
            } catch (e) { errToast(e); }
          } }),
      ]),
    );
  }

  function rejectModal(r) {
    const ta = input({ placeholder: t("common.notes") + "..." });
    const m = modal("\u{1f534} " + t("req.reject"), [
      field(t("common.notes"), ta),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-danger", text: t("req.reject"),
          onclick: async () => {
            try { await API.post(`admin/requests/${r.id}/reject`, { note: ta.value }); toast(t("misc.saved")); m.close(); App.refreshView(); }
            catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* =====================================================================
     HISOBOTLAR (VAZIFA 1)

     Uchta tab:
       1) rep.tab.data   — statistik ko'rsatkichlar (avvalgi funksiya)
       2) rep.tab.creds  — foydalanuvchi ro'yxati eksporti
       3) rep.tab.import — CSV import

     Eksport paneli: toifa checkbox'lari (alohida yoki birgalikda),
     format (CSV/XLSX/PDF) va "login/parol" toggle-switch.

     XAVFSIZLIK: toggle YOQILGAN bo'lsa, backend FAQAT
     (Ism, Familiya, Guruh, Login, Parol) ustunlarini qaytaradi —
     statistika/jadval umuman qo'shilmaydi. Toggle O'CHIRILGAN bo'lsa,
     to'liq ma'lumot chiqadi, lekin login/parol ustunlari BO'LMAYDI.
     Ikki rejim hech qachon aralashmaydi (backend'da qat'iy ajratilgan).
     ===================================================================== */
  const REP_ROLES = [
    { key: "student", label: "rep.type.students", icon: "users" },
    { key: "instructor", label: "rep.type.instructors", icon: "instructor" },
    { key: "admin", label: "rep.type.admins", icon: "shield" },
  ];
  const REP_FORMATS = [
    { key: "csv", label: "rep.fmt.csv" },
    { key: "xlsx", label: "rep.fmt.xlsx" },
    { key: "pdf", label: "rep.fmt.pdf" },
  ];

  async function reports(params) {
    const wrap = el("div", {});
    const tabs = el("div", { class: "tabs mb" });
    const host = el("div", {});
    let tab = (params && params.tab === "creds") ? "creds"
            : (params && params.tab === "import") ? "import" : "data";
    /* Baza sahifasidan "Hisobot" tugmasi bilan kelganda toifa avtomatik
       tanlanadi (goReportsFor) — shunda foydalanuvchi hech narsa bosmaydi. */
    const preset = (params && (params.tab === "students" || params.tab === "instructors" || params.tab === "admins"))
      ? [{ students: "student", instructors: "instructor", admins: "admin" }[params.tab]] : [];

    const TABS = [
      { key: "data", label: "rep.tab.data" },
      { key: "creds", label: "rep.tab.creds" },
      { key: "import", label: "rep.tab.import" },
    ];
    function renderTabs() {
      tabs.innerHTML = "";
      TABS.forEach((tb) => {
        tabs.append(el("button", {
          class: "tab" + (tb.key === tab ? " active" : ""),
          text: "" + t(tb.label),
          onclick: () => { tab = tb.key; renderTabs(); renderHost(); },
        }));
      });
    }
    function renderHost() {
      host.innerHTML = "";
      if (tab === "data") host.append(statsPanel());
      else if (tab === "creds") host.append(exportPanel(preset));
      else host.append(importPanel());
    }
    wrap.append(tabs, host);
    renderTabs();
    renderHost();
    return wrap;
  }

  /* ---------------- 1) statistik ko'rsatkichlar paneli ---------------- */
  /* Bir statistik karta (ikonka + qiymat + yorliq). */
  function stat(ic, l, v) {
    return el("div", { class: "stat-card" }, [
      el("div", { class: "stat-icon", icon: ic }),
      el("div", {}, [el("div", { class: "stat-value", text: String(v) }),
        el("div", { class: "stat-label", text: l })]),
    ]);
  }

  function statsPanel() {
    const p = el("div", {});
    const periodSel = select({ daily: t("report.period.daily"), weekly: t("report.period.weekly"), monthly: t("report.period.monthly") }, "daily");
    const fromI = input({ type: "date" });
    const toI = input({ type: "date" });
    const host = el("div", {});
    const exportBar = el("div", { class: "row mb" });
    p.append(el("div", { class: "row mb wrap" }, [periodSel, field("", fromI), field("", toI),
      el("button", { class: "btn btn-primary", icon: "chart", text: "" + t("report.title"), onclick: load })]));
    p.append(exportBar, host);

    async function load() {
      host.innerHTML = ""; host.append(spinner());
      const q = new URLSearchParams({ period: periodSel.value });
      if (fromI.value) q.set("from", fromI.value);
      if (toI.value) q.set("to", toI.value);
      const res = (await API.get("admin/reports?" + q.toString())).reports;
      host.innerHTML = "";
      const m = res.metrics;
      const grid = el("div", { class: "grid-stats" }, [
        stat("calendar", t("report.sessions"), m.sessions), stat("check_circle", t("report.completed"), m.completed),
        stat("play", t("lesson.status.ongoing"), m.ongoing), stat("x", t("report.cancelled"), m.cancelled),
        stat("check", t("report.present"), m.present), stat("clock", t("report.late"), m.late),
        stat("alert_circle", t("report.absent"), m.absent), stat("users", t("stat.students"), m.students),
      ]);
      const ins = el("div", { class: "card" }, [
        el("h3", { icon: "instructor", text: "" + t("report.per_instructor") }), el("div", { class: "mt" }),
      ]);
      res.per_instructor.forEach(([name, v]) => ins.append(
        el("div", { class: "kv" }, [el("span", { class: "k", text: name }), el("span", { class: "v", text: `${v.sessions} ${t("report.sessions").toLowerCase()} \u00b7 ${v.completed} \u2705` })])));
      const carR = el("div", { class: "card" }, [
        el("h3", { icon: "car", text: "" + t("report.per_car") }), el("div", { class: "mt" }),
      ]);
      res.per_car.forEach(([k, v]) => carR.append(el("div", { class: "kv" }, [el("span", { class: "k", text: k }), el("span", { class: "v", text: `${v.sessions}` })])));
      host.append(grid, el("div", { class: "grid-2 mt" }, [ins, carR]));

      /* --- mashg'ulotlar hisoboti eksporti (eski funksiya saqlangan) --- */
      exportBar.innerHTML = "";
      exportBar.append(el("span", { class: "field-label", text: t("report.export") + ":" }));
      REP_FORMATS.forEach(({ key: fmt }) => {
        exportBar.append(el("button", { class: "btn btn-light btn-sm", text: t("rep.fmt." + fmt),
          onclick: async (ev) => {
            const b = ev.currentTarget;
            b.disabled = true;
            try {
              const q2 = new URLSearchParams({ report: "sessions", format: fmt, period: periodSel.value });
              if (fromI.value) q2.set("from", fromI.value);
              if (toI.value) q2.set("to", toI.value);
              const blob = await API.get("admin/export?" + q2.toString());
              if (!(blob instanceof Blob)) throw new Error("err.server_error");
              saveBlob(blob, "mashgulotlar." + fmt);
              toast(t("rep.exported"));
            } catch (e) { errToast(e); }
            finally { b.disabled = false; }
          } }));
      });
    }
    load();
    return p;
  }

  /* ---------------- 2) foydalanuvchi ro'yxati eksporti ---------------- */
  function exportPanel(preset) {
    const p = el("div", { class: "card" });
    /* --- holat: yangi obyekt, har o'zgarishda YANGI qiymat --- */
    const state = { roles: new Set(preset || []), format: "csv", creds: false, loading: false };

    const typeBox = el("div", { class: "rep-types" });
    const fmtBox = el("div", { class: "row wrap mb rep-fmts" });
    const dlBtn = el("button", { class: "btn btn-primary", icon: "download", text: "" + t("common.download") });
    const hintBox = el("div", {});
    const colBox = el("div", { class: "rep-cols muted" });

    /* --- toifa checkbox'lari --- */
    REP_ROLES.forEach((r) => {
      const cb = el("input", { type: "checkbox", class: "rep-cb", id: "reptype-" + r.key });
      cb.checked = state.roles.has(r.key);
      cb.addEventListener("change", () => {
        /* .add/.delete mutatsiya — render qayta ishga tushishi uchun
           quyidagi `sync()` chaqiriladi. */
        if (cb.checked) state.roles.add(r.key); else state.roles.delete(r.key);
        sync();
      });
      typeBox.append(el("label", { class: "rep-type", for: "reptype-" + r.key }, [
        cb, el("span", { class: "rep-type-ico", icon: r.icon }), el("span", { text: "" + t(r.label) }),
      ]));
    });

    /* --- format tugmalari --- */
    REP_FORMATS.forEach(({ key, label }) => {
      const b = el("button", {
        class: "btn btn-light btn-sm rep-fmt", text: "" + t(label),
        dataset: { fmt: key },
        onclick: () => { state.format = key; sync(); },
      });
      fmtBox.append(b);
    });

    /* --- login/parol toggle-switch ---
       Faqat `toggleRow` ichidagi switch ishlatiladi (u ham `toggleSwitch`dan
       quriladi). Alohida `toggleSwitch` nusxasi yaratilmaydi — aks holda
       ikkita boshqaruvchi bo'lardi va ulardan biri hech qachon ko'rinmasdi. */
    p.append(
      el("h3", { class: "mb", icon: "chart", text: "" + t("rep.pick_types") }),
      el("p", { class: "field-hint", text: "" + t("rep.pick_types_hint") }),
      typeBox,
      el("h4", { class: "card-title mt", text: "" + t("report.export") }),
      fmtBox,
      el("div", { class: "cred-list" }, [
        toggleRow({ title: t("rep.cred_toggle"), desc: t("rep.cred_toggle_hint"), checked: state.creds, onChange: (on) => { state.creds = on; sync(); } }),
      ]),
      hintBox, colBox,
      el("div", { class: "row end mt" }, [dlBtn]),
    );

    /* toggle`ning ikki nusxasi emas — faqat toggleRow ichidagi switch ishlatiladi */

    dlBtn.addEventListener("click", generate);

    /* ustunlar ro'yxati + ogohlantirish — rejimga qarab o'zgaradi */
    function sync() {
      fmtBox.querySelectorAll(".rep-fmt").forEach((b) => {
        b.classList.toggle("btn-primary", b.dataset.fmt === state.format);
        b.classList.toggle("btn-light", b.dataset.fmt !== state.format);
      });
      const n = state.roles.size;
      dlBtn.disabled = state.loading || n === 0;

      hintBox.innerHTML = "";
      if (state.creds) {
        /* --- REJIM A: login/parol FAQAT --- */
        hintBox.append(el("div", { class: "cred-warn", icon: "alert" }, [
          el("div", { class: "cred-warn-t", text: "" + t("rep.cred_toggle_warn") }),
        ]));
        hintBox.append(el("p", { class: "field-hint", text: "" + t("rep.pw_new_needed_hint") }));
        colBox.textContent = "" + t("rep.wrong_mode");
      } else {
        /* --- REJIM B: to'liq ma'lumot, login/parol YO'Q --- */
        colBox.textContent = "" + t("rep.wrong_mode");
      }
      colBox.dataset.mode = state.creds ? "creds" : "full";
    }

    async function generate() {
      if (state.loading) return;
      if (!state.roles.size) { errToast({ code: "rep.no_types", params: {} }); return; }
      state.loading = true;
      sync();
      const btnLabel = dlBtn.querySelector("span:not(.ico)") || null;
      dlBtn.textContent = "";
      dlBtn.append(el("i", { class: "ico ico-spin" }), document.createTextNode(" " + t("rep.generating")));
      try {
        const blob = await API.post("reports/generate", {
          report: "users",
          roles: Array.from(state.roles),
          format: state.format,
          include_credentials: state.creds,
          lang: (typeof I18N !== "undefined" && I18N.lang) ? I18N.lang : "uz",
        });
        if (!(blob instanceof Blob)) throw new Error("err.server_error");
        if (blob.size === 0) throw new Error("err.export.failed");
        saveBlob(blob, (state.creds ? "login_parollar." : "hisobot.") + state.format);
        toast(t("rep.exported"));
      } catch (e) { errToast(e); }
      finally {
        state.loading = false;
        sync();
        dlBtn.innerHTML = "";
        dlBtn.append(el("i", { class: "ico" }), document.createTextNode(" " + t("common.download")));
      }
    }

    sync();
    return p;
  }

  /* ---------------- 3) CSV import ---------------- */
  function importPanel() {
    const p = el("div", { class: "card" });
    const ta = el("textarea", {
      class: "input", style: "min-height:190px;font-family:monospace;font-size:13px",
      text: "first_name;last_name;middle_name;birth_date;phone;group_name;license_category;address;notes\nBekzod;Raimov;Akmalovich;2005-03-12;+998901112233;B-24;B;Farg'ona shahar;import",
    });
    p.append(
      el("h3", { class: "mb", icon: "download", text: "" + t("student.import") }),
      el("p", { class: "field-hint", text: "CSV: first_name;last_name;middle_name;birth_date;phone;group_name;license_category;address;notes" }),
      ta,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => { ta.value = ""; } }),
        el("button", { class: "btn btn-primary", text: t("common.create"), onclick: () => doImport(ta.value) }),
      ]),
      el("p", { class: "field-hint mt", text: "" + t("rep.audit_note") }),
    );
    return p;
  }

  async function doImport(csvText) {
    try {
      const res = await API.post("admin/students/import", { csv: csvText });
      const r = res.results;
      const box = el("div", {});
      [["\u{1f4c4}", t("common.all") + ":", r.total], ["\u2705", t("import.created"), r.created],
       ["\u26a0\ufe0f", t("import.duplicates"), r.duplicates], ["\u274c", t("import.errors"), r.errors.length],
      ].forEach(([a, b, c]) => box.append(el("div", { class: "kv" }, [
        el("span", { class: "k", text: a + " " + b }), el("span", { class: "v", text: String(c) })])));
      if (r.credentials && r.credentials.length) {
        box.append(el("h4", { class: "card-title mt", text: "\u{1f511} " + t("rep.tab.creds") }));
        r.credentials.slice(0, 20).forEach((cr, i) => box.append(el("div", { class: "kv" }, [
          el("span", { class: "k", text: "#" + (i + 1) }), el("span", { class: "v", text: cr.login + " / " + cr.password })])));
      }
      modal("\u{1f4e5} " + t("student.import"), [box,
        el("div", { class: "row end mt" }, [el("button", { class: "btn btn-primary", text: t("common.close"), onclick: (ev) => ev.target.closest(".modal-overlay").close() })]),
      ], { wide: true });
    } catch (e) { errToast(e); }
  }

  /* Blob'ni fayl sifatida saqlaydi (barcha eksportlar uchun umumiy). */
  function saveBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 600);
  }

  /* ============================ AUDIT (faoliyat jurnali) ============================ */
  /* MODUL 1: jadval ko'rinishida (Vaqt / Kim / Nima qildi / Kimga),
     filtrar: sana oralig'i, foydalanuvchi, amal turi, qidiruv maydoni. */
  const ACT_COLORS = {
    backup_created: "green", backup_restored: "red", backup_deleted: "late",
    login_changed: "blue",
    login: "blue", logout: "gray",
    user_created: "green", user_updated: "blue", user_deleted: "red",
    password_changed: "orange", password_reset: "orange",
    session_created: "green", session_cancelled: "red", session_rescheduled: "blue",
    request_approved: "green", request_rejected: "red",
  };

  async function audit(params) {
    params = params || {};
    const wrap = el("div", {}, [el("h3", { class: "mb", icon: "list", text: "" + t("audit.title") })]);

    /* --- filtrlar --- */
    const fFrom = input({ type: "date", class: "input" });
    const fTo = input({ type: "date", class: "input" });
    const fUser = select({ "": t("audit.all_users") });
    const fAction = select({ "": t("audit.all_actions") });
    const fQ = input({ class: "input", placeholder: t("audit.search_ph") });
    if (params.from) fFrom.value = params.from;
    if (params.to) fTo.value = params.to;
    if (params.user_id) fUser.value = String(params.user_id);
    if (params.action) fAction.value = params.action;

    const filters = el("div", { class: "card mb" }, [
      el("div", { class: "row wrap gap-sm" }, [
        el("label", { class: "fld-inline" }, [el("span", { class: "sm muted", text: t("audit.from") }), fFrom]),
        el("label", { class: "fld-inline" }, [el("span", { class: "sm muted", text: t("audit.to") }), fTo]),
        el("label", { class: "fld-inline" }, [el("span", { class: "sm muted", text: t("audit.user") }), fUser]),
        el("label", { class: "fld-inline" }, [el("span", { class: "sm muted", text: t("audit.action") }), fAction]),
        el("div", { class: "f1" }, [fQ]),
      ]),
      el("p", { class: "sm muted mt", text: t("audit.immutable_hint") }),
    ]);
    wrap.append(filters);
    const host = el("div", {});
    wrap.append(host);

    async function load() {
      host.innerHTML = ""; host.append(spinner());
      const qs = [];
      if (fFrom.value) qs.push("from=" + encodeURIComponent(fFrom.value));
      if (fTo.value) qs.push("to=" + encodeURIComponent(fTo.value));
      if (fUser.value) qs.push("user=" + encodeURIComponent(fUser.value));
      if (fAction.value) qs.push("action=" + encodeURIComponent(fAction.value));
      if (fQ.value.trim()) qs.push("q=" + encodeURIComponent(fQ.value.trim()));
      const res = await API.get("admin/audit" + (qs.length ? "?" + qs.join("&") : ""));

      /* filtr dropdownlarini to'ldirish (ma'lumotdan keladi) */
      if (res.user_options && res.user_options.length) {
        const cur = fUser.value;
        fUser.innerHTML = "";
        fUser.append(el("option", { value: "", text: t("audit.all_users") }));
        res.user_options.forEach((u) => fUser.append(el("option", { value: String(u.id), text: u.name })));
        fUser.value = cur;
      }
      if (res.action_options && res.action_options.length) {
        const cur = fAction.value;
        fAction.innerHTML = "";
        fAction.append(el("option", { value: "", text: t("audit.all_actions") }));
        res.action_options.forEach((a) => fAction.append(el("option", { value: a, text: t("audit.act." + a) !== ("audit.act." + a) ? t("audit.act." + a) : a })));
        fAction.value = cur;
      }

      host.innerHTML = "";
      if (!res.logs.length) { host.append(emptyState("\u{1f4dc}", t("audit.empty"))); return; }
      const tbl = el("table", { class: "tbl" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("audit.time") }), el("th", { text: t("audit.who") }),
          el("th", { text: t("audit.did") }), el("th", { text: t("audit.target") }),
        ])]),
        el("tbody", {}, res.logs.map((l) => el("tr", {}, [
          el("td", { text: fmtDateTime(l.timestamp) }),
          el("td", {}, [el("span", { class: "cell-strong", text: l.user_name || t("audit.system") })]),
          el("td", {}, [badge(ACT_COLORS[l.action_type] || "blue", t("audit.act." + l.action_type) !== ("audit.act." + l.action_type) ? t("audit.act." + l.action_type) : l.action_type)]),
          el("td", { text: (l.description || (l.target_type ? l.target_type + (l.target_id ? " #" + l.target_id : "") : "")) || "\u2014", class: "muted" }),
        ]))),
      ]);
      host.append(el("div", { class: "tbl-wrap" }, [tbl]));
    }
    [fFrom, fTo, fUser, fAction].forEach((c) => c.addEventListener("change", load));
    let qt = null;
    fQ.addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(load, 250); });
    load();
    return wrap;
  }

  /* ============================ BACKUP (zaxira nusxa) ============================ */
  /* MODUL 1: qo'lda yaratish, ro'yxat, yuklab olish va tiklash.
     Tiklash JUDA xavfli amal -> ikki bosqichli tasdiqlash:
     1) ogohlantirish oynasi, 2) "TASDIQLASH" so'zini qo'lda kiritish. */
  function backupSize(bytes) {
    const b = Number(bytes) || 0;
    if (b >= 1048576) return (b / 1048576).toFixed(2) + " MB";
    return (b / 1024).toFixed(1) + " KB";
  }

  function backupTime(ts) {
    const n = Number(ts) * 1000;
    if (!n) return "\u2014";
    const d = new Date(n);
    return d.toLocaleString("uz-UZ");
  }

  /* Ikki bosqichli tiklash tasdig'i: avval ogohlantirish, keyin
     "TASDIQLASH" so'zini qo'lda kiritish shart. */
  function restoreConfirm(name, onDone) {
    const inp = input({ class: "input", placeholder: t("backup.restore_word"), autocomplete: "off" });
    const m = modal("\u26a0\ufe0f " + t("backup.restore_title"), [
      el("p", { class: "confirm-text", text: t("backup.restore_warn") }),
      el("p", { class: "muted sm", text: name }),
      el("p", { class: "mt sm", text: t("backup.restore_type") }),
      inp,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-danger", text: t("backup.restore_go"), onclick: () => {
          if (String(inp.value).trim().toUpperCase() !== "TASDIQLASH") {
            inp.classList.add("input-error");
            toast(t("backup.restore_wrong"), "error");
            return;
          }
          m.close(); onDone();
        } }),
      ]),
    ]);
    return m;
  }

  async function backup() {
    const wrap = el("div", {}, []);
    const createBtn = el("button", { class: "btn btn-primary", icon: "save", text: "" + t("backup.create"), onclick: async () => {
      createBtn.disabled = true;
      try { const r = await API.post("admin/backup"); toast(t("backup.created") + ": " + r.file); await loadList(); }
      catch (e) { errToast(e); }
      finally { createBtn.disabled = false; }
    } });
    const host = el("div", {});
    wrap.append(el("div", { class: "row between mb" }, [
      el("h3", { icon: "download", text: "" + t("backup.title") }),
      createBtn,
    ]), host);

    async function loadList() {
      host.innerHTML = ""; host.append(spinner());
      const r = await API.get("admin/backup");
      host.innerHTML = "";
      if (!r.backups.length) { host.append(emptyState("\u{1f5be}", t("backup.empty"))); return; }
      const tbl = el("table", { class: "tbl" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("backup.file") }), el("th", { text: t("common.date") }),
          el("th", { text: t("backup.size") }), el("th", { text: t("common.actions") }),
        ])]),
        el("tbody", {}, r.backups.map((b) => el("tr", {}, [
          el("td", { text: b.name }),
          el("td", { text: backupTime(b.time) }),
          el("td", { text: backupSize(b.size) }),
          el("td", {}, [el("div", { class: "row gap-sm" }, [
            el("button", { class: "btn btn-light btn-sm", icon: "download", text: "" + t("backup.download"),
              onclick: async () => {
                try {
                  const res = await API.get("admin/backup?download=" + encodeURIComponent(b.name));
                  if (res.download && res.download.b64) saveBlob(res.download.b64, res.download.filename || b.name, res.download.mime || "application/octet-stream");
                  else toast(t("backup.download_failed"), "error");
                } catch (e) { errToast(e); }
              } }),
            el("button", { class: "btn btn-light btn-sm", icon: "refresh", text: "" + t("backup.restore"),
              onclick: () => restoreConfirm(b.name, async () => {
                try { await API.post("admin/backup", { action: "restore", filename: b.name }); toast(t("backup.restored")); }
                catch (e) { errToast(e); }
              }) }),
            el("button", { class: "btn btn-danger btn-sm", icon: "trash", text: "" + t("backup.delete"),
              onclick: () => UI.confirmDialog(t("backup.delete_confirm"), async () => {
                try { await API.del("admin/backup?name=" + encodeURIComponent(b.name)); toast(t("backup.deleted")); await loadList(); }
                catch (e) { errToast(e); }
              }) }),
          ])]),
        ]))),
      ]);
      host.append(el("div", { class: "tbl-wrap" }, [tbl]));
    }
    loadList();
    return wrap;
  }

  /* ============================ SOZLAMALAR ============================ */
  async function settings() {
    return Shared.settingsPage({ isAdmin: true });
  }

  /* ============================ PROFIL (Modul 11) ============================ */
  async function profile() {
    const u = App.me.user;
    return Shared.renderProfile({
      roleLabel: t("auth.role_admin"),
      kvs: [
        [t("common.phone"), u.phone || "\u2014"],
        [t("common.login"), u.login],
      ],
    });
  }

  /* ============================ ANALITIKA (M13-B) ============================ */
  async function analytics() {
    const now = new Date();
    const opts = [];
    for (let k = 11; k >= 0; k--) {
      const d = new Date(now.getFullYear(), now.getMonth() - k, 1);
      const ym = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
      opts.push({ ym, label: monthShort(d.getMonth()) + " " + d.getFullYear() });
    }
    // select() options ob'ektini kutadi — bo'sh {} berib, optionlarni
    // qo'lda qo'shamiz va joriy oyni tanlangan qilib belgilaymiz.
    const monSel = select({}, "");
    opts.forEach((o) => monSel.append(el("option", { value: o.ym, text: o.label })));
    monSel.value = opts[opts.length - 1].ym;
    const host = el("div", { class: "mt" });
    const wrap = el("div", {}, [el("div", { class: "card" }, [
      el("div", { class: "row between mb" }, [
        el("h3", { class: "card-title", icon: "search", text: "\u{1f4c8} " + t("nav.analytics") }),
        field(t("analytics.month"), monSel, { class: "f2" }),
      ]),
    ]), host]);
    async function load() {
      host.innerHTML = ""; host.append(spinner());
      const a = (await API.get("admin/analytics?month=" + monSel.value)).analytics || {};
      const cards = [
        ["calendar", t("analytics.total"), a.total],
        ["check_circle", t("analytics.completed"), a.completed],
        ["x", t("analytics.cancelled"), a.cancelled],
        ["chart", t("analytics.cancel_rate"), (a.cancel_rate != null ? a.cancel_rate : 0) + "%"],
        ["clock", t("analytics.hours"), a.hours],
        ["student", t("analytics.students"), a.unique_students],
      ];
      const grid = el("div", { class: "grid-stats" });
      cards.forEach(([icon, label, val]) => grid.append(
        el("div", { class: "stat-card" }, [
          el("div", { class: "stat-icon", icon }),
          el("div", {}, [el("div", { class: "stat-value", text: String(val) }), el("div", { class: "stat-label", text: label })]),
        ])));

      // Kunlik faollik grafigi (oy kunlari bo'yicha)
      const days = a.days || [];
      const maxC = Math.max(1, ...days.map((b) => b.sessions));
      const dCard = el("div", { class: "card" }, [
        el("div", { class: "row between mb" }, [
          el("h3", { class: "card-title", text: "\u{1f4ca} " + t("analytics.daily_chart") }),
          el("span", { class: "muted sm", text: t("analytics.cancel_mark") }),
        ]),
        el("div", { class: "bar-chart" }, days.map((b) => {
          const h = Math.max(4, Math.round((b.sessions / maxC) * 120));
          return el("div", {
            class: "chart-col" + (b.cancelled ? " chart-cancel" : ""),
            title: b.day + ": " + b.sessions + " / \u274c " + b.cancelled,
          }, [
            el("div", { class: "chart-val", text: String(b.sessions) }),
            el("div", { class: "chart-bar", style: "height:" + h + "px" }),
            el("div", { class: "chart-label", text: String(b.day) }),
          ]);
        })),
      ]);

      // Oylik tendentsiya (12 oy)
      const mD = a.months || [];
      const maxM = Math.max(1, ...mD.map((b) => b.sessions));
      const mCard = el("div", { class: "card" }, [
        el("h3", { class: "card-title", text: "\u{1f4c8} " + t("analytics.monthly_chart") }),
        el("div", { class: "bar-chart" }, mD.map((b) => {
          const h = Math.max(4, Math.round((b.sessions / maxM) * 120));
          return el("div", {
            class: "chart-col" + (b.cancelled ? " chart-cancel" : ""),
            title: b.month + ": " + b.sessions + " / \u274c " + b.cancelled,
          }, [
            el("div", { class: "chart-val", text: String(b.sessions) }),
            el("div", { class: "chart-bar", style: "height:" + h + "px" }),
            el("div", { class: "chart-label", text: b.month.slice(5) }),
          ]);
        })),
      ]);

      // Eng band instruktorlar
      const top = a.top_instructors || [];
      const topCard = el("div", { class: "card" }, [
        el("h3", { class: "card-title", text: "\u{1f3c6} " + t("analytics.top_instructors") }),
      ]);
      if (!top.length) {
        topCard.append(emptyState("\u{1f3c6}", t("analytics.no_data")));
      } else {
        const list = el("div", { class: "mt" });
        top.forEach((it, i) => list.append(el("div", { class: "row between pv" }, [
          el("div", { class: "row" }, [
            el("span", { class: "rank" + (i < 3 ? " rank-top" : ""), text: String(i + 1) }),
            el("span", { class: "cell-strong", text: it.name }),
          ]),
          el("div", { class: "muted sm", text: "" + it.sessions + " " + t("week.sessions").toLowerCase() + (it.cancelled ? " \u00b7 \u274c " + it.cancelled : "") }),
        ])));
        topCard.append(list);
      }

      host.innerHTML = "";
      host.append(grid, el("div", { class: "grid-2 mt" }, [dCard, mCard]), el("div", { class: "mt" }, [topCard]));
    }
    monSel.addEventListener("change", load);
    load();
    return wrap;
  }

  /* MODUL 3: `importModal` eksportga qo'shildi — endi faqat "Hisobotlar"
     bo'limidagi "Import" tab orqali ochiladi (Baza bo'limidan olib
     tashlandi, lekin funksiya O'CHIRILMADI). */
  return { dashboard, base, users, students, instructors, cars, lessons, calendar, requests, reports, analytics, audit, backup, settings, profile, importModal, notifications: () => Shared.notificationsPage() };
})();
