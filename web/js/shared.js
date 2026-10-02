/* Umumiy komponentlar: session detallari, foydalanuvchi formasi, xabarlar, yordamchilar */
const Shared = (function () {
  const { t, fmtDate, fmtDateTime, errorText, notifLabel, notifText } = I18N;
  const UI = window.UI;
  const { el, modal, toast, errToast, confirmDialog, field, input, select, badge, statusText, callLink, mapLink, avatar, toggleRow } = UI;

  /* ---------- yordamchilar ---------- */
  function weekdayShort(iso) {
    const names = { mon: t("misc.monday"), tue: t("misc.tuesday"), wed: t("misc.wednesday"), thu: t("misc.thursday"), fri: t("misc.friday"), sat: t("misc.saturday"), sun: t("misc.sunday") };
    return names[iso] || iso;
  }
  function roleLabel(role) {
    if (role === "student") return t("auth.role_student");
    if (role === "instructor") return t("auth.role_instructor");
    if (role === "admin") return t("auth.role_admin");
    return t("notif.system");
  }
  function todayISO() { const d = new Date(); return d.toISOString().slice(0, 10); }
  function timeNowHM() { const d = new Date(); return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0"); }

  function ruleText(code) {
    const map = {
      invalid_date: t("err.invalid_date"), invalid_time: t("err.invalid_time"),
      instructor_not_found: t("err.instructor_not_found"), instructor_blocked: t("err.instructor_blocked"),
      instructor_inactive: t("err.instructor_inactive"), not_work_day: t("err.not_work_day"),
      outside_work_hours: t("err.outside_work_hours"), intersects_break: t("err.intersects_break"),
      car_not_assigned: t("err.car_not_assigned"), car_not_found: t("err.car.not_found"),
      car_in_repair: t("err.car_in_repair"), car_in_checkup: t("err.car_in_checkup"),
      car_inactive: t("err.car_inactive"), instructor_busy: t("err.instructor_busy"),
      car_busy: t("err.car_busy"), capacity_full: t("err.capacity_full"),
      student_busy: t("err.student_busy"), student_not_found: t("err.user.not_found"),
      duplicate_student_in_session: t("err.session.duplicate_student"),
      session_too_long: t("err.session_too_long"), time_order: t("err.invalid_time"),
    };
    if (map[code]) return map[code];
    /* BAND 6: parol kuchlilik qoidalari `auth.password_*` kodlari bilan
       keladi — ular uchun umumiy `errorText` ishlatiladi (`err.*` lug'ati). */
    const e = I18N.errorText(code);
    return (e && e !== code) ? e : code;
  }

  function rulesList(errs) {
    const ul = el("ul", { class: "rules-errors" });
    (errs || []).forEach((c) => ul.append(el("li", { icon: "x", text: "" + ruleText(c) })));
    return ul;
  }

  /* ---------- hisob ma'lumotlari (login/parol) ----------
     MODUL 5: parol endi `password_enc` (AES-256-GCM) sifatida ham
     saqlanadi — admin uni 🔑 orqali ko'ra va o'zgartira oladi. Bu yordamchi
     funksiya YARATILGAN paytdagi credential'larni ko'rsatadi (ular bir
     martalik chiqish natijasi). `hint` — ixtiyoriy ogohlantirish. */
  function credBox(login, password, hint) {
    function row(label, value) {
      const inp = el("input", { class: "input", value: value || "", readonly: "" });
      const copyB = el("button", { class: "btn btn-light btn-sm", icon: "copy", text: "" + t("common.copy"),
        onclick: () => { navigator.clipboard.writeText(value || "").then(() => toast(t("misc.saved"))); } });
      return el("div", { class: "row" }, [
        el("div", { class: "f1" }, [el("div", { class: "field-label", text: label }), inp]),
        copyB,
      ]);
    }
    const kids = [
      el("div", { class: "field-label", icon: "key", text: "" + t("student.credentials") }),
      row(t("auth.login"), login), row(t("auth.password"), password),
    ];
    if (hint) kids.push(el("p", { class: "cred-warn", icon: "warn", text: hint }));
    return el("div", { class: "cred-box" }, kids);
  }

  /* ---------- XABAR YUBORISH ---------- */
  function openMessage(userId, userName) {
    const ta = el("textarea", { class: "input", placeholder: t("instructor.send_msg") + "..." });
    const m = modal(t("lesson.message") + " \u2014 " + userName, [
      ta,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", icon: "message", text: "" + t("instructor.send_msg"),
          onclick: async () => {
            const text = ta.value.trim();
            if (!text) return toast(t("err.msg.empty"), "error");
            try {
              await API.post("me/messages", { to_user_id: userId, text });
              toast(t("misc.saved")); m.close();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* ---------- M3: bildirishnoma -> xabarlar tarixi (dialog + javob) ---------- */
  async function openThread(userId, userName) {
    let hist = { messages: [] };
    try { hist = await API.get("me/messages?with=" + userId); } catch (e) { /* tarix bo'lmasa ham javob yozish mumkin */ }
    const ta = el("textarea", { class: "input", placeholder: t("instructor.send_msg") + "..." });
    const conv = el("div", { class: "conv-list" });
    (hist.messages || []).slice().reverse().forEach((msg) => {
      const mine = msg.from_user_id === (App.me.user.id);
      conv.append(el("div", { class: "conv-bubble " + (mine ? "mine" : "theirs") }, [
        el("div", { class: "conv-bubble-text", text: msg.text }),
        el("div", { class: "conv-bubble-time", text: fmtDateTime(msg.created_at) }),
      ]));
    });
    if (!(hist.messages || []).length) conv.append(el("div", { class: "muted sm", text: t("messages.empty") }));
    const m = modal(t("lesson.message") + " \u2014 " + userName, [
      conv,
      ta,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", icon: "message", text: "" + t("instructor.send_msg"),
          onclick: async () => {
            const text = ta.value.trim();
            if (!text) return toast(t("err.msg.empty"), "error");
            try {
              await API.post("me/messages", { to_user_id: userId, text });
              toast(t("misc.saved")); m.close();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ], { wide: true });
  }

  /* ---------- M3: bildirishnoma -> so'rov detal ---------- */
  function senderFullName(n) {
    return [n.sender_first_name, n.sender_last_name].filter(Boolean).join(" ") || t("notif.unknown");
  }

  async function openRequest(requestId, role) {
    /* MODUL 5A: so'rov ID bo'yicha OCHILADI (ro'yxatdan qidirib topish emas).
       Aks holda eski so'rov (300+ yozuv ichida qolib ketgan, yoki "Eskirgan"/
       "Tarix" bo'limiga o'tgan) umuman topilmaydi va hech narsa ochilmaydi. */
    let req = null;
    try {
      const url = role === "admin"
        ? "admin/requests/" + encodeURIComponent(requestId)
        : "student/requests/" + encodeURIComponent(requestId);
      const res = await API.get(url);
      req = res.request || null;
    } catch (e) { return errToast(e); }
    if (!req) return toast(t("err.request.not_found"), "error");
    const m = modal("\u{1f4e8} " + t("nav.requests"), [], { wide: true });
    const body = [];
    if (role === "admin") {
      body.push(el("div", { class: "user-cell mb" }, [
        avatar({ first_name: req.first_name || "?", last_name: req.last_name || "", profile_image: req.profile_image || "" }, 38),
        el("div", {}, [
          el("strong", { text: `${req.first_name} ${req.last_name}` }),
          el("div", { class: "muted sm", text: req.group_name || req.phone || "" }),
        ]),
      ]));
    }
    body.push(el("div", { class: "row between mb" }, [
      el("div", {}, [
        el("div", { class: "muted sm", text: "" + t("req.preferred") }),
        el("strong", { text: (req.preferred_date ? fmtDate(req.preferred_date) : "\u2014")
          + (req.preferred_start_time ? " " + req.preferred_start_time + "\u2013" + (req.preferred_end_time || "") : "") }),
      ]),
      badge(req.status, statusText(req.status)),
    ]));
    body.push(el("div", { class: "card" }, [
      el("div", { class: "muted", icon: "message", text: "" + (req.message || "\u2014") }),
    ]));
    /* MODUL 5B: eskirgan so'rovda holat aniq ko'rsatiladi. */
    if (req.is_expired) {
      body.push(el("div", { class: "map-msg map-msg-warn mt" }, [
        el("div", { class: "map-msg-title", text: "\u23f3 " + t("req.expired") }),
        el("div", { class: "map-msg-sub", text: t("req.expired_hint") }),
      ]));
    }
    if (role === "admin" && req.status === "pending") {
      body.push(el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-danger btn-sm f1", icon: "checkup", text: "" + t("req.reject"),
          onclick: () => { m.close(); rejectRequest(req.id); } }),
        el("button", { class: "btn btn-primary btn-sm f1", icon: "check_circle", text: "" + t("req.approve"),
          onclick: () => { m.close(); approveRequest(req); } }),
      ]));
    }
    m.body.append(...body);
  }

  async function approveRequest(req) {
    const instructors = (await API.get("admin/instructors")).instructors;
    const f = {
      date: input({ type: "date", value: req.preferred_date || todayISO() }),
      start: input({ type: "time", value: req.preferred_start_time || "15:00" }),
      end: input({ type: "time", value: req.preferred_end_time || "16:00" }),
      instructor: select({}, ""),
    };
    instructors.forEach((i) => f.instructor.append(el("option", {
      value: i.id, text: i.first_name + " " + i.last_name + (i.car ? ` \u{1f697} ${i.car.brand} ${i.car.model}` : ""),
    })));
    const m = modal(t("req.choose_schedule"), [
      field("\u{1f4c5} " + t("lesson.date"), f.date),
      el("div", { class: "row" }, [
        field("\u{1f552} " + t("lesson.start"), f.start, { class: "f1" }),
        field("\u{1f552} " + t("lesson.end"), f.end, { class: "f1" }),
      ]),
      field("\u{1f468}\u{1f3eb} " + t("lesson.instructor"), f.instructor),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", icon: "check_circle", text: "" + t("req.approve"),
          onclick: async () => {
            try {
              await API.post(`admin/requests/${req.id}/approve`, {
                date: f.date.value, start_time: f.start.value, end_time: f.end.value,
                instructor_id: parseInt(f.instructor.value, 10),
              });
              toast(t("misc.saved")); m.close(); App.refreshView();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ], { wide: true });
  }

  async function rejectRequest(requestId) {
    const ta = input({ placeholder: t("common.notes") + "..." });
    const m = modal("\u{1f534} " + t("req.reject"), [
      field(t("common.notes"), ta),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-danger", text: "" + t("req.reject"),
          onclick: async () => {
            try {
              await API.post(`admin/requests/${requestId}/reject`, { note: ta.value });
              toast(t("misc.saved")); m.close(); App.refreshView();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* ---------- M3: bildirishnoma bosilganda tegishli detal ---------- */
  function openNotif(n, data) {
    if (data.session_id) { openSession(data.session_id, App.me.user.role); return; }
    if (data.request_id) { openRequest(data.request_id, App.me.user.role); return; }
    if (data.message_id && n.sender_id) { openThread(n.sender_id, senderFullName(n)); return; }
  }

  /* ---------- MODUL 4: PAROL VA LOGIN O'ZGARTIRISH ----------
     Alohida xavfsizlik oqimi (Profil sahifasidagi "Parol va login
     o'zgartirish" tugmasi orqali ochiladi). "Profilni tahrirlash"da login
     maydoni yo'q — login faqat shu oqim orqali, JORIY PAROL bilan
     o'zgaradi.

     Yangi parol talablari (REAL VAQTDA, foydalanuvchi yozayotganda yangilanadi):
       * kamida 10 ta belgi,
       * kamida bitta kichik harf (a-z),
       * kamida bitta bosh harf (A-Z),
       * kamida bitta raqam (0-9),
       * tavsiya: maxsus belgi (!@#$%^&*).
     Bu tekshiruv FAQAT qulaylik uchun — xuddi shu qoidalar backendda ham
     QAYTA bajariladi (frontendga ishonilmaydi). */
  const PW_RULES = [
    { key: "len",   test: (p) => String(p || "").length >= 10 },
    { key: "lower", test: (p) => /[a-z]/.test(String(p || "")) },
    { key: "upper", test: (p) => /[A-Z]/.test(String(p || "")) },
    { key: "digit", test: (p) => /\d/.test(String(p || "")) },
    { key: "special", test: (p) => /[^A-Za-z0-9]/.test(String(p || "")) },
  ];

  function pwChecklist(pw) {
    const rows = PW_RULES.map((r) => {
      const ok = r.test(pw);
      const item = el("div", { class: "pw-rule" + (ok ? " ok" : " bad") }, [
        el("span", { class: "pw-rule-mark", text: ok ? "\u2713" : "\u2717" }),
        el("span", { class: "pw-rule-text", text: t("auth.pw_rule_" + r.key) }),
      ]);
      return item;
    });
    const box = el("div", { class: "pw-rules" }, [
      el("div", { class: "pw-rules-title", text: "" + t("auth.pw_rules") }),
      el("div", { class: "pw-rules-list" }, rows),
    ]);
    return box;
  }

  function openChangeCredentials() {
    const u = App.me.user;
    const oldPWrap = UI.passwordInput({ placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022", autocomplete: "current-password" });
    const oldP = oldPWrap.input;
    const newLogin = input({ value: u.login || "", placeholder: "usrL_\u2026", autocapitalize: "off",
      autocomplete: "off", spellcheck: false });
    const newPWrap = UI.passwordInput({ placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022", autocomplete: "new-password" });
    const newP = newPWrap.input;
    const repPWrap = UI.passwordInput({ placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022", autocomplete: "new-password" });
    const repP = repPWrap.input;

    const rulesBox = pwChecklist("");
    const matchBox = el("div", { class: "pw-match hidden" });

    const loginChangedInd = el("div", { class: "muted sm hidden", text: "" + t("profile.login_changing") });
    const pwChangedInd = el("div", { class: "muted sm hidden", text: "" + t("profile.pw_changing") });

    function refresh() {
      const pw = String(newP.value || "");
      const all = PW_RULES.slice(0, 4);
      const allOk = all.every((r) => r.test(pw));
      /* Faqat parol kiritilgan paytda tegzilgan holda parol talablari ko'rsatiladi. */
      const pwHas = !!pw;
      pwChangedInd.classList.toggle("hidden", !pwHas);
      rulesBox.classList.toggle("hidden", !pwHas);
      PW_RULES.forEach((r, i) => {
        const row = rulesBox.querySelectorAll(".pw-rule")[i];
        if (!row) return;
        const ok = r.test(pw);
        row.classList.toggle("ok", ok);
        row.classList.toggle("bad", !ok);
        row.querySelector(".pw-rule-mark").textContent = ok ? "\u2713" : "\u2717";
      });
      const rep = String(repP.value || "");
      if (!pw && !rep) {
        matchBox.classList.add("hidden");
      } else {
        matchBox.classList.remove("hidden");
        const same = !!rep && pw === rep;
        matchBox.className = "pw-match " + (same ? "ok" : "bad");
        matchBox.textContent = same ? "\u2713 " + t("auth.pw_match_ok") : "\u2717 " + t("auth.pw_match_bad");
      }
      return allOk;
    }

    /* MODUL 1.3 — login formati: `usrL_` + 14–32 ta harf/raqam.
       Bu backend'dagi `is_valid_login()` (app/auth.py: LOGIN_RE) bilan
       BIR XIL. Backend baribir tekshiradi — frontend faqat foydalanuvchiga
       darhol ko'rsatadi. */
    const LOGIN_RE_JS = /^usrL_[A-Za-z0-9]{14,32}$/;
    const loginHint = el("div", { class: "pw-match hidden" });

    function checkLogin() {
      const val = String(newLogin.value || "").trim();
      const changed = !!val && val !== (u.login || "");
      loginChangedInd.classList.toggle("hidden", !changed);
      if (!changed) { loginHint.classList.add("hidden"); return true; }
      const ok = LOGIN_RE_JS.test(val);
      loginHint.classList.remove("hidden");
      loginHint.className = "pw-match " + (ok ? "ok" : "bad");
      loginHint.textContent = ok
        ? "\u2713 " + t("profile.login_format_ok")
        : "\u2717 " + t("err.profile.login_format");
      return ok;
    }

    newLogin.addEventListener("input", checkLogin);
    [newP, repP].forEach((i) => i.addEventListener("input", refresh));
    refresh();
    checkLogin();

    const saveBtn = el("button", { class: "btn btn-primary", text: "" + t("common.save"), disabled: "" });

    function updateSave() {
      const cur = String(oldP.value || "");
      const login = String(newLogin.value || "").trim();
      const pw = String(newP.value || "");
      const rep = String(repP.value || "");
      const loginChanged = !!login && login !== (u.login || "");
      const pwChanged = !!pw;
      if (!cur || (!loginChanged && !pwChanged)) {
        saveBtn.disabled = true;
        return false;
      }
      let ok = true;
      if (loginChanged && !checkLogin()) ok = false;
      if (pwChanged) {
        if (!refresh()) ok = false;
        if (!rep || pw !== rep) ok = false;
      }
      saveBtn.disabled = !ok;
      return ok;
    }

    [oldP, newLogin, newP, repP].forEach((i) => i.addEventListener("input", updateSave));
    updateSave();

    const m = modal("\u{1f510} " + t("profile.change_credentials"), [
      el("p", { class: "field-hint mb", text: t("profile.change_credentials_hint") }),
      field(t("profile.current_password"), oldPWrap),
      field(t("profile.new_login"), newLogin, { hint: t("profile.login_hint") }),
      loginChangedInd,
      loginHint,
      field(t("profile.new_password"), newPWrap),
      pwChangedInd,
      rulesBox,
      field(t("profile.confirm_new_password"), repPWrap),
      matchBox,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        saveBtn,
      ]),
    ]);
    saveBtn.onclick = async () => {
      const cur = String(oldP.value || "");
      const login = String(newLogin.value || "").trim();
      const pw = String(newP.value || "");
      const rep = String(repP.value || "");
      const loginChanged = !!login && login !== (u.login || "");
      const pwChanged = !!pw;
      if (!cur) return toast(t("auth.err.empty_password"), "error");
      if (!loginChanged && !pwChanged) return toast(t("err.auth.nothing_to_change"), "error");
      if (loginChanged && !checkLogin()) return toast(t("err.profile.login_format"), "error");
      if (pwChanged) {
        if (!refresh()) return toast(t("err.auth.password_weak"), "error");
        if (!rep) return toast(t("err.auth.confirm_required"), "error");
        if (pw !== rep) return toast(t("err.auth.password_mismatch"), "error");
      }
      try {
        await API.post("auth/change-password", {
          old_password: cur,
          new_login: loginChanged ? login : "",
          new_password: pwChanged ? pw : "",
          confirm_password: pwChanged ? rep : "",
        });
        m.close();
        toast(t("profile.credentials_saved"));
        try { await App.refreshMe(); } catch (e) {}
        App.refreshView();
      } catch (e) { errToast(e); }
    };
    return m;
  }

  /* ---------- SESSION DETAILS MODALI ---------- */
  async function openSession(id, role) {
    const m = modal("", [UI.spinner()]);
    try {
      let data;
      if (role === "admin") data = (await API.get(`admin/sessions/${id}`)).session;
      else if (role === "instructor") data = (await API.get(`instructor/sessions/${id}`)).session;
      else data = (await API.get(`student/sessions/${id}`)).session;
      m.querySelector(".modal-head h3").textContent =
        (data.date ? fmtDate(data.date) : "") + " \u00b7 " + data.start_time + "\u2013" + data.end_time;
      m.body.innerHTML = "";
      m.body.append(buildSessionBody(data, role, m));
    } catch (e) {
      m.close();
      errToast(e);
    }
  }

  function buildSessionBody(s, role, m) {
    const kids = [];
    // Asosiy ma'lumotlar
    const info = el("div", { class: "kv-grid" }, []);
    const kvs = [
      [t("lesson.instructor"), s.instructor_name || "\u2014"],
      [t("lesson.date"), fmtDate(s.date)],
      [t("lesson.time"), `${s.start_time}\u2013${s.end_time}`],
      [t("lesson.car"), s.car_name_snapshot ? `${s.car_name_snapshot} \u00b7 ${s.car_plate_snapshot}` : s.car_name_snapshot || "\u2014"],
      [t("lesson.capacity"), `${s.student_count || 0}/${s.capacity_snapshot}`],
      [t("common.status"), statusText(s.status)],
    ];
    if (role !== "student") {
      kvs.push([t("lesson.teacher_phone"), s.instructor_phone || "\u2014"]);
    }
    if (s.cancel_reason) kvs.push(["\u274c " + t("lesson.cancel_reason"), s.cancel_reason]);
    if (s.original_date && s.original_date !== s.date) {
      const from = fmtDate(s.original_date) + " " + (s.original_start_time || s.start_time);
      const to = fmtDate(s.date) + " " + s.start_time;
      kvs.push(["\u{1f504} " + t("lesson.reschedule_info"), `${from} \u2192 ${to}`]);
    }
    kvs.forEach(([k, v]) => info.append(el("div", { class: "kv" }, [el("span", { class: "k", text: k }), el("span", { class: "v", text: v })])));
    kids.push(el("div", { class: "card" }, [info]));

    // Talabalar
    if (s.students && s.students.length) {
      const list = el("div", { class: "student-list" });
      s.students.forEach((stu) => {
        const line = el("div", { class: "stu-line" }, []);
        line.append(avatar(stu, 36),
          el("div", { class: "f1" }, [
            el("div", { class: "cell-strong", text: `${stu.first_name} ${stu.last_name} ${stu.middle_name || ""}`.trim() }),
            el("div", { class: "muted sm", text: (stu.group_name || "") + " \u00b7 " + t("meeting.place") + ": " + (stu.pickup_address || "\u2014") }),
          ]));
        const acts = el("div", { class: "row gap-sm wrap" }, []);
        // MODUL 4: xarita (Yandex Maps) — matni endi "Xaritada ko'rish"
        if (role === "instructor" || role === "admin") {
          acts.append(callLink(stu.phone));
          acts.append(el("button", { class: "btn btn-light btn-sm", icon: "message", text: "" + t("lesson.message"),
            onclick: () => openMessage(stu.user_id, stu.first_name + " " + stu.last_name) }));
        }
        // davomat (instruktor)
        if (role === "instructor" && (s.status === "ongoing" || s.status === "scheduled")) {
          const att = el("div", { class: "att-row mt" }, [
            ["present", t("lesson.present"), "\u{1f7e2}"], ["late", t("lesson.late"), "\u{1f7e1}"], ["absent", t("lesson.absent"), "\u{1f534}"],
          ].map(([code, label, ico]) =>
            el("button", {
              class: "att-btn" + (stu.attendance_status === code ? ` active-${code}` : ""),
              text: `${ico} ${label}`,
              onclick: async () => {
                try {
                  await API.post(`instructor/sessions/${s.id}/attendance`, { student_id: stu.student_id, status: code });
                  toast(t("misc.saved")); m.close(); openSession(s.id, "instructor");
                } catch (e) { errToast(e); }
              },
            })));
          acts.append(att);
        }
        // talaba — pickup tahrirlash
        if (role === "student" && s.status === "scheduled") {
          acts.append(el("button", { class: "btn btn-light btn-sm", icon: "edit", text: "" + t("meeting.place_edit"),
            onclick: () => openPickupEdit(s, m) }));
        }
        line.append(acts);
        list.append(line);
      });
      kids.push(el("div", { class: "card mt" }, [el("h4", { class: "card-title", icon: "users", text: "" + t("lesson.students") + ` (${s.student_count}/${s.capacity_snapshot})` }), list]));
    } else if (role === "student") {
      // Talaba o'z seansida faqat o'zining pickup/davomat holatini ko'radi
      // (student_session_detail o'zi uchun flat qaytaradi: pickup_address, pickup_lat/lng, attendance_status)
      const line = el("div", { class: "stu-line" }, []);
      line.append(
        el("div", { class: "f1" }, [
          el("div", { class: "cell-strong", icon: "user", text: "" + t("auth.role_student") }),
          el("div", { class: "muted sm", text: t("meeting.place") + ": " + (s.pickup_address || "\u2014") }),
        ]));
      const acts = el("div", { class: "row gap-sm wrap" }, []);
      if (s.status === "scheduled") {
        acts.append(el("button", { class: "btn btn-light btn-sm", icon: "edit", text: "" + t("meeting.place_edit"),
          onclick: () => openPickupEdit(s, m) }));
      }
      if (s.attendance_status && s.attendance_status !== "unmarked") {
        const attText = { present: t("lesson.present"), late: t("lesson.late"), absent: t("lesson.absent") }[s.attendance_status] || s.attendance_status;
        acts.append(el("span", { class: "muted sm", icon: "copy", text: "" + t("lesson.attendance") + ": " + attText }));
      }
      line.append(acts);
      kids.push(el("div", { class: "card mt" }, [el("h4", { class: "card-title", icon: "users", text: "" + t("lesson.students") }), line]));
    } else {
      kids.push(el("div", { class: "card mt" }, [UI.emptyState("\u{1f465}", t("instructor.students_empty"))]));
    }

    // Status car paneli bilan birga (admin: talaba qo'shish, instruktorni almashtirish...)
    if (role === "admin") {
      kids.push(adminSessionActions(s, m));
    }
    if (role === "instructor") {
      kids.push(instructorSessionActions(s, m));
    }
    return el("div", {}, kids);
  }

/* ======================================================================
     "Uchrashuv joyi" (pickup) — VAQTINCHA ODDIY MATN REJIMI

     XARITA VAQTINCHA O'CHIRILGAN — API kalit va Geosuggest to'liq sozlangandan
     so'ng qayta yoqiladi. Sababi: Yandex API kaliti hali yo'q.

     HOZIRGI MANTIQ (butun platformada bir xil):
       * Bitta oddiy erkin MATN maydoni — "Uchrashuv joyi".
       * Xarita YO'Q, autocomplete YO'Q, koordinata kiritish YO'Q.
       * Foydalanuvchi shunchaki qo'lda yozadi: "Beshariq, Mustaqillik maydoni".
       * Majburiylik avvalgidek saqlanadi: bo'sh qoldirilsa -> 400
         (`map.address_required`).
       * `pickup_lat` / `pickup_lng` bazada NULL bo'lib qoladi (ustunlar
         O'CHIRILMAGAN — kelajakdagi xarita uchun joy saqlanadi).

     QAYTA QO'YISH (kelajakda):
       1) Bu yerdagi `MAP_DISABLED` = false qiling.
       2) Quyidagi "=== XARITA KO'DI (SAQLANGAN) ===" blokini oching va
          `openPickupEditMap()` ni asosiy funksiya qilib qo'ying
          (`_openPickupEdit_unused_map` yordamchisi shuni tayyor).
       3) `web/js/map.js` allaqachon butunligicha saqlangan (o'chirilmagan).
       4) `.env` ga `YANDEX_MAPS_API_KEY` va `YANDEX_GEOCODER_API_KEY` qo'ying.
     ====================================================================== */
  const MAP_DISABLED = true;

  function openPickupEdit(s, m) {
    /* Oddiy matn rejimi: bitta maydon, xaritasiz. */
    const addr = input({ value: s.pickup_address || "", placeholder: t("meeting.place_ph") });
    const err = el("div", { class: "map-msg map-msg-err hidden" });

    function showErr(code, detail) {
      err.textContent = errorText(code) + (detail ? " " + detail : "");
      err.classList.remove("hidden");
    }
    function clearErr() { err.textContent = ""; err.classList.add("hidden"); }

    const sm = modal(t("meeting.place"), [
      field(t("meeting.place"), addr, { hint: t("meeting.place_hint") }),
      err,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => sm.close() }),
        el("button", { class: "btn btn-primary", text: t("common.save"),
          onclick: async () => {
            clearErr();
            const text = String(addr.value || "").trim();
            /* Bo'sh qoldirilsa — server ham rad etadi. Ikki qatlamli himoya. */
            if (!text) { showErr("map.address_required"); return; }
            try {
              /* `lat`/`lng` YUBORILMAYDI -> bazada NULL qoladi (kelajak uchun). */
              await API.put(`student/sessions/${s.id}/pickup`, { address: text });
              toast(t("misc.saved")); sm.close(); m && m.close(); openSession(s.id, "student");
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* ======================================================================
     === XARITA KO'DI (VAQTINCHA ISHLATILMAYDI — KELAJAK UCHUN SAQLANGAN) ===

     Bu kod `MAP_DISABLED = false` bo'lganda qayta kerak bo'ladi. O'CHIRILMAGAN.
     Saqlangan: Yandex xaritasi, AUTOCOMPLETE (geosuggest), marker,
     reverse geocoding, "nuqta bosish" va lat/lng yuborish.
     ====================================================================== */
  function openPickupEditMap(s, m) {
    const addr = input({ value: s.pickup_address || "", placeholder: t("map.address_ph") });
    const err = el("div", { class: "map-msg map-msg-err hidden" });
    const mapBox = el("div", { class: "map-picker" });
    const mapHint = el("p", { class: "field-hint", icon: "map", text: t("map.pick_hint") });
    const mapNote = el("div", { class: "map-msg hidden" });
    const yandex = el("a", { class: "link", href: "https://yandex.uz/maps/", target: "_blank", rel: "noopener", text: "Yandex Maps" });

    /* Tanlangan koordinata — UI'da ko'rinmaydi, faqat saqlash uchun yuboriladi. */
    let picked = { lat: null, lng: null };
    if (MapView.isNum(s.pickup_lat) && MapView.isNum(s.pickup_lng)) {
      picked = { lat: Number(s.pickup_lat), lng: Number(s.pickup_lng) };
    }

    function showErr(code, detail) {
      err.textContent = errorText(code) + (detail ? " " + detail : "");
      err.classList.remove("hidden");
    }
    function clearErr() { err.textContent = ""; err.classList.add("hidden"); }
    function showNote(code, cls) {
      mapNote.textContent = t(code);
      mapNote.className = "map-msg " + (cls || "map-msg-warn");
    }

    let map = null;
    function showPoint(la, ln) {
      if (map && typeof map.setPoint === "function") map.setPoint(la, ln, false);
    }

    /* Save/Enter: autocomplete tanlanmagan bo'lsa ham, yozilgan manzil bo'yicha
       ANIQ koordinata izlanadi (noto'g'ri nuqta saqlanmasin). */
    async function resolveFromText() {
      const v = String(addr.value || "").trim();
      if (!v) return { ok: false };
      if (picked.lat !== null && picked.lng !== null) return { ok: true, lat: picked.lat, lng: picked.lng };
      const g = await MapView.geocode(v);
      if (g && MapView.isNum(g.lat) && MapView.isNum(g.lng)) {
        picked = { lat: Number(g.lat), lng: Number(g.lng) };
        showPoint(picked.lat, picked.lng);
        addr.value = g.name || v;
        if (ac) ac.setValue(addr.value);
        return { ok: true, lat: picked.lat, lng: picked.lng };
      }
      return { ok: true, lat: null, lng: null };
    }

    let ac = null;
    const sm = modal(t("meeting.place"), [
      field(t("map.address"), addr, { hint: t("map.address_hint") }),
      err,
      mapBox, mapHint, mapNote, yandex,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => sm.close() }),
        el("button", { class: "btn btn-primary", text: t("common.save"),
          onclick: async () => {
            clearErr();
            const text = String(addr.value || "").trim();
            if (!text) { showErr("map.address_required"); return; }
            try {
              const r = await resolveFromText();
              if (!r.ok) { showErr("map.geocoder_failed"); return; }
              await API.put(`student/sessions/${s.id}/pickup`, {
                address: text, lat: r.lat, lng: r.lng,
              });
              toast(t("misc.saved")); sm.close(); m && m.close(); openSession(s.id, "student");
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);

    /* Autocomplete: Yandex takliflar + xarita */
    MapView.config().then(function (c) {
      if (!c || c.geocoder_enabled !== true) {
        showNote("map.geocoder_no_key", "map-msg-err");
      } else {
        showNote("map.autocomplete_hint", "map-msg-ok");
      }
    });
    ac = MapView.attachAutocomplete(addr, {
      onPick: function (item) {
        picked = { lat: item.lat, lng: item.lng };
        clearErr();
        showPoint(item.lat, item.lng);
      },
      onNoResult: function (v) {
        if (String(v || "").trim().length >= 3) showNote("map.no_result", "map-msg-warn");
      },
      onUnavailable: function () { showNote("map.geocoder_no_key", "map-msg-err"); },
      onEnter: function () { resolveFromText(); },
    });

    Promise.resolve(MapView.mount(mapBox, {
      lat: picked.lat, lng: picked.lng,
      onChange: async function (la, ln) {
        picked = { lat: Number(la), lng: Number(ln) };
        clearErr();
        const name = await MapView.reverseGeocode(la, ln);
        if (name) {
          addr.value = name;
          if (ac) ac.setValue(name);
          showNote("map.reverse_ok", "map-msg-ok");
        } else {
          showNote("map.reverse_fail", "map-msg-warn");
        }
      },
    })).then(function (mm) { map = mm; }).catch(function () { /* xarita yuklanmadi */ });
  }
  /* === /XARITA KO'DI (VAQTINCHA ISHLATILMAYDI) === */

  /* Xarita rejimi kerak bo'lsa shu qatori ikalasini almashtiradi:
       openPickupEdit = openPickupEditMap; */
  function _openPickupEdit_unused_map(s, m) { return openPickupEditMap(s, m); }

  /* ---------- ADMIN: session boshqarish ---------- */
  function adminSessionActions(s, m) {
    const box = el("div", { class: "card mt" });
    const title = el("h4", { class: "card-title", icon: "settings", text: "" + t("common.actions") });
    const btns = el("div", { class: "row wrap gap-sm mt" });
    if (s.status === "scheduled") {
      btns.append(
        el("button", { class: "btn btn-light btn-sm", icon: "plus", text: "" + t("lesson.add_student"), onclick: () => addStudentModal(s, m) }),
        el("button", { class: "btn btn-light btn-sm", text: "\u{1f504} " + t("lesson.reschedule_btn"), onclick: () => rescheduleModal(s) }),
        el("button", { class: "btn btn-danger btn-sm", text: "\u2715 " + t("lesson.cancel_btn"), onclick: () => cancelModal(s) }),
        el("button", { class: "btn btn-light btn-sm", icon: "edit", text: "" + t("common.notes"), onclick: () => notesModal(s) }),
      );
    }
    box.append(title, btns);
    return box;
  }

  async function addStudentModal(s) {
    const students = (await API.get("admin/users?role=student&status=active")).users;
    const sel = select({ "": t("lesson.add_student") + "..." }, "", { id: "stud-sel" });
    students.forEach((u) => sel.append(el("option", { value: u.student ? u.student.id : "", text: `${u.first_name} ${u.last_name} (${u.login})` })));
    const cap = s.student_count >= s.capacity_snapshot;
    const m = modal(t("lesson.add_student"), [
      cap ? el("p", { class: "muted", icon: "alert", text: "" + t("lesson.capacity_full_warn") }) : null,
      field(t("lesson.students"), sel),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: t("common.add"),
          onclick: async () => {
            const sid = sel.value;
            if (!sid) return;
            try {
              await API.post(`admin/sessions/${s.id}/students`, { student_id: sid });
              toast(t("misc.saved")); m.close(); openSession(s.id, "admin");
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  async function rescheduleModal(s) {
    const instructors = (await API.get("admin/instructors")).instructors || [];
    const instSel = select({}, s.instructor_id);
    instructors.forEach((i) => instSel.append(el("option", { value: i.id, text: `${i.first_name} ${i.last_name}`, selected: i.id === s.instructor_id ? "selected" : "" })));
    const dateInp = input({ type: "date", value: s.date });
    const startInp = input({ type: "time", value: s.start_time });
    const endInp = input({ type: "time", value: s.end_time });
    let autoBox = el("div", { class: "field" });
    const m = modal(t("lesson.reschedule_title"), [
      field(t("lesson.date"), dateInp),
      el("div", { class: "row" }, [field(t("lesson.start"), startInp, { class: "f1" }), field(t("lesson.end"), endInp, { class: "f1" })]),
      field(t("lesson.instructor"), instSel),
      autoBox,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: t("common.save"),
          onclick: async () => {
            try {
              await API.post(`admin/sessions/${s.id}/reschedule`, {
                date: dateInp.value, start_time: startInp.value, end_time: endInp.value, instructor_id: instSel.value,
              });
              toast(t("misc.saved")); m.close(); App.refreshView();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
    instSel.addEventListener("change", async () => {
      const iid = instSel.value;
      if (!iid) return;
      const car = (await API.get(`admin/instructors`)).instructors.find((i) => String(i.id) === String(iid));
      autoBox.innerHTML = "";
      if (car && car.car) autoBox.append(field("\u{1f512} " + t("lesson.car"), el("div", { class: "input readonly", text: car.car.brand + " " + car.car.model + " \u2014 " + car.car.plate_number })));
      else autoBox.append(field("\u{1f512} " + t("lesson.car"), el("div", { class: "input readonly", text: "\u2014" })));
    });
    instSel.dispatchEvent(new Event("change"));
  }

  function cancelModal(s) {
    const reasonSel = select({
      "": t("lesson.cancel_reason") + "...",
      car: "\u{1f697} " + t("err.car_in_repair"),
      instructor: "\u{1f468}\u200d\u{1f3eb} " + t("err.instructor_busy"),
      school: "\u{1f3eb} " + t("lesson.cancel_reason"),
      schedule: "\u{1f4c5} " + t("nav.schedule"),
      other: "\u{1f4dd} " + t("common.other"),
    });
    const m = modal(t("lesson.cancel_btn"), [
      field(t("lesson.cancel_reason"), reasonSel),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-danger", text: "\u2715 " + t("lesson.cancel_btn"),
          onclick: async () => {
            try {
              await API.post(`admin/sessions/${s.id}/cancel`, { reason: reasonSel.value });
              toast(t("misc.saved")); m.close(); App.refreshView();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  function notesModal(s) {
    const ta = el("textarea", { class: "input", text: s.notes || "" });
    const m = modal(t("common.notes"), [
      ta,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: t("common.save"),
          onclick: async () => {
            try { await API.post(`admin/sessions/${s.id}/notes`, { notes: ta.value }); toast(t("misc.saved")); m.close(); }
            catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* ---------- INSTRUKTOR: session boshqarish ---------- */
  function instructorSessionActions(s, m) {
    const box = el("div", { class: "card mt" });
    const btns = el("div", { class: "row wrap gap-sm mt" });
    if (s.status === "scheduled") {
      btns.append(el("button", { class: "btn btn-primary", icon: "play", text: "" + t("lesson.start_btn"),
        onclick: async () => {
          try {
            await API.post(`instructor/sessions/${s.id}/start`);
            toast(t("misc.saved")); m.close(); openSession(s.id, "instructor"); App.refreshView();
          } catch (e) { errToast(e); }
        } }),
        el("button", { class: "btn btn-light btn-sm", text: "\u{1f504} " + t("lesson.reschedule_btn"), onclick: () => instructorRescheduleModal(s, m) }),
        el("button", { class: "btn btn-danger btn-sm", text: "\u2715 " + t("lesson.cancel_btn"), onclick: () => instructorCancelModal(s, m) }),
      );
    }
    if (s.status === "ongoing") {
      btns.append(el("button", { class: "btn btn-cyan", text: "\u23f9 " + t("lesson.finish_btn"),
        onclick: async () => {
          try {
            await API.post(`instructor/sessions/${s.id}/finish`);
            toast(t("misc.saved")); m.close(); openSession(s.id, "instructor"); App.refreshView();
          } catch (e) { errToast(e); }
        } }));
    }
    if (btns.children.length) box.append(el("h4", { class: "card-title", icon: "settings", text: "" + t("common.actions") }), btns);
    return box;
  }

  /* Instruktor: mashg'ulotni ko'chirish (sana/vaqt — instruktor o'zgaradi) */
  function instructorRescheduleModal(s, m) {
    const dateInp = input({ type: "date", value: s.date });
    const startInp = input({ type: "time", value: s.start_time });
    const endInp = input({ type: "time", value: s.end_time });
    const mm = modal(t("lesson.reschedule_title"), [
      field(t("lesson.date"), dateInp),
      el("div", { class: "row" }, [field(t("lesson.start"), startInp, { class: "f1" }), field(t("lesson.end"), endInp, { class: "f1" })]),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => mm.close() }),
        el("button", { class: "btn btn-primary", text: t("common.save"),
          onclick: async () => {
            try {
              await API.post(`instructor/sessions/${s.id}/reschedule`, {
                date: dateInp.value, start_time: startInp.value, end_time: endInp.value,
              });
              toast(t("misc.saved"));
              if (m) m.close();
              mm.close();
              openSession(s.id, "instructor");
              App.refreshView();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* Instruktor: mashg'ulotni sababi bilan bekor qilish */
  function instructorCancelModal(s, m) {
    const reasonSel = select({
      "": t("lesson.cancel_reason") + "...",
      car: "\u{1f697} " + t("err.car_in_repair"),
      instructor: "\u{1f468}\u200d\u{1f3eb} " + t("err.instructor_busy"),
      school: "\u{1f3eb} " + t("lesson.cancel_reason"),
      schedule: "\u{1f4c5} " + t("nav.schedule"),
      other: "\u{1f4dd} " + t("common.other"),
    });
    const mm = modal(t("lesson.cancel_btn"), [
      field(t("lesson.cancel_reason"), reasonSel),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => mm.close() }),
        el("button", { class: "btn btn-danger", text: "\u2715 " + t("lesson.cancel_btn"),
          onclick: async () => {
            try {
              await API.post(`instructor/sessions/${s.id}/cancel`, { reason: reasonSel.value });
              toast(t("misc.saved"));
              if (m) m.close();
              mm.close();
              openSession(s.id, "instructor");
              App.refreshView();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* ---------- ADMIN: foydalanuvchi yaratish/tahrirlash ---------- */
  async function openUserForm(role, user) {
    const isEdit = !!user;
    const f = {};
    const wrap = el("div", {});
    const personal = el("div", { class: "grid-2" }, []);
    f.first_name = input({ value: user ? user.first_name : "" });
    f.last_name = input({ value: user ? user.last_name : "" });
    f.middle_name = input({ value: user ? user.middle_name : "" });
    f.birth_date = input({ type: "date", value: user ? user.birth_date : "" });
    f.gender = select({ "": t("common.all"), erkak: "Erkak", ayol: "Ayol" }, user ? user.gender : "");
    f.phone = input({ value: user ? user.phone : "", placeholder: "+998 90 123 45 67" });
    f.secondary_phone = input({ value: user ? user.secondary_phone : "" });
    personal.append(
      field(t("common.last_name"), f.last_name), field(t("common.name"), f.first_name),
      field(t("common.middle_name"), f.middle_name), field(t("student.birth_date"), f.birth_date),
      field(t("student.gender"), f.gender), field(t("common.phone"), f.phone),
    );
    if (role === "student") personal.append(field(t("student.phone2"), f.secondary_phone));
    wrap.append(el("h4", { class: "card-title", icon: "user", text: "" + t("common.name") }), personal);

    const extra = el("div", { class: "grid-2 mt" }, []);
    if (role === "student") {
      f.group_name = input({ value: user && user.student ? user.student.group_name : "" });
      f.license_category = input({ value: user && user.student ? user.student.license_category : "B" });
      f.address = input({ value: user && user.student ? user.student.address : "" });
      f.notes = input({ value: user && user.student ? user.student.notes : "" });
      f.total_lessons_target = input({
        type: "number", min: "1", max: "999",
        placeholder: t("users.total_lessons_group_placeholder"),
        value: user && user.student && user.student.total_lessons_target
          ? user.student.total_lessons_target : "",
      });
      extra.append(
        field(t("student.group"), f.group_name), field(t("student.category"), f.license_category),
        field(t("student.address"), f.address), field(t("common.notes"), f.notes),
        // MODUL 5: individual "Jami darslar" maqsadi. Bo'sh qoldirilsa —
        // platformaning umumiy (ommaviy) sozlamasi qo'llaniladi.
        field(t("users.total_lessons"), f.total_lessons_target, { hint: t("users.total_lessons_hint") }),
      );
    } else if (role === "instructor") {
      f.license_categories = input({ value: user && user.instructor ? user.instructor.license_categories : "B" });
      f.experience_years = input({ type: "number", value: user && user.instructor ? user.instructor.experience_years : 0 });
      f.bio = el("textarea", { class: "input", text: user && user.instructor ? user.instructor.bio : "" });
      f.work_start = input({ type: "time", value: (user && user.instructor && user.instructor.work_start) || "08:00" });
      f.work_end = input({ type: "time", value: (user && user.instructor && user.instructor.work_end) || "18:00" });
      f.break_start = input({ type: "time", value: (user && user.instructor && user.instructor.break_start) || "13:00" });
      f.break_end = input({ type: "time", value: (user && user.instructor && user.instructor.break_end) || "14:00" });
      f.work_days = select(
        { mon: t("misc.monday"), tue: t("misc.tuesday"), wed: t("misc.wednesday"), thu: t("misc.thursday"), fri: t("misc.friday"), sat: t("misc.saturday"), sun: t("misc.sunday") },
        "", { multiple: "" },
      );
      const selDays = user && user.instructor ? (user.instructor.work_days || "[]") : "[]";
      try { JSON.parse(selDays).forEach((d) => { const o = Array.from(f.work_days.options).find((o2) => o2.value === d); if (o) o.selected = true; }); } catch (e) {}
      extra.append(
        field(t("instructor.license_categories") || "Toifa", f.license_categories),
        field(t("instructor.experience"), f.experience_years),
        field(t("instructor.bio"), f.bio),
        field(t("instructor.work_days"), f.work_days),
        field(t("instructor.schedule") + " (start/end)", f.work_start, { class: "f1" }),
        field("", f.work_end, { class: "f1" }),
        field(t("instructor.break") + " (from/to)", f.break_start, { class: "f1" }),
        field("", f.break_end, { class: "f1" }),
      );
    } else if (role === "admin") {
      // MODUL 3: admin uchun qo'shimcha maydonlar (guruh/toifa) kerak emas.
      extra.append(el("p", { class: "field-hint", text: t("users.admin_role_hint") }));
    }
    wrap.append(el("h4", { class: "card-title", icon: "copy", text: "" + t("common.filter"), dataset: { style: "margin-top:14px" } }), extra);

    const carBox = el("div", { class: "mt" });
    let carSel = null;
    if (role === "instructor") {
      const cars = (await API.get("admin/cars")).cars.filter((c) => c.status === "active");
      carSel = select({ "": "\u2014 " + t("car.reassign") + " \u2014" }, user && user.instructor ? user.instructor.assigned_car_id : "", {});
      cars.forEach((c) => carSel.append(el("option", { value: c.id, text: `${c.brand} ${c.model} \u2014 ${c.plate_number}`, selected: user && user.instructor && user.instructor.assigned_car_id === c.id ? "selected" : "" })));
      carBox.append(field("\u{1f697} " + t("instructor.assign_car"), carSel));
      wrap.append(carBox);
    }

    let credArea = null;
    if (!isEdit) credArea = el("div", { class: "mt muted", icon: "key", text: "" + t("student.credentials") + " \u2014 saqlangach ko'rinadi" });

    /* MODUL 3: yangi ADMIN — roli faqat admin, login/parol AVTOMATIK
       generatsiya qilinadi va 🔑 orqali keyin ham ko'riladi. */
    const addTitle = role === "student" ? t("student.add")
      : role === "instructor" ? t("instructor.add")
      : t("users.add_admin");

    const m = modal((isEdit ? t("common.edit") + ": " : addTitle), [
      wrap,
      credArea,
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: t("common.save"),
          onclick: async () => {
            let payload = {
              first_name: f.first_name.value, last_name: f.last_name.value, middle_name: f.middle_name.value,
              birth_date: f.birth_date.value, gender: f.gender.value, phone: f.phone.value, role,
            };
            if (role === "student") {
              payload.secondary_phone = f.secondary_phone.value;
              payload.group_name = f.group_name.value; payload.license_category = f.license_category.value;
              payload.address = f.address.value; payload.notes = f.notes.value;
              // MODUL 5: bo'sh = ommaviy sozlamaga qaytish (NULL)
              payload.total_lessons_target = f.total_lessons_target.value.trim();
            } else if (role === "instructor") {
              const selDays = Array.from(f.work_days.selectedOptions).map((o) => o.value);
              payload.license_categories = f.license_categories.value; payload.experience_years = parseInt(f.experience_years.value || 0);
              payload.bio = f.bio.value || ""; payload.work_days = selDays.length ? selDays : ["mon", "tue", "wed", "thu", "fri", "sat"];
              payload.work_start = f.work_start.value; payload.work_end = f.work_end.value;
              payload.break_start = f.break_start.value; payload.break_end = f.break_end.value;
            }
            try {
              if (isEdit) {
                await API.put(`admin/users/${user.id}`, { ...payload, student: payload, instructor: payload });
                if (carSel) await API.post(`admin/instructors/${user.instructor.id}/car`, { car_id: carSel.value || null });
                toast(t("misc.saved")); m.close(); App.refreshView();
              } else {
                const res = await API.post("admin/users", payload);
                m.close();
                // MODUL 3/5: yangi foydalanuvchi yaratildi. Credential'lar
                // shu yerda ko'rsatiladi, va 🔑 orqali keyin HAM ko'riladi
                // hamda o'zgartiriladi (parol shifrlangan holda saqlanadi).
                openUserCredentials(res.credentials, role === "admin"
                  ? { title: t("users.add_admin"), hint: t("users.cred_visible_note") }
                  : { hint: t("users.cred_visible_note") });
                App.refreshView();
              }
            } catch (e) { errToast(e); }
          } }),
      ]),
    ], { wide: true });
  }

  /* ============================================================
     MODUL 5 — ADMIN: LOGIN VA PAROLNI KO'RISH + BIRGA O'ZGARTIRISH
     ============================================================
     Talab: admin har bir foydalanuvchining login va parolini ko'ra olsin va
     xohlagancha o'zgartira olsin. Backend parolni AES-256-GCM bilan
     shifrlab saqlaydi (`users.password_enc`) — bu oynada ochiladi.

     Xavfsizlik: har bir ko'rish va o'zgartirish AUDIT jurnaliga yoziladi
     (`user_credentials_viewed` / `user_credentials_changed`).

     `can_view: false` bo'lsa (eski foydalanuvchi yoki kalit yo'q) —
     parol maydoni bo'sh qoladi va sabab ko'rsatiladi. Admin o'z bilgan
     parolni maydonga kiritib "biriktirish" orqali uni ko'rinadigan qila
     oladi (parol o'zgartirmaydi). */
  const LOGIN_RE_JS = /^usrL_[A-Za-z0-9]{14,32}$/;

  function credReasonText(reason) {
    if (reason === "crypto") return t("users.cred_no_crypto");
    return t("users.cred_legacy");
  }

  function openUserCredentialsManager(user, onDone) {
    const loginI = input({ class: "input", value: "", autocapitalize: "off",
      autocomplete: "off", spellcheck: false });
    const pwWrap = UI.passwordInput({ placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022", autocomplete: "off" });
    const pwI = pwWrap.input;
    const box = el("div", { class: "cred-box" });
    const note = el("p", { class: "cred-warn", icon: "warn" });
    const boxKids = [
      el("div", { class: "field-label", icon: "key", text: "" + t("student.credentials") }),
      el("div", { class: "row" }, [
        el("div", { class: "f1" }, [
          el("div", { class: "field-label", text: "" + t("auth.login") }), loginI,
        ]),
        el("button", { class: "btn btn-light btn-sm", icon: "copy", text: "" + t("common.copy"),
          onclick: () => { navigator.clipboard.writeText(loginI.value || "").then(() => toast(t("misc.saved"))); } }),
      ]),
      el("div", { class: "row" }, [
        el("div", { class: "f1" }, [
          el("div", { class: "field-label", text: "" + t("auth.password") }), pwWrap,
        ]),
        el("button", { class: "btn btn-light btn-sm", icon: "copy", text: "" + t("common.copy"),
          onclick: () => { navigator.clipboard.writeText(pwI.value || "").then(() => toast(t("misc.saved"))); } }),
      ]),
      el("div", { class: "field-hint" }, [
        el("span", { text: "" + t("users.cred_format") }),
        el("code", { text: " " + t("users.cred_format_hint") }),
      ]),
      note,
    ];
    box.append(el("div", {}, boxKids));

    let origLogin = user.login || "";
    let origPass = "";
    const saveBtn = el("button", { class: "btn btn-primary", icon: "save", text: "" + t("common.save") });
    const genBtn = el("button", { class: "btn btn-light", icon: "refresh", text: "" + t("users.cred_generate") });

    const m = modal("\u{1f511} " + t("users.cred_title") + " \u2014 " + (user.first_name ? user.first_name + " " + user.last_name : user.login), [
      box,
      el("p", { class: "field-hint mt", icon: "alert", text: "" + t("users.cred_audit_note") }),
      el("div", { class: "row end mt" }, [
        genBtn,
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        saveBtn,
      ]),
    ], { wide: true });

    function refresh() {
      const newLogin = loginI.value.trim();
      const newPass = pwI.value;
      const dirty = (newLogin && newLogin !== origLogin) || (newPass && newPass !== origPass);
      saveBtn.disabled = !dirty;
    }
    loginI.addEventListener("input", refresh);
    pwI.addEventListener("input", refresh);

    /* Parol generatsiyasi — foydalanuvchiga berish uchun. Maydonga
       yoziladi (birdan saqlanmaydi), shuning uchun admin avval ko'radi. */
    genBtn.addEventListener("click", () => {
      genBtn.disabled = true;
      API.post(`admin/users/${user.id}/credentials`, { generate_password: true })
        .then((r) => {
          pwI.value = r.password || "";
          origPass = "";              // endi "o'zgartirilgan" hisoblanadi
          note.textContent = "";
          note.className = "cred-warn";
          note.append(el("span", { text: "" + t("users.cred_generated") }));
          toast(t("misc.saved"));
          refresh();
        })
        .catch(errToast)
        .finally(() => { genBtn.disabled = false; });
    });

    /* O'zgartirish — tasdiqsiz bajarilMAYDI (parol/login = maxfiy amal). */
    saveBtn.addEventListener("click", () => {
      const newLogin = loginI.value.trim();
      const newPass = pwI.value;
      const what = [];
      if (newLogin && newLogin !== origLogin) what.push(t("auth.login"));
      if (newPass && newPass !== origPass) what.push(t("auth.password"));
      if (!what.length) { m.close(); return; }
      confirmDialog("" + t("users.cred_save_confirm", { what: what.join(" + ") }), () => {
        API.put(`admin/users/${user.id}/credentials`, { login: newLogin, password: newPass })
          .then((r) => {
            if (r.attached) {
              toast("" + t("users.cred_attached"));
            } else if (!r.changed) {
              /* "Agar admin o'zi almashtirsa, o'zgarishsiz saqlansin":
                 hech narsa o'zgarmadi — xato EMAS, oddiy xabar. */
              toast("" + t("users.cred_unchanged"));
            } else {
              const labels = (r.what || []).map((w) =>
                w === "login" ? t("auth.login") : t("auth.password"));
              toast("" + t("users.cred_saved", { what: labels.join(" + ") }));
            }
            m.close();
            if (typeof onDone === "function") onDone();
          })
          .catch(errToast);
      }, { danger: true });
    });

    /* Dastlabki yuklash — joriy login va parolni olamiz. */
    box.append(UI.spinner(""));
    API.get(`admin/users/${user.id}/credentials`).then((r) => {
      box.lastChild.remove();
      origLogin = r.login || "";
      origPass = r.password || "";
      loginI.value = origLogin;
      pwI.value = origPass;
      if (r.can_view) {
        note.className = "field-hint";
        note.append(el("span", { text: "" + t("users.cred_visible_note") }));
      } else {
        note.className = "cred-warn";
        note.append(el("span", { text: "" + credReasonText(r.reason) }));
      }
      refresh();
    }).catch((e) => {
      box.lastChild.remove();
      errToast(e);
      m.close();
    });
    return m;
  }

  function openUserCredentials(creds, opts = {}) {
    const title = opts.title || t("student.credentials");
    const m = modal("\u{1f511} " + title, [
      credBox(creds.login, creds.password, opts.hint || t("users.cred_visible_note")),
      el("p", { class: "field-hint mt", icon: "alert", text: "" + t("auth.no_registration") }),
      el("div", { class: "row end mt" }, [el("button", { class: "btn btn-primary", text: t("common.close"), onclick: () => m.close() })]),
    ]);
    return m;
  }

  /* ============================================================
     PROFIL (Modul 2 — uchala rol uchun umumiy bo'lim)
     ============================================================ */
  function profileFullName(u) {
    return [u.first_name, u.last_name, u.middle_name || ""].filter(Boolean).join(" ") || "\u2014";
  }

  function _profileRefresh() {
    App.refreshMe().then(() => App.refreshView());
  }

  /* ---- Avatar: tanlash → kesish (crop) → yuklash ---- */
  function pickAvatar(user) {
    const fi = el("input", { type: "file", accept: "image/jpeg,image/png,image/webp", style: "display:none" });
    document.body.appendChild(fi);
    fi.addEventListener("change", () => {
      const file = fi.files && fi.files[0];
      fi.remove();
      if (!file) return;
      if (!/^image\/(jpeg|png|webp)$/.test(file.type)) return errToast({ code: "img.format" });
      if (file.size > 5 * 1024 * 1024) return errToast({ code: "img.size" });
      openCropModal(file, async (dataUrl) => {
        try {
          await API.put("me/profile/avatar", { image: dataUrl });
          toast(t("profile.photo_saved"));
          _profileRefresh();
        } catch (e) { errToast(e); }
      });
    });
    fi.click();
  }

  function openCropModal(file, onDataUrl) {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => build(img);
      img.src = reader.result;
    };
    reader.readAsDataURL(file);

    function build(img) {
      const nw = img.naturalWidth, nh = img.naturalHeight;
      const STAGE = 380;
      const fit = Math.min(STAGE / nw, STAGE / nh);
      const dw = Math.max(1, Math.round(nw * fit)), dh = Math.max(1, Math.round(nh * fit));
      const bigScale = Math.min(1, 1024 / Math.max(nw, nh));
      const bw = Math.max(1, Math.round(nw * bigScale)), bh = Math.max(1, Math.round(nh * bigScale));

      const stage = el("div", { class: "crop-stage", style: `width:${dw}px;height:${dh}px;max-width:100%` });
      const cv = el("canvas", { width: dw, height: dh, style: "display:block;width:100%;height:100%" });
      cv.getContext("2d").drawImage(img, 0, 0, dw, dh);

      let sqSize = Math.min(dw, dh);
      let sx = Math.round((dw - sqSize) / 2), sy = Math.max(0, Math.round((dh - sqSize) / 2));
      const sq = el("div", { class: "crop-sq", style: `width:${sqSize}px;height:${sqSize}px;left:${sx}px;top:${sy}px` });

      let dragging = false, offX = 0, offY = 0;
      sq.addEventListener("pointerdown", (e) => {
        dragging = true; offX = e.clientX - sx; offY = e.clientY - sy;
        sq.setPointerCapture(e.pointerId);
      });
      sq.addEventListener("pointermove", (e) => {
        if (!dragging) return;
        const rect = stage.getBoundingClientRect();
        const ratioX = rect.width ? dw / rect.width : 1;
        const ratioY = rect.height ? dh / rect.height : 1;
        sx = Math.max(0, Math.min(dw - sqSize, e.clientX - offX));
        sy = Math.max(0, Math.min(dh - sqSize, e.clientY - offY));
        sq.style.left = sx + "px"; sq.style.top = sy + "px";
      });
      sq.addEventListener("pointerup", () => { dragging = false; });

      const doCrop = () => {
        const out = el("canvas", { width: 512, height: 512 });
        const octx = out.getContext("2d");
        octx.imageSmoothingQuality = "high";
        const bcv = el("canvas", { width: bw, height: bh });
        bcv.getContext("2d").drawImage(img, 0, 0, bw, bh);
        const srcX = Math.round(sx * (bw / dw)), srcY = Math.round(sy * (bh / dh));
        const srcW = Math.round(sqSize * (bw / dw)), srcH = Math.round(sqSize * (bh / dh));
        octx.drawImage(bcv, srcX, srcY, srcW, srcH, 0, 0, 512, 512);
        return out.toDataURL("image/jpeg", 0.9);
      };

      const m = modal(t("profile.crop"), [
        el("p", { class: "field-hint mb", text: "" + t("profile.crop_help") }),
        stage,
        el("div", { class: "row end mt" }, [
          el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
          el("button", { class: "btn btn-cyan", icon: "check", text: "" + t("profile.crop") + " \u2702",
            onclick: () => { onDataUrl(doCrop()); m.close(); } }),
        ]),
      ]);
      stage.append(cv, sq);
    }
  }

  /* ---- BAND 15: "Profilim" -> "Tahrirlash"
       Tahrirlanadigan 5 ta maydon:
         1. Tug'ilgan sana (birth_date)
         2. Telefon (phone)
         3. LOGIN — `usrL_` formatida va UNIKAL bo'lishi shart
         4. Guruh (group_name)          — talaba uchun
         5. Haydovchilik toifasi (license_category) — talaba uchun

       PAROL BU YERDA YO'Q: ko'rsatilmaydi, tahrirlanmaydi. Uning o'zgarishi
       faqat `Parolni o'zgartirish` oqimi orqali (eski parol + kuchli yangi).
       "Ro'yxatga olingan sana" (enrolled_at) ham tahrirlanmaydi va talabaga
       ko'rsatilmaydi — bu ma'lumot faqat admin uchun (BAND 16). */
  function editProfileModal(user) {
    const isStudent = (user.role === "student");
    const stu = (App.me.student || {});
    const fName = input({ value: user.first_name || "" });
    const lName = input({ value: user.last_name || "" });
    const mName = input({ value: user.middle_name || "" });
    const phone = input({ value: user.phone || "", placeholder: "+998 90 123 45 67", inputmode: "tel" });
    const birth = input({ type: "date", value: user.birth_date || "", max: Shared.todayISO() });
    const group = input({ value: stu.group_name || "", placeholder: t("student.group_ph") });
    const cat = input({ value: stu.license_category || "", placeholder: t("student.category_ph") });

    const rows = [el("div", { class: "grid-2" }, [
      field(t("common.last_name"), lName),
      field(t("common.first_name"), fName),
      field(t("common.middle_name"), mName),
      field(t("common.phone"), phone),
      field(t("student.birth_date"), birth),
    ])];
    if (isStudent) {
      rows.push(el("div", { class: "grid-2" }, [
        field(t("student.group"), group),
        field(t("student.category"), cat),
      ]));
    }
    rows.push(el("div", { class: "map-msg map-msg-warn mt" }, [
      el("div", { text: t("profile.password_not_here") }),
    ]));
    rows.push(el("div", { class: "row end mt" }, [
      el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
      el("button", { class: "btn btn-primary", text: "" + t("common.save"),
        onclick: async () => {
          const payload = {
            first_name: fName.value, last_name: lName.value,
            middle_name: mName.value, phone: phone.value,
            birth_date: birth.value,
          };
          if (isStudent) {
            payload.group_name = group.value;
            payload.license_category = cat.value;
          }
          try {
            const r = await API.put("me/profile", payload);
            toast(t("misc.saved")); m.close();
            _profileRefresh();
          } catch (e) { errToast(e); }
        } }),
    ]));

    const m = modal(t("profile.edit"), rows);
  }

  /* ---- 2FA ---- */
  function twoFAButtons() {
    const u = App.me.user;
    if (u.totp_enabled) {
      return [
        badge("blue", t("profile.twofa_enabled")),
        el("button", { class: "btn btn-light btn-sm", icon: "shield", text: "" + t("profile.twofa_disable"), onclick: () => disableTwoFA() }),
      ];
    }
    return [
      badge("b-gray", t("profile.twofa_disabled")),
      el("button", { class: "btn btn-light btn-sm", icon: "shield", text: "" + t("profile.twofa_enable"), onclick: () => enableTwoFA() }),
    ];
  }

  function enableTwoFA() {
    const pw = input({ type: "password", placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022" });
    const phone = input({ type: "tel", placeholder: "+998 90 123 45 67" });
    if (App.me.user.phone) phone.value = App.me.user.phone;
    const m = modal("\u{1f510} " + t("profile.twofa"), [
      el("p", { class: "field-hint", text: "" + t("profile.twofa_password_hint") }),
      field(t("auth.old_password"), pw),
      el("p", { class: "field-hint", text: "" + t("profile.twofa_phone_hint") }),
      field(t("common.phone"), phone),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-primary", text: "" + t("auth.save"),
          onclick: async () => {
            try {
              await API.post("me/2fa/enable", { password: pw.value, phone: phone.value });
              m.close();
              twoFACodeStep();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  function twoFACodeStep() {
    const code = input({ inputmode: "numeric", placeholder: "123456", autocomplete: "one-time-code",
      style: "letter-spacing:.4em;font-weight:800" });
    const m = modal("\u{1f510} " + t("profile.twofa"), [
      el("p", { class: "field-hint mb", text: "" + t("profile.twofa_sms_sent") }),
      field(t("profile.twofa_code"), code),
      el("div", { class: "row between wrap mb" }, [
        el("span", { class: "muted sm", text: "" + t("profile.twofa_sms_note") }),
      ]),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-cyan", text: "" + t("profile.twofa_confirm"),
          onclick: async () => {
            try {
              await API.post("me/2fa/verify-enable", { code: code.value });
              toast(t("profile.twofa_enabled")); m.close();
              _profileRefresh();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  function disableTwoFA() {
    const pw = input({ type: "password", placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022" });
    const m = modal("\u{1f513} " + t("profile.twofa"), [
      el("p", { class: "field-hint", text: "" + t("profile.twofa_password_hint") }),
      field(t("auth.old_password"), pw),
      el("div", { class: "row end mt" }, [
        el("button", { class: "btn btn-light", text: t("common.cancel"), onclick: () => m.close() }),
        el("button", { class: "btn btn-danger", text: "" + t("profile.twofa_disable"),
          onclick: async () => {
            try {
              await API.post("me/2fa/disable", { password: pw.value });
              toast(t("profile.twofa_disabled")); m.close();
              _profileRefresh();
            } catch (e) { errToast(e); }
          } }),
      ]),
    ]);
  }

  /* ---- Asosiy profil ko'rinishi (3 rol uchun) ----
     BAND 15: `opts.editable` — "Tahrirlash" tugmasi chiqadi.
     Parol bu yerda KO'RSATILMAYDI (faqat "Parolni o'zgartirish" tugmasi). */
  function renderProfile(opts = {}) {
    const u = App.me.user;
    const wrap = el("div", {}, [el("h3", { class: "mb", icon: "user", text: "" + t("nav.profile") })]);
    const big = el("div", { class: "profile-avatar-wrap" }, [
      avatar(u, 76),
      el("button", { class: "avatar-upload", icon: "camera", title: t("profile.upload_photo"),
        onclick: () => pickAvatar(u) }),
    ]);
    const actions = el("div", { class: "row gap-sm mt wrap" }, []);
    if (opts.editable !== false) {
      actions.append(el("button", { class: "btn btn-cyan btn-sm", icon: "edit", text: "" + t("profile.edit"),
        onclick: () => editProfileModal(u) }));
    }
    actions.append(el("button", { class: "btn btn-primary btn-sm", icon: "lock", text: "" + t("profile.change_credentials"),
      onclick: () => openChangeCredentials() }));
    const head = el("div", { class: "profile-head" }, [
      big,
      el("div", { class: "f1" }, [
        el("div", { class: "profile-name", text: profileFullName(u) }),
        el("div", { class: "muted", text: opts.roleLabel || u.role }),
        actions,
      ]),
    ]);
    const card = el("div", { class: "card" }, [head]);
    (opts.kvs || []).forEach(([k, v]) =>
      card.append(el("div", { class: "kv" }, [el("span", { class: "k", text: k }), el("span", { class: "v", text: v })]))
    );
    card.append(el("div", { class: "kv" }, [
      el("span", { class: "k", icon: "shield", text: "" + t("profile.twofa") }),
      el("div", { class: "v", style: "display:flex;align-items:center;gap:8px;flex-wrap:wrap" }, twoFAButtons()),
    ]));
    wrap.append(card);
    return wrap;
  }

  /* ---------- M12: SOZLAMALAR (3 rol uchun umumiy sahifa) ---------- */
  function _lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function _lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  function applyTheme(theme) {
    const saved = theme || _lsGet("theme") || "light";
    document.documentElement.dataset.theme = saved === "dark" ? "dark" : "light";
    return saved;
  }

  /* BAND 17: bildirishnoma sozlamalari — 3 ta REAL soz-lama, barchasi DB'da.
     `[frontend kalit, DB ustuni]`:
       - "So'rovlar" va "Xavfsizlik hodisalari" olib tashlandi (BAND 8).
       - "Admin xabarlari" alohida: `message` (tizim ichi chat) dan farqlanadi. */
  const NOTIF_PREFS = [
    ["reminder", "lesson_reminders", "settings.notif_reminder"],
    ["admin", "admin_messages", "settings.notif_admin"],
    ["lesson", "lesson_status_updates", "settings.notif_lesson"],
    ["message", "messages", "settings.notif_message"],
    ["requests", "requests", "settings.notif_request"],
    ["security", "security", "settings.notif_security"],
  ];

  function settingsPage(opts = {}) {
    const isAdmin = !!opts.isAdmin;
    const wrap = el("div", {}, [el("h3", { class: "mb", icon: "settings", text: "" + t("settings.title") })]);
    const body = el("div", {});
    wrap.append(body);
    body.append(UI.spinner());
    Promise.all([
      API.get("me/settings"),
      isAdmin ? API.get("admin/settings") : Promise.resolve(null),
      API.get("me/sessions"),
    ]).then(([meS, adminS, sessR]) => {
      const m = (meS && meS.settings) || {};
      const s = (adminS && adminS.settings) || {};
      const sessions = (sessR && sessR.sessions) || [];
      body.innerHTML = "";
      body.append(
        langSettingsCard(m),
        themeSettingsCard(m),
        notifSettingsCard(m),
        securitySettingsCard(sessions),
        ...(isAdmin ? [platformSettingsCard(s)] : []),
        logoutCard(),
      );
    }).catch((e) => {
      body.innerHTML = "";
      body.append(UI.emptyState("\u26a0\ufe0f", I18N.errorText(e && e.code) || t("settings.title")));
    });
    return wrap;
  }

  function langSettingsCard(m) {
    const current = I18N.getLang();
    const box = el("div", { class: "lang-switch" });
    Object.entries(I18N.LANGS).forEach(([code, label]) => {
      const btn = el("button", { class: "lang-btn" + (current === code ? " active" : ""), text: label,
        onclick: () => {
          if (code === I18N.getLang()) return;
          I18N.setLang(code);
          API.put("me/settings", { lang: code }).catch(() => {});
          toast(t("misc.saved"));
        } });
      box.append(btn);
    });
    return el("div", { class: "card mb" }, [
      el("h3", { class: "card-title", text: "\u{1f310} " + t("settings.lang_title") }),
      el("div", { class: "muted sm mb", text: t("settings.region_info") }),
      box,
    ]);
  }

  function themeSettingsCard(m) {
    const saved = (m.theme === "dark" || _lsGet("theme") === "dark") ? "dark" : "light";
    const box = el("div", { class: "lang-switch" });
    const items = [["light", t("settings.theme_light")], ["dark", t("settings.theme_dark")]];
    const btns = [];
    items.forEach(([val, label]) => {
      const btn = el("button", { class: "lang-btn" + (saved === val ? " active" : ""), text: label,
        onclick: () => {
          _lsSet("theme", val);
          applyTheme(val);
          API.put("me/settings", { theme: val }).catch(() => {});
          btns.forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
          toast(t("misc.saved"));
        } });
      btns.push(btn);
      box.append(btn);
    });
    return el("div", { class: "card mb" }, [
      el("h3", { class: "card-title", text: "\u{1f3a8} " + t("settings.theme_title") }),
      el("div", { class: "muted sm mb", text: t("settings.theme_hint") }),
      box,
    ]);
  }

  /* BAND 17: har bir tugma REAL — o'zgarish darhol `PUT /api/me/settings`
     orqali `notification_settings` jadvaliga yoziladi. Brauzer yopilsa yoki
     boshqa qurilmada kirsangiz ham holat saqlanib qoladi (localStorage EMAS). */
  function notifSettingsCard(m) {
    const dbPrefs = Object.assign({}, m.notification_settings || {});
    const legacy = Object.assign({}, m.notif || {});
    /* Toggle o'zgarishida faqat o'sha ustunni yuboramiz — boshqalari buzilmaydi. */
    function save(column, value) {
      return API.put("me/settings", { notification_settings: { [column]: !!value } })
        .catch((e) => errToast(e));
    }
    const card = el("div", { class: "card mb" }, [
      el("h3", { class: "card-title", icon: "bell", text: "" + t("settings.notif_title") }),
      el("div", { class: "muted sm mb", text: t("settings.notif_hint") }),
      el("div", {}, NOTIF_PREFS.map(([legacyKey, column, labelKey]) => {
        /* Manba: yangi `notification_settings`; eski `notif` — fallback. */
        const on = Object.prototype.hasOwnProperty.call(dbPrefs, column)
          ? dbPrefs[column] !== false
          : legacy[legacyKey] !== false;
        return toggleRow({
          title: "" + t(labelKey + "_title"),
          desc: (() => { const d = t(labelKey + "_desc"); return d && d !== labelKey + "_desc" ? d : ""; })(),
          checked: on,
          onChange: (v) => { save(column, v); toast(t("misc.saved")); },
        });
      })),
    ]);
    return card;
  }

  function securitySettingsCard(sessions) {
    const card = el("div", { class: "card" }, [
      el("h3", { class: "card-title", text: "\u{1f6e1}\ufe0f " + t("settings.security_title") }),
      el("div", { class: "row between mb wrap" }, [
        el("div", { class: "muted sm", text: t("settings.sessions_title") + ": " + sessions.length }),
        el("div", { class: "row gap-sm wrap" }, [
          el("button", { class: "btn btn-light btn-sm", icon: "lock", text: "" + t("profile.change_credentials"),
            onclick: () => openChangeCredentials() }),
          el("button", { class: "btn btn-danger btn-sm", text: t("settings.revoke_all"),
            onclick: () => confirmDialog(t("settings.revoke_all_confirm"), async () => {
              try {
                await API.post("me/sessions/revoke-all", {});
                // Joriy sessiya ham tugadi — keyingi API chaqiruv logout'ni ishga tushiradi
                API.get("auth/me").catch(() => {});
                toast(t("settings.sessions_current_revoked"));
              } catch (e) { errToast(e); }
            }, { danger: true, yesText: t("settings.revoke_all") }) }),
        ]),
      ]),
    ]);
    if (!sessions.length) {
      card.append(UI.emptyState("\u{1f4f5}", t("settings.sessions_empty")));
      return card;
    }
    card.append(el("div", { class: "table-wrap" }, [el("table", { class: "tbl" }, [
      el("thead", {}, [el("tr", {}, [
        el("th", { text: t("settings.sessions_created") }),
        el("th", { text: t("settings.sessions_last_seen") }),
        el("th", { text: t("settings.sessions_expires") }),
        el("th", { text: t("common.status") }),
        el("th", {}),
      ])]),
      el("tbody", {}, sessions.map((ss) => el("tr", {}, [
        el("td", { text: I18N.fmtDateTime(ss.created_at) }),
        el("td", { class: "muted", text: ss.last_seen ? I18N.fmtDateTime(ss.last_seen) : "\u2014" }),
        el("td", { class: "muted", text: I18N.fmtDateTime(ss.expires_at) }),
        el("td", {}, [ss.current ? el("span", { class: "badge b-cyan", text: t("settings.sessions_current") }) : el("span", { class: "muted sm", text: "\u2022" })]),
        el("td", { style: "text-align:right" }, [el("button", {
          class: "btn btn-light btn-sm", icon: "x", text: "" + t("settings.revoke"),
          onclick: async () => {
            try {
              const r = await API.post("me/sessions/revoke", { id: ss.id });
              if (r.current_revoked) API.get("auth/me").catch(() => {});
              else App.refreshView();
            } catch (e) { errToast(e); }
          },
        })]),
      ]))),
    ])]));
    return card;
  }

  /* Chiqish kartasi — boshqa sozlamalardan alohida ajratilgan holda,
     eng pastda. Qaytarib bo'lmaydigan (destructive) amal bo'lgani uchun
     qizil uslubda + tasdiqlash oynasi bilan. Admin, Instruktor va Talaba
     uchun bir xil komponentda bitta marta yozilgan. */
  function logoutCard() {
    return el("div", { class: "card logout-card" }, [
      el("h3", { class: "card-title", text: "\u{1f6aa} " + t("settings.logout_title") }),
      el("div", { class: "muted sm", text: t("settings.logout_hint") }),
      el("div", { class: "muted sm mb", text: t("settings.logout_desc") }),
      el("button", {
        class: "btn btn-danger", icon: "logout", text: "" + t("settings.logout_btn"),
        onclick: () => { if (window.App && App.confirmLogout) App.confirmLogout(); },
      }),
    ]);
  }

  function platformSettingsCard(s) {
    const allowVal = { v: s.allow_student_requests !== false };
    const durI = input({ type: "number", min: 15, step: 5, value: s.lesson_duration_min || 90 });
    const wsI = input({ type: "time", value: s.work_start || "" });
    const weI = input({ type: "time", value: s.work_end || "" });
    const remI = input({ type: "number", min: 1, step: 5, value: s.reminder_minutes || 60 });
    // MODUL 5: ommaviy (platforma) "Jami darslar" maqsadi
    const tgtI = input({ type: "number", min: 1, max: 999, step: 1, value: s.total_lessons_target || 30 });
    return el("div", { class: "card" }, [
      el("h3", { class: "card-title", text: "\u{1f6e0}\ufe0f " + t("settings.platform_title") }),
      el("div", { class: "muted sm mb", text: t("settings.platform_hint") }),
      el("div", { class: "mb" }, [toggleRow({
        title: "" + t("settings.allow_requests"),
        desc: t("settings.allow_requests_desc"),
        checked: allowVal.v,
        onChange: (v) => { allowVal.v = v; },
      })]),
      el("div", { class: "split-2" }, [
        field(t("settings.lesson_duration"), durI),
        field(t("settings.work_start"), wsI),
        field(t("settings.work_end"), weI),
        field(t("settings.reminder_minutes"), remI),
        // MODUL 5: ommaviy maqsad
        field(t("settings.total_lessons"), tgtI),
      ]),
      el("small", { class: "field-hint mb", text: t("settings.reminder_hint") }),
      el("small", { class: "field-hint mb", text: t("settings.total_lessons_hint") }),
      el("div", { class: "row end mt" }, [el("button", { class: "btn btn-primary", text: t("common.save"), onclick: async () => {
        try {
          await API.put("admin/settings", {
            allow_student_requests: allowVal.v,
            lesson_duration_min: Math.max(15, parseInt(durI.value, 10) || 90),
            work_start: wsI.value, work_end: weI.value,
            reminder_minutes: Math.max(1, parseInt(remI.value, 10) || 60),
            total_lessons_target: Math.max(1, Math.min(999, parseInt(tgtI.value, 10) || 30)),
          });
          toast(t("misc.saved"));
        } catch (e) { errToast(e); }
      } })]),
    ]);
  }

  /* ============================================================
     BILDIRISHNOMALAR — to'liq bo'lim (sidebar bo'limi).
     Barcha rollar uchun umumiy; filtrlash, o'chirish, tozalash.

     BAND 8  — Kategoriyalar QISQARTIRILDI: "So'rovlar" va
               "Xavfsizlik hodisalari" olib tashlandi. Qolganlari:
               Barchasi · Mashg'ulotlar · Xabarlar · Mashg'ulot eslatmalari.
     BAND 11 — Har bir bildirishnoma ALOHIDA DB qatori. Ro'yxatdagi matn
               faqat o'sha qatorning `body`si; boshqa qatorga "ko'chmaydi".
     BAND 12 — "Xabarlar" kategoriyasi FAQAT `source='ADMIN_MESSAGE'`
               (admin yuborgan xabar) — avtomatik eslatma yoki boshqa
               bildirishnoma bu yerda chiqmaydi.
     BAND 21 — `data` matni bitta joyda (`JSON.parse`) va `metadata`
               (tayyor ob'ekt) afzal ishlatiladi — noto'g'ri key/ID xatosi yo'q.
     ============================================================ */

  /* Eski `type` bo'yicha kategoriya (fallback). */
  function notifCategory(n) {
    const src = String((n && n.source) || "").toUpperCase();
    if (src === "LESSON_REMINDER") return "reminder";
    if (src === "ADMIN_MESSAGE") return "message";
    if (src === "LESSON_ASSIGNED" || src === "LESSON_COMPLETED" ||
        src === "LESSON_CANCELLED" || src === "LESSON_RESCHEDULED" ||
        src === "LESSON_STARTED") return "lesson";
    const t0 = String((n && n.type) || "").toLowerCase();
    if (t0 === "reminder") return "reminder";
    if (t0 === "admin") return "message";
    if (t0.startsWith("lesson") || t0 === "cancel") return "lesson";
    if (t0.startsWith("message") || t0.startsWith("msg")) return "message";
    return "info";
  }

  function notificationsPage() {
    const wrap = el("div", {}, []);
    const body = el("div", {}, [UI.spinner()]);
    wrap.append(body);
    API.get("me/notifications").then((res) => {
      body.innerHTML = "";
      const list = (res.notifications || []).slice();
      let filter = "all";
      /* BAND 8: faqat 4 ta filtr. */
      const CATS = [
        ["all", t("notif.all")],
        ["lesson", t("notif.cat_lesson")],
        ["message", t("notif.cat_message")],
        ["reminder", t("notif.cat_reminder")],
      ];
      const chipsRow = el("div", { class: "notif-filters" }, []);
      const listEl = el("div", { class: "notif-page" }, []);

      function render() {
        chipsRow.innerHTML = "";
        CATS.forEach(([cat, label]) => {
          chipsRow.append(el("button", {
            class: "chip" + (filter === cat ? " on" : ""),
            text: label,
            onclick: () => { filter = cat; render(); },
          }));
        });
        const items = filter === "all" ? list : list.filter((n) => notifCategory(n) === filter);
        listEl.innerHTML = "";
        if (!items.length) { listEl.append(UI.emptyState("\u{1f514}", t("notif.empty"))); return; }
        items.forEach((n) => {
          /* BAND 21: metadata bitta qatorda tayyor ob'ekt bo'lsa — ishlatiladi,
             aks holda `data` matnidan o'qiladi. Ikalasi ham bo'lmasa — {}. */
          const data = (n.metadata && typeof n.metadata === "object")
            ? n.metadata
            : (function () { try { return JSON.parse(n.data || "{}") || {}; } catch (e) { return {}; } })();
          const senderName = n.sender_id
            ? [n.sender_first_name, n.sender_last_name].filter(Boolean).join(" ") || t("notif.unknown")
            : t("notif.system");
          const senderRole = (n.sender_role || (n.sender_id ? "user" : "")) || "system";
          const senderAvatar = n.sender_id
            ? avatar({ first_name: n.sender_first_name || "?", last_name: n.sender_last_name || "",
                       profile_image: n.sender_profile_image || "" }, 34)
            : el("div", { class: "avatar notif-sys-avatar", style: "width:34px;height:34px;font-size:16px", text: "\u2699" });
          listEl.append(el("div", {
            /* BAND 21: React kaliti emas, lekin barqaror identifikator —
               `id` butun son, ko'rsatkich (index) EMAS. */
            key: "notif-" + n.id,
            class: "notif-page-item" + (n.is_read ? "" : " unread"),
            dataset: { nid: String(n.id) },
            onclick: async () => {
              if (!n.is_read) {
                n.is_read = 1;
                API.post("me/notifications/read", { id: n.id }).catch(() => {});
                render(); App.refreshMe();
              }
              Shared.openNotif(n, data);
            },
          }, [
            el("span", { class: "notif-unread-dot", "aria-hidden": "true" }),
            senderAvatar,
            el("div", { class: "f1" }, [
              el("div", { class: "notif-title", text: notifLabel(n.title) }),
              el("div", { class: "notif-meta" }, [
                el("span", { class: "notif-sender", text: senderName }),
                el("span", { class: "notif-role " + senderRole, text: roleLabel(senderRole) }),
              ]),
              el("div", { class: "notif-body", text: notifText(n, data) }),
              el("div", { class: "notif-time", text: I18N.fmtDateTime(n.created_at) }),
            ]),
            el("button", { class: "link-btn notif-del", title: t("notif.delete"), text: "\u2715",
              onclick: async (ev) => {
                ev.stopPropagation();
                try {
                  await API.post("me/notifications/delete", { id: n.id });
                  const i = list.indexOf(n);
                  if (i >= 0) list.splice(i, 1);
                  render(); App.refreshMe();
                } catch (e) { errToast(e); }
              } }),
          ]));
        });
      }
      render();
      wrap.append(
        el("h3", { class: "mb", icon: "bell", text: "" + t("notif.title") }),
        el("div", { class: "row between wrap mb" }, [
          chipsRow,
          el("div", { class: "row gap-sm wrap" }, [
            el("button", { class: "btn btn-light btn-sm", icon: "check", text: "" + t("notif.read_all"), onclick: async () => {
              await API.post("me/notifications/read", {});
              list.forEach((n) => { n.is_read = 1; });
              render(); App.refreshMe();
            } }),
            el("button", { class: "btn btn-light btn-sm", icon: "x", text: "" + t("notif.clear_all"), onclick: () => {
              confirmDialog(t("notif.clear_all_confirm"), async () => {
                await API.post("me/notifications/clear", {});
                list.length = 0;
                render(); App.refreshMe();
              }, { danger: true, yesText: t("notif.clear_all") });
            } }),
          ]),
        ]),
        listEl,
      );
    }).catch((e) => {
      body.innerHTML = "";
      body.append(UI.emptyState("\u26a0\ufe0f", I18N.errorText(e && e.code) || t("notif.title")));
    });
    return wrap;
  }

  return {
    openSession, openMessage, openChangeCredentials, credBox, rulesList,
    openUserForm, openUserCredentials, openUserCredentialsManager, openRequest, openThread, openNotif,
    renderProfile, profileFullName, pickAvatar, editProfileModal,
    settingsPage, applyTheme, notificationsPage, notifCategory,
    todayISO, timeNowHM, weekdayShort, fmtDate, fmtDateTime,
  };
})();
