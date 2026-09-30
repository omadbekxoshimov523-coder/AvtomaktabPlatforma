/* TALABA kabineti: Bosh sahifa, Mening jadvalim, Amaliy mashg'ulotlarim, Tarix, So'rovlar, Profil */
window.StudentViews = (function () {
  const { t, fmtDate } = I18N;
  const UI = window.UI;
  const { el, toast, errToast, badge, statusText, avatar, emptyState, spinner, field, input, timeline, checklist, notifMini, mapLink } = UI;

  async function dashboard() {
    const [home, notifRes] = await Promise.all([API.get("student/home"), API.get("me/notifications")]);
    const st = App.me.student || {};
    const wrap = el("div", {}, []);

    // Profil sarlavhasi
    wrap.append(el("div", { class: "card mb" }, [
      el("div", { class: "row between" }, [
        el("div", {}, [
          el("div", { class: "cell-strong", text: (App.me.user.first_name || "") + " " + (App.me.user.last_name || "") }),
          el("div", { class: "muted sm", text: (st.group_name || "") + " · " + (st.license_category || "") }),
        ]),
        avatar(App.me.user, 44),
      ]),
    ]));

    /* MODUL 5: "Haftadagi darslar" -> "Jami darslar", "Amaliy soatlar" kartasi
       OLIB TASHLANDI. Endi faqat 2 ta karta bor — ikkalasi ham teng kenglik
       va teng balandlikda (grid-2 + stat-card-equal), har birida progress
       bar va foiz. Maqsad: individual (talaba) yoki ommaviy (platforma). */
    const pr = home.progress || { target: 0, done: 0, remaining: 0, pct: 0, mode: "group" };
    const ov = home.overall;
    const isGroup = pr.mode !== "individual";

    const statCard = (icon, label, value, sub, barPct, accent) => el("div", { class: "stat-card stat-card-equal" }, [
      el("div", { class: "stat-icon" + (accent ? " stat-icon-" + accent : ""), icon }),
      el("div", { class: "stat-body" }, [
        el("div", { class: "stat-value", text: String(value) }),
        el("div", { class: "stat-label", text: label }),
        sub ? el("div", { class: "stat-sub", text: sub }) : el("div", { class: "stat-sub" }),
        el("div", { class: "progress-bar mt" }, [
          el("div", {
            class: "progress-fill" + (accent ? " fill-" + accent : ""),
            style: "width:" + Math.max(0, Math.min(100, barPct)) + "%",
          }),
        ]),
        el("div", { class: "stat-pct", text: barPct + "%" }),
      ]),
    ]);

    wrap.append(el("div", { class: "grid-2 mb stat-row" }, [
      // 1-karta: Jami darslar (maqsad)
      statCard(
        "calendar",
        t("week.total_lessons"),
        pr.target,
        isGroup ? t("users.mode_group") : t("users.mode_individual"),
        pr.pct,
        "navy"
      ),
      // 2-karta: Bajarilgan darslar
      statCard(
        "check_circle",
        t("week.done_lessons"),
        pr.done,
        t("week.remaining_lessons", { n: pr.remaining }),
        pr.pct,
        "gold"
      ),
    ]));

    // Umumiy progress + muvaffaqiyat foizi
    const progCard = el("div", { class: "card mb" }, [
      el("h3", { class: "card-title", text: "📈 " + t("home.overall_progress") }),
      el("div", { class: "prog-line" }, [el("span", { text: t("progress.total") }), el("strong", { text: String(ov.sessions) })]),
      el("div", { class: "prog-line" }, [el("span", { text: t("progress.done") }), el("strong", { text: String(ov.done) })]),
      el("div", { class: "prog-line" }, [el("span", { text: t("progress.remaining") }), el("strong", { text: String(ov.sessions - ov.done) })]),
      el("div", { class: "prog-line" }, [el("span", { text: t("progress.hours") }), el("strong", { text: String(ov.hours) })]),
      el("div", { class: "progress-bar mt" }, [el("div", { class: "progress-fill", style: "width:" + pr.pct + "%" })]),
      el("div", { class: "muted sm mt", text: t("stat.success_label") + ": " + pr.pct + "%" }),
    ]);
    wrap.append(progCard);

    // Keyingi mashg'ulot
    const nextCard = el("div", { class: "card" }, [el("h3", { class: "card-title", text: "⏭️ " + t("lesson.next") }), el("div", { class: "mt" })]);
    const n = home.next;
    if (!n) {
      nextCard.append(emptyState("📅", t("lesson.no_upcoming")));
      nextCard.append(el("button", { class: "btn btn-cyan mt", text: "📨 " + t("lesson.request_btn"), onclick: () => requestModal() }));
    } else {
      nextCard.append(sessionCard(n));
      nextCard.append(el("button", { class: "btn btn-primary mt", icon: "search", text: "" + t("lesson.view_calendar"), onclick: () => Shared.openSession(n.id, "student") }));
    }
    wrap.append(nextCard);

    // So'nggi bildirishnomalar (M1: tezkor havolalar olib tashlandi)
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
    return el("div", { class: "session-card " + s.status, dataset: { sid: s.id }, onclick: () => Shared.openSession(s.id, "student") }, [
      el("div", { class: "row between" }, [
        el("div", { class: "session-time", text: `${fmtDate(s.date)} · ${s.start_time}–${s.end_time}` }),
        badge(s.status, statusText(s.status)),
      ]),
      el("div", { class: "session-meta" }, [
        el("div", { icon: "instructor", text: "" + (s.instructor_name || "") }),
        el("div", { icon: "car", text: "" + (s.car_name_snapshot || "") + " · " + s.car_plate_snapshot }),
        el("div", { icon: "users", text: "" + (s.student_count || 0) + "/" + s.capacity_snapshot }),
        // MODUL 4: olish manzili + "Xaritada ko'rish" (Yandex Maps) havolasi
        el("div", { icon: "map" }, [
          el("span", { text: "📍 " + (s.pickup_address || "—") }),
          s.pickup_lat && s.pickup_lng
            ? el("span", {}, ["  ", mapLink(s.pickup_lat, s.pickup_lng, t("map.open"))])
            : null,
        ]),
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
      const res = await API.get("student/sessions?upcoming=1");
      host.innerHTML = "";
      const list = el("div", { class: "grid" });
      res.sessions
        .filter((s) => !dateI.value || s.date === dateI.value)
        .forEach((s) => list.append(sessionCard(s)));
      if (!list.children.length) list.append(emptyState("📅", t("lesson.no_upcoming")));
      host.append(list);
    }
    dateI.addEventListener("change", load);
    load();
    return wrap;
  }

  async function lessons() {
    const res = await API.get("student/sessions?upcoming=1");
    const wrap = el("div", {}, [el("h3", { class: "mb", icon: "car", text: "" + t("nav.my_lessons") })]);
    if (!res.sessions.length) { wrap.append(emptyState("🚗", t("lesson.no_upcoming"))); wrap.append(el("button", { class: "btn btn-cyan mt", text: "📨 " + t("lesson.request_btn"), onclick: () => requestModal() })); return wrap; }
    const list = el("div", { class: "grid-2" });
    res.sessions.forEach((s) => list.append(sessionCard(s)));
    wrap.append(list);
    return wrap;
  }

  async function history() {
    const res = await API.get("student/sessions?upcoming=0");
    const wrap = el("div", {}, [el("div", { class: "row between mb" }, [
      el("h3", { icon: "copy", text: "" + t("nav.history") }),
      res.sessions.length ? el("button", { class: "btn btn-light btn-sm", icon: "trash", text: "" + t("history.clear_all"),
        onclick: () => UI.confirmDialog(t("history.clear_all_confirm"), async () => {
          try { await API.post("student/history/clear"); toast(t("misc.saved")); App.refreshView(); }
          catch (e) { errToast(e); }
        }) }) : null,
    ])]);
    if (!res.sessions.length) { wrap.append(emptyState("📋", t("lesson.history_empty"))); return wrap; }
    const tbl = el("table", { class: "tbl" }, [el("thead", {}, [el("tr", {}, [
      el("th", { text: t("lesson.date") }), el("th", { text: t("lesson.time") }),
      el("th", { text: t("lesson.instructor") }), el("th", { text: t("lesson.car") }),
      el("th", { text: t("lesson.attendance") }), el("th", { text: t("common.status") }),
      el("th", {}),
    ])]), el("tbody", {}, res.sessions.map((s) => el("tr", {
      class: "row-click", onclick: () => Shared.openSession(s.id, "student"),
    }, [
      el("td", { text: fmtDate(s.date) }), el("td", { text: s.start_time + "–" + s.end_time }),
      el("td", { text: s.instructor_name }), el("td", { text: s.car_name_snapshot + " " + s.car_plate_snapshot }),
      el("td", {}, [attBadge(s.attendance_status)]),
      el("td", {}, [badge(s.status, statusText(s.status))]),
      el("td", {}, [el("button", { class: "btn-ghost btn-sm", title: t("history.delete"), text: "✕",
        onclick: (e) => {
          e.stopPropagation();
          API.post("student/history/delete", { session_id: s.id })
            .then(() => { toast(t("misc.saved")); App.refreshView(); })
            .catch((err) => errToast(err));
        } })]),
    ])))]);
    wrap.append(tbl);
    return wrap;
  }
  function attBadge(st) {
    const map = { present: ["b-green", t("lesson.present")], late: ["b-orange", t("lesson.late")], absent: ["b-red", t("lesson.absent")], unmarked: ["b-gray", t("lesson.unmarked")] };
    const [cls, tx] = map[st] || map.unmarked;
    return badge(cls, tx);
  }

  async function requests() {
    const res = await API.get("student/requests");
    const wrap = el("div", {}, [
      el("div", { class: "row between mb" }, [el("h3", { text: "📨 " + t("nav.requests") }),
        el("div", { class: "row gap-sm" }, [
          res.requests.length ? el("button", { class: "btn btn-light btn-sm", icon: "trash", text: "" + t("requests.clear_all"),
            onclick: () => UI.confirmDialog(t("requests.clear_all_confirm"), async () => {
              try { await API.post("student/requests/clear"); toast(t("misc.saved")); App.refreshView(); }
              catch (e) { errToast(e); }
            }) }) : null,
          el("button", { class: "btn btn-cyan btn-sm", icon: "plus", text: "" + t("lesson.request_btn"), onclick: () => requestModal() }),
        ])]),
    ]);
    const list = el("div", { class: "grid-2" });
    res.requests.forEach((r) => list.append(el("div", { class: "card" }, [
      el("div", { class: "row between" }, [
        el("div", { class: "row gap-sm" }, [el("strong", { text: fmtDate(r.preferred_date || "—") + " " + (r.preferred_start_time || "") }), badge(r.status, statusText(r.status))]),
        el("button", { class: "btn-ghost btn-sm", title: t("requests.delete"), text: "✕", onclick: () => {
          API.post("student/requests/delete", { request_id: r.id })
            .then(() => { toast(t("misc.saved")); App.refreshView(); })
            .catch((err) => errToast(err));
        } }),
      ]),
      el("div", { class: "muted sm mt", icon: "message", text: "" + (r.message || "—") }),
    ])));
    if (!res.requests.length) list.append(emptyState("📨", t("notif.empty")));
    wrap.append(list);
    return wrap;
  }

  function requestModal() {
    const dateI = input({ type: "date" });
    const startI = input({ type: "time", value: "15:00" });
    const endI = input({ type: "time", value: "16:00" });
    const msgI = el("textarea", { class: "input" });
    const m = UI.modal(t("lesson.request_form"), [
      el("p", { class: "field-hint", text: t("student.with_car") }),
      field("📅 " + t("lesson.date"), dateI),
      el("div", { class: "row" }, [field("🕒 " + t("lesson.start"), startI, { class: "f1" }), field("🕒 " + t("lesson.end"), endI, { class: "f1" })]),
      field(t("common.notes"), msgI),
      el("div", { class: "row end mt" }, [el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: t("common.send") || t("common.save"),
          onclick: async () => {
            try {
              await API.post("student/requests", {
                preferred_date: dateI.value, preferred_start_time: startI.value, preferred_end_time: endI.value, message: msgI.value,
              });
              toast(t("misc.saved")); m.close(); App.refreshView();
            } catch (e) { errToast(e); }
          } })]),
    ]);
  }

  async function profile() {
    const u = App.me.user;
    const st = App.me.student || {};
    return Shared.renderProfile({
      roleLabel: t("auth.role_student"),
      kvs: [
        [t("student.birth_date"), u.birth_date ? fmtDate(u.birth_date) : "—"],
        [t("common.phone"), u.phone || "—"],
        [t("common.login"), u.login],
        [t("student.group"), st.group_name || "—"],
        [t("student.category"), st.license_category || "—"],
        [t("student.enrolled"), st.enrolled_at ? fmtDate(st.enrolled_at) : "—"],
      ],
    });
  }

  function settings() {
    return Shared.settingsPage({ isAdmin: false });
  }

  return { dashboard, schedule, lessons, history, requests, profile, settings, notifications: () => Shared.notificationsPage() };
})();