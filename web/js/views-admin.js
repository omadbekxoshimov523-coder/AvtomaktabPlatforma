/* ADMIN ko'rinishlari: Dashboard, Yangi baza, Talabalar, Instruktorlar,
   Avtomobillar, Mashg'ulotlar, Kalendar, So'rovlar, Hisobotlar, Audit,
   Bildirishnomalar, Sozlamalar, Backup */
window.AdminViews = (function () {
  const { t, fmtDate, fmtDateTime, errorText, monthShort } = I18N;
  const UI = window.UI;
  const { el, toast, errToast, badge, statusText, avatar, carPhoto, field, input, select, modal, emptyState, spinner, confirmDialog, callLink, mapLink, timeline, checklist, notifMini } = UI;

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
        el("h3", { class: "card-title", text: "📊 " + t("week.chart_title") }),
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
      el("h3", { class: "card-title", text: "📅 " + t("dash.today_sessions_title") }),
    ]);
    if (!sessList.length) {
      sessCard.append(emptyState("📭", t("today.no_sessions")));
    } else {
      const tbl = el("table", { class: "tbl" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "🕒" }), el("th", { text: t("lesson.instructor") }),
          el("th", { text: "🚗 " + t("lesson.car") }), el("th", { text: "👥 " + t("car.capacity") }), el("th", { text: t("common.status") }),
        ])]),
        el("tbody", {}, sessList.map((s) => el("tr", { class: "row-click", onclick: () => Shared.openSession(s.id, "admin") }, [
          el("td", { text: `${s.start_time}–${s.end_time}` }),
          el("td", { text: s.instructor_name || "—" }),
          el("td", { class: "muted", text: (s.car_name_snapshot || "—") + (s.car_plate_snapshot ? " · " + s.car_plate_snapshot : "") }),
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
        el("div", { class: "session-time", text: `${s.start_time}–${s.end_time}` }),
        badge(s.status, statusText(s.status)),
      ]),
      el("div", { class: "session-meta" }, [
        el("div", { icon: "instructor", text: "" + (s.instructor_name || "") }),
        el("div", { icon: "car", text: "" + (s.car_name_snapshot || "—") + " · " + (s.car_plate_snapshot || "") }),
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
        el("button", { class: "btn btn-light", text: "⚡ " + t("student.bulk"),
          onclick: () => bulkModal() }),
        el("button", { class: "btn btn-light", icon: "download", text: "" + t("student.import"),
          onclick: () => importModal() }),
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
      if (!users.length) { host.append(emptyState("👥", t("instructor.students_empty"))); return; }
      const tbl = el("table", { class: "tbl" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("common.name") }), el("th", { text: "Rol" }),
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
            el("td", { text: u.role }),
            el("td", { text: u.phone || "—" }),
            el("td", { text: info.join(", ") || "—" }),
            el("td", {}, [statusBadge(u)]),
            el("td", {}, [el("div", { class: "actions" }, [
              el("button", { class: "btn btn-light btn-sm", text: "✏️", onclick: () => editUser(u) }),
              u.role !== "admin" ? el("button", { class: "btn btn-light btn-sm", text: "🔑", onclick: () => resetPass(u) }) : null,
              u.role === "instructor" && u.instructor ? el("button", { class: "btn btn-light btn-sm", text: "🚗", onclick: () => Shared.openUserForm("instructor", u) }) : null,
              u.role !== "admin" ? el("button", { class: "btn btn-light btn-sm", text: u.status === "blocked" ? "🔓" : "🔒",
                onclick: () => toggleBlock(u) }) : null,
              u.role !== "admin" ? el("button", { class: "btn btn-danger btn-sm", text: "🗑",
                onclick: () => confirmDialog(t("common.delete") + "?", async () => {
                  try { await API.del(`admin/users/${u.id}`); toast(t("misc.saved")); load(); }
                  catch (e) { errToast(e); }
                }, { danger: true }) }) : null,
            ])]),
          ]);
        })),
      ]);
      host.append(tbl);
    }
    function statusBadge(u) {
      if (u.deleted_at) return badge("archived", statusText("archived"));
      return badge(u.status, u.status === "active" ? t("student.status.active") : u.status === "blocked" ? t("stat.blocked") : t("stat.archived"));
    }
    function editUser(u) { Shared.openUserForm(u.role, u); }
    async function resetPass(u) {
      try {
        const res = await API.post(`admin/users/${u.id}/reset-password`);
        Shared.openUserCredentials({ login: res.login, password: res.password });
      } catch (e) { errToast(e); }
    }
    async function toggleBlock(u) {
      try {
        await API.post(`admin/users/${u.id}/status`, { status: u.status === "blocked" ? "unblock" : "block" });
        toast(t("misc.saved")); load();
      } catch (e) { errToast(e); }
    }
    [searchI, roleSel, statusSel].forEach((c) => c.addEventListener("change", load));
    let timer;
    searchI.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(load, 350); });
    load();
    return wrap;
  }

  function bulkModal() {
    const countI = select({ "10": "10", "50": "50", "100": "100", "500": "500", "1000": "1000" }, "10");
    const m = modal("⚡ " + t("nav.students") + " — Bulk", [
      field(t("student.bulk") + " — " + t("common.count"), countI),
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
              modal("✅ " + t("misc.success") + ` (${res.count})`, [list, el("div", { class: "row end mt" }, [el("button", { class: "btn btn-primary", text: t("common.close"), onclick: () => App.refreshView() })]), ], { wide: true });
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
    const m = modal("📥 " + t("student.import"), [
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
                ["📄", t("common.all") + ":", r.total],
                ["✅", t("import.created"), r.created],
                ["⚠️", t("import.duplicates"), r.duplicates],
                ["❌", t("import.errors"), r.errors.length],
              ];
              const box = el("div", {});
              rows.forEach(([a, b, c]) => box.append(el("div", { class: "kv" }, [el("span", { class: "k", text: a + " " + b }), el("span", { class: "v", text: String(c) })])));
              if (r.credentials.length) {
                box.append(el("h4", { class: "card-title mt", text: "🔑 Login/Parol" }));
                r.credentials.slice(0, 20).forEach((cr, i) => box.append(el("div", { class: "kv" }, [
                  el("span", { class: "k", text: `#${i + 1}` }), el("span", { class: "v", text: cr.login + " / " + cr.password })])));
              }
              // xatolar
              modal("📥 " + t("student.import"), [box,
                el("div", { class: "row end mt" }, [el("button", { class: "btn btn-primary", text: t("common.close"), onclick: (ev) => ev.target.closest(".modal-overlay").close() })]),
              ], { wide: true });
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
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

  // Eski havolalar (kichik o'zgarish uchun saqlanadi)
  function students(params) { return users({ tab: "student" }); }
  function instructors(params) { return users({ tab: "instructor" }); }

  function userSearchBox(placeholder) {
    return input({ type: "search", placeholder: placeholder || (t("common.search") + "...") });
  }
  function debounce(fn, ms) {
    let tm;
    return () => { clearTimeout(tm); tm = setTimeout(fn, ms || 300); };
  }

  /* ------------------------------ TALABALAR ------------------------------ */
  function studentsTable(host) {
    const searchI = userSearchBox(t("users.search_student"));
    const addB = el("button", {
      class: "btn btn-primary", icon: "plus", text: "" + t("student.add"),
      onclick: () => Shared.openUserForm("student"),
    });
    host.append(el("div", { class: "row between mb" }, [searchI, addB]));

    async function load() {
      host.innerHTML = "";
      host.append(spinner());
      const res = await API.get("admin/users?role=student&q=" + encodeURIComponent(searchI.value));
      const list = res.users.filter((u) => !u.deleted_at);
      host.innerHTML = "";
      host.append(el("div", { class: "row between mb" }, [searchI, addB]));
      if (!list.length) { host.append(emptyState("👨‍🎓", t("users.empty_student"))); return; }

      const tbl = el("table", { class: "tbl" }, [el("thead", {}, [el("tr", {}, [
        el("th", { text: t("common.name") }),
        el("th", { text: t("student.group") }),
        el("th", { text: t("student.category") }),
        el("th", { text: t("users.instructor") }),
        el("th", { text: t("users.progress") }),
        el("th", { text: t("common.phone") }),
        el("th", { text: t("common.status") }),
        el("th", { text: t("common.actions") }),
      ])]), el("tbody", {}, list.map((u) => {
        const pr = u.progress || { done: 0, total: 0, pct: 0 };
        const names = (u.instructors || []).map((x) => x.name);
        return el("tr", {}, [
          el("td", {}, [el("div", { class: "user-cell" }, [avatar(u, 34), el("div", {}, [
            el("div", { class: "cell-strong", text: `${u.first_name} ${u.last_name}` }),
            el("div", { class: "muted", text: u.login })])])]),
          el("td", { text: (u.student && u.student.group_name) || "—" }),
          el("td", { text: (u.student && u.student.license_category) || "—" }),
          el("td", {}, [names.length
            ? el("span", { text: names.length > 2 ? names.slice(0, 2).join(", ") + ` +${names.length - 2}` : names.join(", ") })
            : el("span", { class: "muted", text: "—" })]),
          el("td", {}, [el("div", { class: "prog-mini" }, [
            el("div", { class: "prog-mini-bar" }, [el("i", { style: `width:${pr.pct}%` })]),
            el("span", { class: "muted sm", text: `${pr.done}/${pr.total}` }),
          ])]),
          el("td", { text: u.phone || "—" }),
          el("td", {}, [badge(u.status, u.status === "active" ? t("student.status.active") : t("stat.blocked"))]),
          el("td", {}, [el("div", { class: "actions" }, [
            el("button", { class: "btn btn-light btn-sm", text: "✏️", onclick: () => Shared.openUserForm("student", u) }),
            el("button", { class: "btn btn-danger btn-sm", text: "🗑", onclick: () => confirmDialog(t("users.delete_confirm", { name: `${u.first_name} ${u.last_name}` }), async () => {
              try { await API.del(`admin/users/${u.id}`); toast(t("misc.saved")); load(); } catch (e) { errToast(e); }
            }, { danger: true }) }),
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
    host.append(el("div", { class: "row between mb" }, [searchI, addB]));

    async function load() {
      host.innerHTML = "";
      host.append(spinner());
      const res = await API.get("admin/users?role=instructor&q=" + encodeURIComponent(searchI.value));
      const list = res.users.filter((u) => !u.deleted_at);
      host.innerHTML = "";
      host.append(el("div", { class: "row between mb" }, [searchI, addB]));
      if (!list.length) { host.append(emptyState("🚗", t("users.empty_instructor"))); return; }

      const tbl = el("table", { class: "tbl" }, [el("thead", {}, [el("tr", {}, [
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
        return el("tr", {}, [
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
          el("td", { text: (inst.work_start ? `${inst.work_start}–${inst.work_end}` : "—") }),
          el("td", { text: u.phone || "—" }),
          el("td", {}, [badge(u.status, u.status === "active" ? t("student.status.active") : t("stat.blocked"))]),
          el("td", {}, [el("div", { class: "actions" }, [
            el("button", { class: "btn btn-light btn-sm", text: "✏️", onclick: () => Shared.openUserForm("instructor", u) }),
            el("button", { class: "btn btn-cyan btn-sm", icon: "car", text: "" + t("car.reassign"), onclick: () => assignCarModal(u) }),
            el("button", { class: "btn btn-danger btn-sm", text: "🗑", onclick: () => confirmDialog(t("users.delete_confirm", { name: `${u.first_name} ${u.last_name}` }), async () => {
              try { await API.del(`admin/users/${u.id}`); toast(t("misc.saved")); load(); } catch (e) { errToast(e); }
            }, { danger: true }) }),
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
    const bar = el("div", { class: "row between mb" }, [
      searchI,
      el("span", { class: "muted sm", text: t("users.admins_hint") }),
    ]);
    host.append(bar);

    async function load() {
      host.innerHTML = "";
      host.append(spinner());
      const res = await API.get("admin/users?role=admin&q=" + encodeURIComponent(searchI.value));
      const list = res.users.filter((u) => !u.deleted_at);
      host.innerHTML = "";
      host.append(bar);
      if (!list.length) { host.append(emptyState("🛡️", t("users.empty_admin"))); return; }

      const tbl = el("table", { class: "tbl" }, [el("thead", {}, [el("tr", {}, [
        el("th", { text: t("common.name") }),
        el("th", { text: t("users.perms") }),
        el("th", { text: t("users.last_login") }),
        el("th", { text: t("common.phone") }),
        el("th", { text: t("common.status") }),
      ])]), el("tbody", {}, list.map((u) => el("tr", {}, [
        el("td", {}, [el("div", { class: "user-cell" }, [avatar(u, 34), el("div", {}, [
          el("div", { class: "cell-strong", text: `${u.first_name} ${u.last_name}` }),
          el("div", { class: "muted", text: u.login })])])]),
        el("td", {}, [el("span", { class: "badge badge-cyan", text: t("auth.role_admin") })]),
        el("td", { text: u.last_login_at || "—" }),
        el("td", { text: u.phone || "—" }),
        el("td", {}, [badge(u.status, u.status === "active" ? t("student.status.active") : t("stat.blocked"))]),
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
    const sel = select({ "": "— " + t("car.not_assigned") + " —" }, instructor.assigned_car_id || "", {});
    cars.forEach((c) => sel.append(el("option", { value: c.id, text: `${c.brand} ${c.model} — ${c.plate_number} (${statusText(c.status)})`, selected: instructor.assigned_car_id === c.id ? "selected" : "" })));
    const m = modal("🚗 " + t("car.reassign") + " — " + instructor.first_name + " " + instructor.last_name, [
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
      if (!r2.cars.length) { host.append(emptyState("🚗", t("car.not_assigned"))); return; }
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
            el("div", { text: `📅 ${c.year || "—"} · ${c.color || ""}` }),
            el("div", { text: `👥 ${t("car.capacity")}: ${c.practice_capacity}` }),
            el("div", { text: `🩺 ${t("car.inspection")}: ${c.technical_inspection_date || "—"}` }),
            el("div", { text: `🛡️ ${t("car.insurance")}: ${c.insurance_expiry || "—"}` }),
            el("div", { text: `${t("car.assigned_to")}: ${r2.assigned_to[c.id] || "—"}` }),
            el("div", { text: `📷 ${photos.length ? photos.length + " " + t("car.photo_count") : t("car.no_photos")}` }),
          ]),
          el("div", { class: "row between mt car-actions" }, [
            stSel,
            el("div", { class: "actions" }, [
              el("button", { class: "btn btn-light btn-sm", title: t("car.photos"), text: "📷",
                onclick: () => carPhotosModal(c) }),
              el("button", { class: "btn btn-light btn-sm", text: "✏️", onclick: () => carModal(c) }),
              el("button", { class: "btn btn-danger btn-sm", text: "🗑", onclick: () => confirmDialog("Delete?", async () => {
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
        field("🔢 " + t("car.plate"), f.plate), field(t("car.year"), f.year),
        field(t("car.color"), f.color), field(t("car.seats"), f.seats),
        field("👥 " + t("car.capacity"), f.capacity), field(t("car.status"), f.status),
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
    const m = modal("📷 " + car.plate_number + " · " + t("car.photos"), [
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
      if (!photos.length) { grid.append(emptyState("📷", t("car.no_photos"))); return; }
      photos.forEach((p) => {
        const del = el("button", { class: "btn btn-danger btn-sm photo-del", text: "✕",
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
      if (!res.sessions.length) list.append(emptyState("📚", t("lesson.empty_today")));
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
    f.car = el("div", { class: "input readonly", text: "—" });
    f.cap = el("div", { class: "input readonly", text: "—" });
    const studSelWrap = el("div", {});
    const addedList = el("div", { class: "mt" });
    const added = [];

    const studentsRes = await API.get("admin/users?role=student&status=active");
    const allStudents = studentsRes.users.filter((u) => u.student && !u.deleted_at);

    function renderStudents() {
      studSelWrap.innerHTML = "";
      const sel = select({});
      allStudents.forEach((u) => {
        if (!added.includes(String(u.student.id))) sel.append(el("option", { value: u.student.id, text: `${u.first_name} ${u.last_name} (${u.student.group_name || ""})` }));
      });
      const addBtn = el("button", { class: "btn btn-cyan btn-sm", icon: "plus", text: "" + t("lesson.add_student"),
        onclick: () => { const v = sel.value; if (v && !added.includes(v)) added.push(v); renderStudents(); } });
      studSelWrap.append(el("div", { class: "row" }, [el("div", { class: "f1" }, [sel]), addBtn]));
      addedList.innerHTML = "";
      // f.cap div elementi — sig'im "🔒 N" shaklida textContent'da turadi
      const capNum = f.cap.textContent !== "—" ? parseInt(String(f.cap.textContent).replace("🔒 ", "") || "0") : 0;
      if (capNum && added.length > capNum) {
        addedList.append(el("div", { class: "muted mt", icon: "alert", text: "" + t("lesson.capacity_full_warn") }));
      }
      added.forEach((sid) => {
        const u = allStudents.find((x) => String(x.student.id) === String(sid));
        const line = el("div", { class: "kv" }, [
          el("span", { class: "k", icon: "graduation", text: " 👨" + (u ? `${u.first_name} ${u.last_name}` : sid) }),
          el("button", { class: "btn btn-ghost", text: "✕", onclick: () => { added.splice(added.indexOf(sid), 1); renderStudents(); } }),
        ]);
        addedList.append(line);
      });
    }

    async function onInstructor() {
      const inst = instructors.find((i) => String(i.id) === String(f.instructor.value));
      if (inst && inst.car) {
        f.car.textContent = "🔒 " + inst.car.brand + " " + inst.car.model + " — " + inst.car.plate_number;
        f.cap.textContent = "🔒 " + inst.car.practice_capacity;
        renderStudents();
      } else {
        f.car.textContent = "—";
        f.cap.textContent = "—";
        addedList.innerHTML = "";
      }
    }

    const m = modal(t("lesson.create_title"), [
      el("div", { class: "grid-2" }, [
        field("📅 " + t("lesson.date"), f.date),
        el("div", { class: "row" }, [field("🕒 " + t("lesson.start"), f.start, { class: "f1" }), field("🕒 " + t("lesson.end"), f.end, { class: "f1" })]),
        field("👨‍🏫 " + t("lesson.instructor"), f.instructor),
        field("🚗 " + t("lesson.car"), f.car),
        field("👥 " + t("lesson.capacity"), f.cap),
      ]),
      el("div", { class: "mt" }, [
        el("div", { class: "field-label", icon: "graduation", text: " 👨" + t("lesson.students") + " " + (f.cap.textContent !== "—" ? `(${added.length}/${f.cap.textContent.replace("🔒 ", "")})` : "") }),
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
              toast(t("misc.saved") + " 🚗 " + res.auto.car);
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
    const prevB = el("button", { class: "btn btn-light btn-sm", text: "←", onclick: () => { anchor = shift(anchor, -1); load(); } });
    const nextB = el("button", { class: "btn btn-light btn-sm", text: "→", onclick: () => { anchor = shift(anchor, 1); load(); } });
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
        el("strong", { text: fmtDate(anchor) + (view !== "day" ? ` – ${fmtDate(shift(anchor, 1))}` : "") }));
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
          el("div", { class: "day-head", text: fmtDate(d) + (evts.length ? ` · ${evts.length}` : "") }),
          ...(evts.length ? evts.slice(0, 8).map((e) => sessionMini(e)) : [el("div", { class: "muted", text: "—" })]),
        ]));
      });
      host.append(grid);
    }
    function sessionMini(s) {
      return el("div", { class: "cal-evt " + s.status, dataset: { sid: s.id }, onclick: () => Shared.openSession(s.id, "admin") }, [
        el("strong", { text: `${s.start_time}–${s.end_time}` }),
        el("div", { icon: "instructor", text: "" + s.instructor_name }),
        el("div", { class: "muted sm", icon: "car", text: "" + (s.car_name_snapshot || "") + " · 👥 " + s.student_count + "/" + s.capacity_snapshot }),
      ]);
    }
    buildViews();
    load();
    return wrap;
  }

  /* ============================ SO'ROVLAR ============================ */
  async function requests() {
    const res = await API.get("admin/requests");
    const wrap = el("div", {}, [el("h3", { class: "mb", text: "📨 " + t("nav.requests") })]);
    if (!res.requests.length) { wrap.append(emptyState("📨", t("req.title"))); return wrap; }
    const list = el("div", { class: "grid-2" });
    res.requests.forEach((r) => {
      list.append(el("div", { class: "card" }, [
        el("div", { class: "row between mb" }, [
          el("div", { class: "user-cell" }, [avatar(r, 34), el("div", {}, [
            el("strong", { text: `${r.first_name} ${r.last_name}` }),
            el("div", { class: "muted sm", text: r.group_name || "" }),
          ])]),
          badge(r.status, statusText(r.status)),
        ]),
        el("div", { class: "muted sm" }, [
          el("div", { icon: "calendar", text: "" + t("req.preferred") + ": " + (r.preferred_date ? fmtDate(r.preferred_date) : "—") + " " + (r.preferred_start_time ? r.preferred_start_time + "–" + r.preferred_end_time : "") }),
          el("div", { icon: "message", text: "" + (r.message || "—") }),
        ]),
        r.status === "pending" ? el("div", { class: "row mt" }, [
          el("button", { class: "btn btn-primary btn-sm f1", icon: "check_circle", text: "" + t("req.approve"), onclick: () => approveModal(r) }),
          el("button", { class: "btn btn-danger btn-sm f1", icon: "checkup", text: "" + t("req.reject"), onclick: () => rejectModal(r) }),
        ]) : null,
      ]));
    });
    wrap.append(list);
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
    instructors.forEach((i) => f.instructor.append(el("option", { value: i.id, text: i.first_name + " " + i.last_name + (i.car ? ` 🚗 ${i.car.brand} ${i.car.model}` : "") })));
    m.body.append(
      el("p", { class: "muted mb", text: `📨 ${r.first_name} ${r.last_name} — ${fmtDate(r.preferred_date || "—")} ${r.preferred_start_time || ""}` }),
      el("div", { class: "grid-2" }, [
        field("📅 " + t("lesson.date"), f.date),
        el("div", { class: "row" }, [field("🕒 " + t("lesson.start"), f.start, { class: "f1" }), field("🕒 " + t("lesson.end"), f.end, { class: "f1" })]),
        field("👨‍🏫 " + t("lesson.instructor"), f.instructor),
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
    const m = modal("🔴 " + t("req.reject"), [
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

  /* ============================ HISOBOTLAR ============================ */
  async function reports() {
    const wrap = el("div", {}, []);
    const periodSel = select({ daily: t("report.period.daily"), weekly: t("report.period.weekly"), monthly: t("report.period.monthly") }, "daily");
    const fromI = input({ type: "date" });
    const toI = input({ type: "date" });
    const host = el("div", {});
    const exportBar = el("div", { class: "row mb" });
    wrap.append(el("div", { class: "row mb wrap" }, [periodSel, field("", fromI), field("", toI),
      el("button", { class: "btn btn-primary", icon: "chart", text: "" + t("report.title"), onclick: load })]));
    wrap.append(exportBar, host);

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
        el("h3", { icon: "instructor", text: "" + t("report.per_instructor") }),
        el("div", { class: "mt" }),
      ]);
      res.per_instructor.forEach(([name, v]) => ins.append(el("div", { class: "kv" }, [
        el("span", { class: "k", text: name }), el("span", { class: "v", text: `${v.sessions} ${t("report.sessions").toLowerCase()} · ${v.completed} ✅` })])));
      const carR = el("div", { class: "card" }, [
        el("h3", { icon: "car", text: "" + t("report.per_car") }), el("div", { class: "mt" }),
      ]);
      res.per_car.forEach(([k, v]) => carR.append(el("div", { class: "kv" }, [el("span", { class: "k", text: k }), el("span", { class: "v", text: `${v.sessions}` })])));
      host.append(grid, el("div", { class: "grid-2 mt" }, [ins, carR]));

      // eksport tugmalari
      exportBar.innerHTML = "";
      exportBar.append(el("span", { class: "field-label", text: t("report.export") + ":" }));
      ["csv", "xlsx", "pdf"].forEach((fmt) => {
        exportBar.append(el("button", { class: "btn btn-light btn-sm", text: fmt.toUpperCase(),
          onclick: async () => {
            try {
              // Backend download kaliti bilan to'g'ridan-to'g'ri fayl yuboradi (server.py _dispatch_response)
              // -> API klienti Blob qaytaradi (kontent-tip fayl turi, JSON emas)
              const q2 = new URLSearchParams({ report: "sessions", format: fmt, period: periodSel.value });
              if (fromI.value) q2.set("from", fromI.value);
              if (toI.value) q2.set("to", toI.value);
              const blob = await API.get("admin/export?" + q2.toString());
              if (!(blob instanceof Blob)) throw new Error("err.server_error");
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              const name = "hisobot." + (fmt === "pdf" ? "html" : fmt);
              a.download = name;
              document.body.appendChild(a); a.click();
              setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 400);
            } catch (e) { errToast(e); }
          } }));
      });
    }
    function stat(ic, l, v) { return el("div", { class: "stat-card" }, [el("div", { class: "stat-icon", icon: ic }), el("div", {}, [el("div", { class: "stat-value", text: String(v) }), el("div", { class: "stat-label", text: l })])]); }
    load();
    return wrap;
  }

  /* ============================ AUDIT ============================ */
  async function audit() {
    const res = await API.get("admin/audit");
    const wrap = el("div", {}, [el("h3", { class: "mb", icon: "file", text: "" + t("audit.title") })]);
    if (!res.logs.length) { wrap.append(emptyState("📜", t("auth.no_registration"))); return wrap; }
    const tbl = el("table", { class: "tbl" }, [el("thead", {}, [el("tr", {}, [
      el("th", { text: t("common.date") }), el("th", { text: "Admin" }), el("th", { text: t("common.actions") }),
      el("th", { text: "Entity" }), el("th", { text: t("common.notes") }),
    ])]), el("tbody", {}, res.logs.map((l) => el("tr", {}, [
      el("td", { text: fmtDateTime(l.created_at) }),
      el("td", { text: String(l.admin_id || "—") }),
      el("td", {}, [badge("blue", l.action)]),
      el("td", { text: `${l.entity_type || ""} #${l.entity_id || ""}` }),
      el("td", { text: JSON.stringify(JSON.parse(l.details || "{}")), class: "muted" }),
    ])))]);
    wrap.append(tbl);
    return wrap;
  }

  /* ============================ BACKUP ============================ */
  async function backup() {
    const wrap = el("div", {}, []);
    const listB = el("button", { class: "btn btn-primary", icon: "save", text: "" + t("backup.create"), onclick: async () => {
      try { const r = await API.post("admin/backup"); toast(t("backup.created") + ": " + r.file); loadList(); }
      catch (e) { errToast(e); }
    } });
    const host = el("div", { class: "mt" });
    wrap.append(listB, host);
    async function loadList() {
      host.innerHTML = ""; host.append(spinner());
      const r = await API.get("admin/backup");
      host.innerHTML = "";
      if (!r.backups.length) { host.append(emptyState("💾", t("backup.title"))); return; }
      const list = el("div", { class: "grid-2" });
      r.backups.forEach((b) => list.append(el("div", { class: "card row between" }, [
        el("div", {}, [el("div", { class: "cell-strong", text: b.name }), el("div", { class: "muted sm", text: (b.size / 1024).toFixed(1) + " KB" })]),
      ])));
      host.append(list);
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
        [t("common.phone"), u.phone || "—"],
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
        el("h3", { class: "card-title", icon: "search", text: "📈 " + t("nav.analytics") }),
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
          el("h3", { class: "card-title", text: "📊 " + t("analytics.daily_chart") }),
          el("span", { class: "muted sm", text: t("analytics.cancel_mark") }),
        ]),
        el("div", { class: "bar-chart" }, days.map((b) => {
          const h = Math.max(4, Math.round((b.sessions / maxC) * 120));
          return el("div", {
            class: "chart-col" + (b.cancelled ? " chart-cancel" : ""),
            title: b.day + ": " + b.sessions + " / ❌ " + b.cancelled,
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
        el("h3", { class: "card-title", text: "📈 " + t("analytics.monthly_chart") }),
        el("div", { class: "bar-chart" }, mD.map((b) => {
          const h = Math.max(4, Math.round((b.sessions / maxM) * 120));
          return el("div", {
            class: "chart-col" + (b.cancelled ? " chart-cancel" : ""),
            title: b.month + ": " + b.sessions + " / ❌ " + b.cancelled,
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
        el("h3", { class: "card-title", text: "🏆 " + t("analytics.top_instructors") }),
      ]);
      if (!top.length) {
        topCard.append(emptyState("🏆", t("analytics.no_data")));
      } else {
        const list = el("div", { class: "mt" });
        top.forEach((it, i) => list.append(el("div", { class: "row between pv" }, [
          el("div", { class: "row" }, [
            el("span", { class: "rank" + (i < 3 ? " rank-top" : ""), text: String(i + 1) }),
            el("span", { class: "cell-strong", text: it.name }),
          ]),
          el("div", { class: "muted sm", text: "" + it.sessions + " " + t("week.sessions").toLowerCase() + (it.cancelled ? " · ❌ " + it.cancelled : "") }),
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

  return { dashboard, base, users, students, instructors, cars, lessons, calendar, requests, reports, analytics, audit, backup, settings, profile, notifications: () => Shared.notificationsPage() };
})();