/* INSTRUKTOR kabineti: Bosh sahifa, Bugun, Jadval, Talabalarim, Avtomobilim, Xabarlar, Profil */
window.InstructorViews = (function () {
  const { t, fmtDate } = I18N;
  const UI = window.UI;
  const { el, toast, errToast, badge, statusText, avatar, carPhoto, emptyState, spinner, field, input, mapLink, callLink, timeline, checklist, notifMini, modal, select } = UI;

  async function dashboard() {
    const res = await API.get("instructor/home");
    const car = res.car || (App.me && App.me.car) || null;
    const wrap = el("div", {}, []);

    // Tabrik va avtomobil kartasi
    wrap.append(el("div", { class: "card mb" }, [
      el("div", { class: "row between" }, [
        el("div", {}, [
          el("div", { class: "cell-strong", text: "👋 " + (App.me.user.first_name || "") + " " + (App.me.user.last_name || "") }),
          el("div", { class: "muted sm", text: t("auth.role_instructor") }),
        ]),
        avatar(App.me.user, 44),
      ]),
    ]));
    if (car) {
      wrap.append(el("div", { class: "car-big mb" }, [
        el("div", { class: "car-icon", text: "🚗" }),
        el("div", { class: "f1" }, [
          el("div", { class: "car-model", text: `${car.brand} ${car.model}` }),
          el("div", { class: "car-plate", text: car.plate_number }),
        ]),
        el("div", {}, [badge(car.status, statusText(car.status)), el("div", { class: "muted sm mt", icon: "users", text: "" + t("car.capacity") + ": " + car.practice_capacity })]),
      ]));
    } else {
      wrap.append(el("div", { class: "card mb" }, [emptyState("🚗", t("instructor.no_car"))]));
    }

    // Haftalik statistika (umumiy holat)
    const weekly = el("div", { class: "grid-stats grid-stats-compact mb" });
    [
      ["calendar", t("week.sessions"), res.weekly.sessions],
      ["check_circle", t("week.done"), res.weekly.done],
      ["clock", t("week.hours"), res.weekly.hours],
      ["student", t("week.students"), res.weekly.students],
      ["calendar", t("week.today"), res.weekly.today],
    ].forEach(([icon, label, val]) => weekly.append(el("div", { class: "stat-card" }, [
      el("div", { class: "stat-icon", icon }),
      el("div", {}, [el("div", { class: "stat-value", text: String(val) }), el("div", { class: "stat-label", text: label })]),
    ])));
    wrap.append(weekly);

    // Umumiy progress + tezkor havolalar
    const progCard = el("div", { class: "card" }, [
      el("h3", { class: "card-title", text: "📈 " + t("home.overall_progress") }),
      el("div", { class: "prog-line" }, [el("span", { text: t("progress.total") }), el("strong", { text: String(res.overall.sessions) })]),
      el("div", { class: "prog-line" }, [el("span", { text: t("progress.done") }), el("strong", { text: String(res.overall.done) })]),
      el("div", { class: "prog-line" }, [el("span", { text: t("progress.hours") }), el("strong", { text: String(res.overall.hours) })]),
    ]);
    wrap.append(progCard);

    // So'nggi bildirishnomalar
    const notifRes = await API.get("me/notifications");
    const notifCard = el("div", { class: "card mt" }, [
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
    wrap.append(notifCard);
    return wrap;
  }

  function sessionCard(s) {
    return el("div", { class: "session-card " + s.status, onclick: () => Shared.openSession(s.id, "instructor") }, [
      el("div", { class: "row between" }, [
        el("div", { class: "session-time", text: `${s.start_time}–${s.end_time}` }),
        badge(s.status, statusText(s.status)),
      ]),
      el("div", { class: "session-meta" }, [
        el("div", { icon: "car", text: "" + (s.car_name_snapshot || "—") + " · " + s.car_plate_snapshot }),
        el("div", { class: "session-count", icon: "users", text: "" + (s.student_count || 0) + "/" + s.capacity_snapshot }),
      ]),
    ]);
  }

  async function schedule() {
    const dateI = input({ type: "date", value: Shared.todayISO() });
    const host = el("div", { class: "mt" });
    const wrap = el("div", {}, [el("div", { class: "row mb" }, [field("📅 " + t("lesson.date"), dateI, { class: "f1" })])]);
    wrap.append(host);
    async function load() {
      host.innerHTML = ""; host.append(spinner());
      const res = await API.get("instructor/schedule?date=" + dateI.value);
      host.innerHTML = "";
      const list = el("div", { class: "grid-2" });
      res.sessions.forEach((s) => list.append(sessionCard(s)));
      if (!res.sessions.length) list.append(emptyState("🗓", t("lesson.empty_today")));
      host.append(list);
    }
    dateI.addEventListener("change", load);
    load();
    return wrap;
  }

  async function students() {
    const res = await API.get("instructor/students");
    const wrap = el("div", {}, [el("h3", { class: "mb", icon: "graduation", text: " 👨" + t("nav.my_students") })]);
    if (!res.students.length) { wrap.append(emptyState("👨‍🎓", t("instructor.students_empty"))); return wrap; }
    const grid = el("div", { class: "grid-3" });
    res.students.forEach((s) => grid.append(el("div", { class: "card" }, [
      el("div", { class: "user-cell mb" }, [avatar(s, 42), el("div", {}, [
        el("div", { class: "cell-strong", text: s.first_name + " " + s.last_name }),
        el("div", { class: "muted sm", text: (s.group_name || "") + " · " + (s.license_category || "") }),
      ])]),
      el("div", { class: "row" }, [
        callLink(s.phone),
        el("button", { class: "btn btn-light btn-sm", icon: "message", text: "" + t("lesson.message"),
          onclick: () => Shared.openMessage(s.user_id, s.first_name + " " + s.last_name) }),
      ]),
    ])));
    wrap.append(grid);
    return wrap;
  }

  async function car() {
    const res = await API.get("instructor/car");
    const c = res.car;
    const wrap = el("div", {}, [el("div", { class: "row between mb" }, [
      el("h3", { icon: "car", text: "" + t("nav.my_car") }),
      res.car ? el("button", { class: "btn btn-primary", icon: "edit", text: "" + t("common.edit"),
        onclick: () => carEditModal(c) }) : null,
    ])]);
    if (!c) { wrap.append(el("div", { class: "card" }, [emptyState("🚗", t("instructor.no_car"))])); return wrap; }
    wrap.append(el("div", { class: "card" }, [
      el("div", { class: "car-big mb" }, [
        carPhoto(res.photos && res.photos[0] ? res.photos[0].path : "", 92),
        el("div", {}, [
          el("div", { class: "car-model", text: `${c.brand} ${c.model}` }),
          el("div", { class: "car-plate", text: c.plate_number }),
        ]),
      ]),
      badge(c.status, statusText(c.status)),
      el("p", { class: "field-hint mt", text: t("instructor.car_note") }),
    ]));
    if (res.photos && res.photos.length) {
      wrap.append(el("div", { class: "card mt" }, [
        el("h4", { class: "mb", text: "📷 " + t("car.photos") }),
        el("div", { class: "car-photos-grid" }, res.photos.map((p) => carPhoto(p.path, 130))),
      ]));
    }
    const kv = el("div", { class: "card mt" }, []);
    [
      [t("car.year"), String(c.year || "—")], [t("car.color"), c.color || "—"],
      [t("car.seats"), String(c.seat_count || "—")], [t("car.capacity"), String(c.practice_capacity)],
      [t("car.inspection"), c.technical_inspection_date || "—"], [t("car.insurance"), c.insurance_expiry || "—"],
    ].forEach(([k, v]) => kv.append(el("div", { class: "kv" }, [el("span", { class: "k", text: k }), el("span", { class: "v", text: v })])));
    wrap.append(kv);
    return wrap;
  }

  /* M6 — instruktor O'Z mashinasini tahrirlaydi (assigned_car_id orqali backend tekshiradi) */
  function carEditModal(c) {
    const f = {
      brand: input({ value: c.brand || "" }),
      model: input({ value: c.model || "" }),
      plate: input({ value: c.plate_number || "", placeholder: "01 A 123 AA" }),
      year: input({ type: "number", value: c.year || 2022 }),
      color: input({ value: c.color || "" }),
      seats: input({ type: "number", value: c.seat_count || 4 }),
      capacity: input({ type: "number", value: c.practice_capacity || 4 }),
      inspection: input({ type: "date", value: c.technical_inspection_date || "" }),
      insurance: input({ type: "date", value: c.insurance_expiry || "" }),
    };
    const notes = el("textarea", { class: "input", text: c.notes || "" });
    const m = modal(t("common.edit") + " — 🚗 " + (c.brand || "") + " " + (c.model || ""), [
      el("div", { class: "grid-2" }, [
        field(t("car.brand"), f.brand), field(t("car.model"), f.model),
        field("🔢 " + t("car.plate"), f.plate), field(t("car.year"), f.year),
        field(t("car.color"), f.color), field(t("car.seats"), f.seats),
        field("👥 " + t("car.capacity"), f.capacity),
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
              practice_capacity: parseInt(f.capacity.value || 4),
              technical_inspection_date: f.inspection.value, insurance_expiry: f.insurance.value, notes: notes.value,
            };
            try {
              await API.put("instructor/car", payload);
              toast(t("misc.saved")); m.close(); App.refreshView();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  async function messages() {
    const res = await API.get("me/messages");
    const wrap = el("div", {}, [el("h3", { class: "mb", icon: "message", text: "" + t("nav.messages") })]);
    if (!res.messages.length) { wrap.append(emptyState("💬", t("instructor.students_empty"))); return wrap; }
    const list = el("div", { class: "card" });
    res.messages.forEach((msg) => {
      list.append(el("div", { class: "kv" }, [
        el("span", { class: "k", text: (msg.first_name || "?") + " " + (msg.last_name || "") + " · " + (msg.created_at || "").slice(0, 16) }),
        el("span", { class: "v", text: msg.text }),
      ]));
    });
    wrap.append(list);
    return wrap;
  }

  async function profile() {
    const u = App.me.user;
    const inst = App.me.instructor || {};
    return Shared.renderProfile({
      roleLabel: t("auth.role_instructor"),
      kvs: [
        [t("common.phone"), u.phone || "—"],
        [t("common.login"), u.login],
        [t("instructor.schedule"), `${inst.work_start || "—"}–${inst.work_end || "—"}`],
      ],
    });
  }

  function settings() {
    return Shared.settingsPage({ isAdmin: false });
  }

  return { dashboard, schedule, students, car, messages, profile, settings, notifications: () => Shared.notificationsPage() };
})();