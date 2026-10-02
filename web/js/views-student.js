/* TALABA kabineti: Bosh sahifa, Amaliy mashg'ulotlarim, Tarix, So'rovlar, Profil

   BAND 2  — Bosh sahifada 3 ta karta: [Jami darslar] [Bajarilgan] [Qolgan]
             + pastroqda KATTА "Umumiy progress" bloki. Barcha raqamlar DB'dan.
   BAND 4  — "Mening jadvalim" talaba interfeysidan, sidebar va routing'dan
             BUTUNLAY olib tashlandi. Qolgan nom: "Amaliy mashg'ulotlarim".
   BAND 10 — Bosh sahifadagi "So'nggi bildirishnomalar" bloki olib tashlandi.
   BAND 13 — Kelajakdagi va o'tilgan mashg'ulotlar aniq ajratiladi:
             1 kun o'tgan dars "kelayotgan" ro'yxatidan chiqadi, lekin
             "Mashg'ulotlar tarixi"da saqlanadi va bajarilganlar soniga kiradi.
   BAND 14 — Holatlar: KUTILMOQDA / TASDIQLANGAN / JARAYONDA / BAJARILGAN /
             BEKOR QILINGAN / O'TIB KETGAN (yakunlanmagan). "Kutilmoqda" faqat
             kelmagan mashg'ulotlar uchun.
*/
window.StudentViews = (function () {
  const { t, fmtDate } = I18N;
  const UI = window.UI;
  const { el, toast, errToast, badge, statusText, avatar, emptyState, spinner, field, input, mapLink } = UI;

  /* BAND 14: biznes holatidan badge. `scheduled` o'zi yetarli emas —
     kelmagan, tasdiqlangan va o'tib ketgan holatlar boshqacha ko'rinadi. */
  function statusBadge(s) {
    const disp = s._display_status || s.status;
    const label = t("st." + disp) || t("common.status");
    return badge(disp, label);
  }

  async function dashboard() {
    const home = await API.get("student/home");
    const st = App.me.student || {};
    const wrap = el("div", {}, []);

    /* Profil sarlavhasi */
    wrap.append(el("div", { class: "card mb" }, [
      el("div", { class: "row between" }, [
        el("div", {}, [
          el("div", { class: "cell-strong", text: (App.me.user.first_name || "") + " " + (App.me.user.last_name || "") }),
          el("div", { class: "muted sm", text: (st.group_name || "") + " \u00b7 " + (st.license_category || "") }),
        ]),
        avatar(App.me.user, 44),
      ]),
    ]));

    /* ------------------------------------------------------------------ BAND 2
       Uchta karta: [Jami darslar] [Bajarilgan darslar] [Qolgan darslar].
       Barcha qiymatlar `student/home` -> progress (DB'dan). Hech qanday
       hardcoded raqam yo'q. */
    const pr = home.progress || { target: 0, done: 0, remaining: 0, pct: 0, mode: "group" };
    const target = Number(pr.target) || 0;
    const done = Number(pr.done) || 0;
    const remaining = Number(pr.remaining != null ? pr.remaining : Math.max(0, target - done));
    const pct = target ? Math.max(0, Math.min(100, Math.round(done * 100 / target))) : 0;
    const isGroup = pr.mode !== "individual";

    /* Yordamchi: bitta karta (ikona + qiymat + nom + izoh). */
    const statCard = (icon, label, value, sub, accent) => el("div", { class: "stat-card stat-card-equal" }, [
      el("div", { class: "stat-icon" + (accent ? " stat-icon-" + accent : "") , icon }),
      el("div", { class: "stat-body" }, [
        el("div", { class: "stat-value", text: String(value) }),
        el("div", { class: "stat-label", text: label }),
        sub ? el("div", { class: "stat-sub", text: sub }) : el("div", { class: "stat-sub" }),
      ]),
    ]);

    wrap.append(el("div", { class: "grid-3 mb stat-row stat-row-3" }, [
      /* 1) JAMI darslar — maqsad (bitta talaba yoki barcha talabalar uchun) */
      statCard("calendar", t("week.total_lessons"), target,
               isGroup ? t("users.mode_group") : t("users.mode_individual"), "navy"),
      /* 2) BAJARILGAN darslar — faqat `status='completed'` (o'tib ketgan yetmaydi!) */
      statCard("check_circle", t("week.done_lessons"), done,
               t("week.done_share", { n: pct }), "gold"),
      /* 3) QOLGAN darslar — `remaining` (manfiy bo'lmaydi) */
      statCard("hourglass", t("week.remaining_lessons"), remaining,
               t("week.remaining_note"), "amber"),
    ]));

    /* ------------------------------------------------- BAND 2: KATTA progress */
    const ov = home.overall || { sessions: 0, done: 0, hours: 0 };
    const counts = home.counts || {};
    const progCard = el("div", { class: "card mb progress-big" }, [
      el("h3", { class: "card-title", text: "\u{1f4c8} " + t("home.overall_progress") }),
      el("div", { class: "progress-big-bar" }, [
        el("div", { class: "progress-fill", style: "width:" + pct + "%" }),
        el("span", { class: "progress-big-label", text: pct + "%" }),
      ]),
      el("div", { class: "progress-big-meta" }, [
        el("div", {}, [
          el("div", { class: "muted sm", text: t("progress.done") }),
          el("div", { class: "cell-strong", text: String(done) }),
        ]),
        el("div", {}, [
          el("div", { class: "muted sm", text: t("progress.total") }),
          el("div", { class: "cell-strong", text: String(target) }),
        ]),
        el("div", {}, [
          el("div", { class: "muted sm", text: t("progress.remaining") }),
          el("div", { class: "cell-strong", text: String(remaining) }),
        ]),
        el("div", {}, [
          el("div", { class: "muted sm", text: t("progress.hours") }),
          el("div", { class: "cell-strong", text: String(Number(ov.hours) || 0) }),
        ]),
      ]),
      /* BAND 13/14: kelmagan / o'tib ketgan mashg'ulotlar aniq ko'rsatiladi. */
      el("div", { class: "progress-big-foot" }, [
        el("span", { class: "chip chip-cyan", text: t("home.upcoming_count", { n: Number(counts.upcoming) || 0 }) }),
        el("span", { class: "chip chip-gray", text: t("home.sessions_count", { n: Number(counts.total) || 0 }) }),
        Number(counts.overdue) ? el("span", { class: "chip chip-orange", text: t("home.overdue_count", { n: Number(counts.overdue) || 0 }) }) : null,
      ]),
    ]);
    wrap.append(progCard);

    /* --------------------------------------------------------- Keyingi mashg'ulot */
    const nextCard = el("div", { class: "card mb" }, [el("h3", { class: "card-title", text: "\u23ed\ufe0f " + t("lesson.next") }), el("div", { class: "mt" })]);
    const n = home.next;
    if (!n) {
      nextCard.append(emptyState("\u{1f4c5}", t("lesson.no_upcoming")));
      nextCard.append(el("button", { class: "btn btn-cyan mt", text: "\u{1f4e8} " + t("lesson.request_btn"), onclick: () => requestModal() }));
    } else {
      nextCard.append(sessionCard(n));
      nextCard.append(el("button", { class: "btn btn-primary mt", icon: "search", text: "" + t("lesson.view_calendar"), onclick: () => Shared.openSession(n.id, "student") }));
    }
    wrap.append(nextCard);

    /* BAND 10: "So'nggi bildirishnomalar" bloki BU YERDAN BUTUNLAY
       olib tashlangan. Bildirishnomalar faqat `Bell` menyusi va alohida
       "Bildirishnomalar" sahifasi orqali ko'rinadi. */
    return wrap;
  }

  function sessionCard(s) {
    return el("div", { class: "session-card " + (s._display_status || s.status), dataset: { sid: s.id }, onclick: () => Shared.openSession(s.id, "student") }, [
      el("div", { class: "row between" }, [
        el("div", { class: "session-time", text: `${fmtDate(s.date)} \u00b7 ${s.start_time}\u2013${s.end_time}` }),
        statusBadge(s),
      ]),
      el("div", { class: "session-meta" }, [
        el("div", { icon: "instructor", text: "" + (s.instructor_name || "") }),
        el("div", { icon: "car", text: "" + (s.car_name_snapshot || "") + " \u00b7 " + s.car_plate_snapshot }),
        el("div", { icon: "users", text: "" + (s.student_count || 0) + "/" + s.capacity_snapshot }),
        // BAND 1: olish manzili matn sifatida (xarita havolaasi vaqtinchalik
        // o'chirilgan — API kalitlari to'liq sozlangandan keyin qaytariladi).
        el("div", { icon: "map" }, [
          el("span", { text: "\u{1f4cd} " + (s.pickup_address || "\u2014") }),
        ]),
      ]),
    ]);
  }

  /* ------------------------------------------------------------------ BAND 4
     "Mening jadvalim" -> endi FAQAT "Amaliy mashg'ulotlarim" (KELMAGAN darslar).
     Backend `?upcoming=1` allaqachon kelmaganlarni qaytaradi; BAND 13 bo'yicha
     o'tib ketgan darslar bu ro'yxatga KIRMAYDI (ular "Tarix"da). */
  async function lessons() {
    const res = await API.get("student/sessions?upcoming=1");
    const wrap = el("div", {}, [el("h3", { class: "mb", icon: "car", text: "" + t("nav.my_lessons") })]);
    if (!res.sessions.length) {
      wrap.append(emptyState("\u{1f697}", t("lesson.no_upcoming")));
      wrap.append(el("button", { class: "btn btn-cyan mt", text: "\u{1f4e8} " + t("lesson.request_btn"), onclick: () => requestModal() }));
      return wrap;
    }
    const list = el("div", { class: "grid-2" });
    res.sessions.forEach((s) => list.append(sessionCard(s)));
    wrap.append(list);
    return wrap;
  }

  /* ------------------------------------------------------------------ BAND 13/14
     "Mashg'ulotlar tarixi": o'tilgan darslar. O'tib ketgan lekin yakunlanmagan
     darslar ham shu yerda, `OVERDUE` badge bilan — ular "Bajarilgan" deb
     hisoblanMAYDI. */
  async function history() {
    const res = await API.get("student/sessions?upcoming=0");
    const overdue = res.sessions.filter((s) => s._display_status === "overdue").length;
    const wrap = el("div", {}, [el("div", { class: "row between mb" }, [
      el("div", { class: "row gap-sm wrap" }, [
        el("h3", { icon: "copy", text: "" + t("nav.history") }),
        overdue ? el("span", { class: "chip chip-orange", text: t("home.overdue_count", { n: overdue }) }) : null,
      ]),
      res.sessions.length ? el("button", { class: "btn btn-light btn-sm", icon: "trash", text: "" + t("history.clear_all"),
        onclick: () => UI.confirmDialog(t("history.clear_all_confirm"), async () => {
          try { await API.post("student/history/clear"); toast(t("misc.saved")); App.refreshView(); }
          catch (e) { errToast(e); }
        }) }) : null,
    ])]);
    if (!res.sessions.length) { wrap.append(emptyState("\u{1f4cb}", t("lesson.history_empty"))); return wrap; }
    const tbl = el("table", { class: "tbl" }, [el("thead", {}, [el("tr", {}, [
      el("th", { text: t("lesson.date") }), el("th", { text: t("lesson.time") }),
      el("th", { text: t("lesson.instructor") }), el("th", { text: t("lesson.car") }),
      el("th", { text: t("lesson.attendance") }), el("th", { text: t("common.status") }),
      el("th", {}),
    ])]), el("tbody", {}, res.sessions.map((s) => el("tr", {
      class: "row-click", onclick: () => Shared.openSession(s.id, "student"),
    }, [
      el("td", { text: fmtDate(s.date) }), el("td", { text: s.start_time + "\u2013" + s.end_time }),
      el("td", { text: s.instructor_name }), el("td", { text: (s.car_name_snapshot || "") + " " + (s.car_plate_snapshot || "") }),
      el("td", {}, [attBadge(s.attendance_status)]),
      el("td", {}, [statusBadge(s)]),
      el("td", {}, [el("button", { class: "btn-ghost btn-sm", title: t("history.delete"), text: "\u2715",
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

  /* MODUL 5B: uchta bo'lim — Faol / Eskirgan / Tarix (mashg'ulot sanasi +
     1 kun, faqat hali tasdiqlanmagan so'rovlarda). */
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
    const tabsHost = el("div", {});
    const listHost = el("div", {});
    const wrap = el("div", {}, [
      el("div", { class: "row between mb" }, [el("h3", { text: "\u{1f4e8} " + t("nav.requests") }),
        el("div", { class: "row gap-sm" }, [
          el("button", { class: "btn btn-light btn-sm", icon: "trash", text: "" + t("requests.clear_all"),
            onclick: () => UI.confirmDialog(t("requests.clear_all_confirm"), async () => {
              try { await API.post("student/requests/clear"); toast(t("misc.saved")); App.refreshView(); }
              catch (e) { errToast(e); }
            }) }),
          el("button", { class: "btn btn-cyan btn-sm", icon: "plus", text: "" + t("lesson.request_btn"), onclick: () => requestModal() }),
        ])]),
      el("p", { class: "field-hint mb", text: t("req.auto_hidden") }),
      tabsHost, listHost,
    ]);

    async function load(m) {
      listHost.innerHTML = ""; listHost.append(UI.spinner());
      const res = await API.get("student/requests?filter=" + encodeURIComponent(m));
      tabsHost.innerHTML = "";
      tabsHost.append(requestTabs(m, res.counts || {}, load));
      listHost.innerHTML = "";
      const items = res.requests || [];
      if (!items.length) { listHost.append(emptyState("\u{1f4e8}", t("notif.empty"))); return; }
      const list = el("div", { class: "grid-2" });
      items.forEach((r) => list.append(el("div", { class: "card" }, [
        el("div", { class: "row between" }, [
          el("div", { class: "row gap-sm" }, [el("strong", { text: fmtDate(r.preferred_date || "\u2014") + " " + (r.preferred_start_time || "") }),
            r.is_expired ? badge("late", t("req.expired")) : null,
            badge(r.status, statusText(r.status))]),
          el("button", { class: "btn-ghost btn-sm", title: t("requests.delete"), text: "\u2715", onclick: () => {
            API.post("student/requests/delete", { request_id: r.id })
              .then(() => { toast(t("misc.saved")); App.refreshView(); })
              .catch((err) => errToast(err));
          } }),
        ]),
        el("div", { class: "muted sm mt", icon: "message", text: "" + (r.message || "\u2014") }),
        r.is_expired ? el("div", { class: "field-hint", text: t("req.expired_hint") }) : null,
      ])));
      listHost.append(list);
    }

    await load("active");
    return wrap;
  }

  function requestModal() {
    const dateI = input({ type: "date" });
    const startI = input({ type: "time", value: "15:00" });
    const endI = input({ type: "time", value: "16:00" });
    const msgI = el("textarea", { class: "input" });
    const m = UI.modal(t("lesson.request_form"), [
      el("p", { class: "field-hint", text: t("student.with_car") }),
      field("\u{1f4c5} " + t("lesson.date"), dateI),
      el("div", { class: "row" }, [field("\u{1f552} " + t("lesson.start"), startI, { class: "f1" }), field("\u{1f552} " + t("lesson.end"), endI, { class: "f1" })]),
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

  /* ------------------------------------------------------------------ BAND 15/16
     "Profilim" — ko'rsatish + "Tahrirlash" tugmasi.
       * Tahrirlanadigan: tug'ilgan sana, telefon, login, guruh, haydovchilik toifasi.
       * PAROL bu yerda KO'RSATILMAYDI va tahrirlanmaydi (alohida xavfsiz oqim:
         "Parolni o'zgartirish" — `POST /api/auth/change-password`).
       * "Ro'yxatga olingan sana" talabaga KO'RSATILMAYDI (backend ham yashiradi).
  */
  async function profile() {
    const u = App.me.user;
    const st = App.me.student || {};
    return Shared.renderProfile({
      editable: true,          /* -> "Tahrirlash" tugmasi chiqadi */
      kvs: [
        [t("student.birth_date"), u.birth_date ? fmtDate(u.birth_date) : "\u2014"],
        [t("common.phone"), u.phone || "\u2014"],
        [t("common.login"), u.login],
        [t("student.group"), st.group_name || "\u2014"],
        [t("student.category"), st.license_category || "\u2014"],
        /* BAND 16: `enrolled_at` talabaga umuman qaytarilmaydi (faqat admin). */
      ],
    });
  }

  function settings() {
    return Shared.settingsPage({ isAdmin: false });
  }

  return {
    dashboard, lessons, history, requests, profile, settings,
    notifications: () => Shared.notificationsPage(),
    statusBadge,
  };
})();