/* Asosiy ilova: login, shell, marshrutlash, bildirishnomalar, tillar */
(function () {
  const { t, setLang, getLang, LANGS } = I18N;
  const UI = window.UI;
  const { el, toast, errToast, badge, statusText, avatar } = UI;

  const App = {
    me: null,            // /api/auth/me natijasi
    view: "dashboard",
    params: {},
    roleNav: {},
  };
  window.App = App;

  const NAV_KEYS = {
    admin: [
      /* MODUL 1: "Dashboard" -> "Bosh sahifa" (Talaba/Instruktor kabi).
         `nav.home` kaliti ishlatiladi — `nav.dashboard` o'chirilgan. */
      ["dashboard", "dashboard", "nav.home"],
      ["notifications", "bell", "nav.notifications"],
      ["base", "book", "nav.base"],
      ["calendar", "calendar", "nav.calendar"],
      ["requests", "inbox", "nav.requests"],
      // MODUL 6: foydalanuvchilar bitta bo'limda, ichida 3 ta tab (rol bo'yicha)
      ["users", "users", "nav.users"],
      ["cars", "car", "nav.cars"],
      ["lessons", "lessons", "nav.lessons"],
      ["reports", "chart", "nav.reports"],
      ["analytics", "pie", "nav.analytics"],
      ["audit", "list", "nav.audit"],
      ["backup", "download", "nav.backup"],
      ["settings", "settings", "nav.settings"],
      ["profile", "user", "nav.profile"],
    ],
    instructor: [
      ["dashboard", "dashboard", "nav.home"],
      ["notifications", "bell", "nav.notifications"],
      ["schedule", "calendar", "nav.schedule"],
      ["students", "student", "nav.my_students"],
      ["car", "car", "nav.my_car"],
      ["messages", "message", "nav.messages"],
      ["profile", "user", "nav.profile"],
      ["settings", "settings", "nav.settings"],
    ],
    student: [
      /* BAND 4: "Mening jadvalim" (schedule) talaba uchun BUTUNLAY olib
         tashlandi — sidebar, routing va view. Qolgan nom: "Amaliy
         mashg'ulotlarim" (lessons). */
      ["dashboard", "dashboard", "nav.home"],
      ["notifications", "bell", "nav.notifications"],
      ["lessons", "lessons", "nav.my_lessons"],
      ["history", "list", "nav.history"],
      ["requests", "inbox", "nav.requests"],
      ["profile", "user", "nav.profile"],
      ["settings", "settings", "nav.settings"],
    ],
  };

  /* BAND 4: eski manzil ("#/student/schedule") endi top'ga olib borilmaydi —
     foydalanuvchi "Mening jadvalim" o'rniga avtomatik "Amaliy mashg'ulotlarim"
     sahifasiga yuboriladi (404/bo'sh sahifa ko'rsatilmaydi). */
  const ROUTE_ALIASES = {
    "student:schedule": "student:lessons",
  };

  function resolveRoute(role, view) {
    return ROUTE_ALIASES[(role || "") + ":" + (view || "")] || view;
  }

  function navFor(role) {
    return (NAV_KEYS[role] || []).map(([v, icon, key]) => [v, icon, t(key)]);
  }

  /* ---------------- login ---------------- */
  // MODUL 2: rol bo'sh qoldirilmaydi — login paytida MAJBURIY tanlanadi.
  let selectedRole = "";
  let otpStep = false; // 2FA bosqichi: OTP kiritish maydoni ko'rsatilgan

  function resetRoleButtons() {
    selectedRole = "";
    document.querySelectorAll("#login-form .role-btn").forEach((b) => {
      b.classList.remove("active");
      b.setAttribute("aria-pressed", "false");
    });
    const sw = document.getElementById("role-switch");
    if (sw) sw.classList.remove("err");
  }

  function showFieldErr(field, msg) {
    const wrap = document.getElementById("fld-" + field);
    const errEl = document.getElementById("err-" + field);
    if (wrap) wrap.classList.add("error", "shake");
    if (errEl) { errEl.textContent = msg; errEl.classList.add("show"); }
    setTimeout(() => { if (wrap) wrap.classList.remove("shake"); }, 500);
  }
  function clearFieldErr(field) {
    const wrap = document.getElementById("fld-" + field);
    const errEl = document.getElementById("err-" + field);
    if (wrap) wrap.classList.remove("error");
    if (errEl) errEl.classList.remove("show");
  }
  function showLoginAlert(msg) {
    const al = document.getElementById("login-alert");
    if (!al) return;
    al.textContent = msg;
    al.classList.remove("hidden");
    al.classList.add("show");
  }
  function hideLoginAlert() {
    const al = document.getElementById("login-alert");
    if (!al) return;
    al.classList.remove("show");
    al.classList.add("hidden");
  }
  function setLoginLoading(on) {
    const btn = document.getElementById("login-submit");
    if (!btn) return;
    btn.classList.toggle("loading", on);
    btn.disabled = on;
    const label = btn.querySelector(".btn-login-label");
    if (label) label.textContent = on ? t("auth.signing_in") : t("auth.signin");
  }

  /* Fon rasm uchun yengil parallax (sichqoncha harakati, 10-15px) */
  function initParallax() {
    const bg = document.getElementById("login-bg");
    const screen = document.getElementById("login-screen");
    if (!bg || !screen || !matchMedia("(pointer: fine)").matches) return;
    screen.addEventListener("mousemove", (ev) => {
      const r = screen.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const nx = (ev.clientX - r.left) / r.width - 0.5;
      const ny = (ev.clientY - r.top) / r.height - 0.5;
      bg.style.transform = "translate(" + (nx * 26).toFixed(1) + "px," + (ny * 22).toFixed(1) + "px)";
    });
    screen.addEventListener("mouseleave", () => { bg.style.transform = ""; });
  }

  function showResetBox(show) {
    document.getElementById("reset-box").classList.toggle("hidden", !show);
    document.getElementById("login-form").classList.toggle("hidden", show);
  }

  function initLogin() {
    const screen = document.getElementById("login-screen");
    screen.classList.remove("hidden");
    initParallax();

    document.getElementById("eye-btn").addEventListener("click", () => {
      const p = document.getElementById("login-password");
      const show = p.type === "password";
      p.type = show ? "text" : "password";
      document.querySelector("#eye-btn .ico-eye").classList.toggle("hidden", show);
      document.querySelector("#eye-btn .ico-eye-off").classList.toggle("hidden", !show);
    });

    // Rol tanlash (MODUL 2): rol MAJBURIY. Avval "hech biri tanlanmagan" holati
    // mavjud edi — u holda backend rol tekshiruvini butunlay o'tkazib yuborardi
    // va foydalanuvchi o'z rolini ko'rsatmasdan kirishi mumkin edi.
    const roleBtns = document.querySelectorAll("#login-form .role-btn");
    function selectRole(role) {
      selectedRole = role || "";
      roleBtns.forEach((x) => {
        const on = x.dataset.role === role;
        x.classList.toggle("active", on);
        x.setAttribute("aria-pressed", on ? "true" : "false");
      });
      document.getElementById("role-switch").classList.toggle("err", !role);
      if (role) clearFieldErr("role");
    }
    roleBtns.forEach((b) => b.addEventListener("click", () => {
      selectRole(b.dataset.role);
      hideLoginAlert();
    }));

    // "Meni eslab qolish" — oldingi login saqlangan bo'lsa
    const rmBtn = document.getElementById("login-remember");
    const rememberVal = () => rmBtn.getAttribute("aria-checked") === "true";
    const setRemember = (v) => {
      rmBtn.setAttribute("aria-checked", v ? "true" : "false");
      rmBtn.classList.toggle("on", v);
    };
    rmBtn.addEventListener("click", () => setRemember(!rememberVal()));
    try {
      const saved = localStorage.getItem("rm_login");
      if (saved) {
        document.getElementById("login-username").value = saved;
        setRemember(true);
      }
    } catch (e) {}

    document.getElementById("login-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      hideLoginAlert();
      ["login", "password", "otp"].forEach(clearFieldErr);

      const login = document.getElementById("login-username").value.trim();
      const password = document.getElementById("login-password").value;
      let ok = true;
      if (!login) { showFieldErr("login", t("auth.err.empty_login")); ok = false; }
      if (!password) { showFieldErr("password", t("auth.err.empty_password")); ok = false; }
      // MODUL 2: rolni tanlash shart. Backend ham buni tekshiradi, lekin foydalanuvchi
      // noto'g'ri rolni yuborib serverga xato so'rov yubormasligi uchun ham
      // shu yerda to'xtatamiz.
      if (!selectedRole) {
        showFieldErr("role", t("auth.err.empty_role"));
        document.getElementById("role-switch").classList.add("err");
        ok = false;
      }
      if (otpStep) {
        const otpVal = document.getElementById("login-otp").value.trim();
        if (!otpVal) { showFieldErr("otp", I18N.errorText("auth.otp_required")); ok = false; }
      }
      if (!ok) {
        document.getElementById("login-card").classList.add("shake");
        setTimeout(() => document.getElementById("login-card").classList.remove("shake"), 450);
        return;
      }

      // MODUL 3: "eslab qolish" — checkbox o'chirilgan bo'lsa, eski login ham
      // tozalanadi (aks holda keyingi safar yana avtomatik to'ldirilardi).
      try {
        if (rememberVal()) localStorage.setItem("rm_login", login);
        else localStorage.removeItem("rm_login");
      } catch (e) {}

      setLoginLoading(true);
      try {
        const payload = {
          login,
          password,
          remember: rememberVal(),
          role: selectedRole,
        };
        if (otpStep) payload.otp = document.getElementById("login-otp").value.trim();
        const res = await API.post("auth/login", payload);
        otpStep = false;
        document.getElementById("fld-otp").classList.add("hidden");
        await enter(res);
      } catch (e) {
        if (e && e.code === "auth.otp_required") {
          otpStep = true;
          document.getElementById("fld-otp").classList.remove("hidden");
          showLoginAlert(I18N.errorText(e.code));
          setTimeout(() => document.getElementById("login-otp").focus(), 60);
        } else if (e && e.code === "auth.otp_invalid") {
          showFieldErr("otp", I18N.errorText(e.code));
          document.getElementById("login-otp").value = "";
          setTimeout(() => document.getElementById("login-otp").focus(), 60);
        } else if (e && e.code === "auth.user_blocked") showLoginAlert(t("auth.err.blocked"));
        else if (e && e.code === "auth.wrong_role") {
          // Xavfsizlik: foydalanuvchining HAQIQIY roli oshkor qilinmaydi
          // ("siz Talaba ekansiz" deb aytilmaydi). Faqat neytral eslatma.
          showLoginAlert(I18N.errorText("auth.wrong_role"));
          const sw = document.getElementById("role-switch");
          if (sw) sw.classList.add("err");
          showFieldErr("role", t("auth.err.role_retry"));
        }
        else if (e && e.code) {
          showLoginAlert(I18N.errorText(e.code));
          if (e.code === "auth.wrong_credentials") showFieldErr("password", I18N.errorText(e.code));
        }
        else showLoginAlert(t("auth.err.network"));
      } finally {
        setLoginLoading(false);
      }
    });

    document.getElementById("forgot-btn").addEventListener("click", () => showResetBox(true));

    const rst1 = document.getElementById("rst-step1");
    const rst2 = document.getElementById("rst-step2");
    let resetLogin = "";
    document.getElementById("reset-send").addEventListener("click", async () => {
      resetLogin = document.getElementById("reset-login").value.trim();
      if (!resetLogin) { toast(t("auth.err.empty_login")); return; }
      const snd = document.getElementById("reset-send");
      snd.disabled = true;
      try {
        const res = await API.post("auth/request-password-reset", { login: resetLogin });
        if (res && res.token) document.getElementById("reset-code").value = res.token;
        toast(t("auth.reset_requested"));
        rst1.classList.add("hidden");
        rst2.classList.remove("hidden");
      } catch (e) { errToast(e); }
      finally { snd.disabled = false; }
    });
    document.getElementById("reset-apply").addEventListener("click", async () => {
      const code = document.getElementById("reset-code").value.trim();
      const p1 = document.getElementById("reset-pass").value;
      const p2 = document.getElementById("reset-pass2").value;
      if (!code) { toast(t("auth.err.empty_login")); return; }
      if (!p1) { toast(t("auth.err.empty_password")); return; }
      if (p1 !== p2) { toast(t("auth.reset_mismatch")); return; }
      const btn = document.getElementById("reset-apply");
      btn.disabled = true;
      try {
        await API.post("auth/reset-password", { token: code, new_password: p1 });
        toast(t("auth.reset_done"), "success");
        document.getElementById("login-username").value = resetLogin;
        ["reset-login", "reset-code", "reset-pass", "reset-pass2"].forEach((id) => { document.getElementById(id).value = ""; });
        rst2.classList.add("hidden");
        rst1.classList.remove("hidden");
        showResetBox(false);
      } catch (e) { errToast(e); }
      finally { btn.disabled = false; }
    });
    document.getElementById("reset-back").addEventListener("click", () => {
      if (!rst2.classList.contains("hidden")) {
        rst2.classList.add("hidden");
        rst1.classList.remove("hidden");
      } else {
        showResetBox(false);
      }
    });

    applyLangUI();
  }

  function applyLangUI() {
    document.querySelectorAll("[data-lang]").forEach((b) => b.classList.toggle("active", b.dataset.lang === getLang()));
    document.querySelectorAll("[data-i18n]").forEach((el2) => {
      const k = el2.getAttribute("data-i18n");
      const text = t(k);
      if (el2.tagName === "INPUT" || el2.tagName === "TEXTAREA") el2.placeholder = text;
      else el2.textContent = text;
    });
    document.querySelectorAll("[data-i18n-attr]").forEach((el2) => {
      (el2.getAttribute("data-i18n-attr") || "").split(/\s*,\s*/).forEach((pair) => {
        const i = pair.indexOf(":");
        if (i > 0) el2.setAttribute(pair.slice(0, i), t(pair.slice(i + 1)));
      });
    });
  }

  async function enter(loginRes) {
    try {
      const me = await API.get("auth/me");
      App.me = me;
      document.getElementById("login-screen").classList.add("hidden");
      document.getElementById("app-shell").classList.remove("hidden");
      buildSidebar();
      buildTopbar();
      App.go("dashboard");
      if (me.user.must_change_password) {
        setTimeout(() => {
          const m = Shared.openChangePassword(false);
          const inp = m.querySelectorAll("input");
          inp.forEach((i) => i.value = "");
        }, 300);
      }
    } catch (e) {
      errToast(e);
    }
  }

  /* ---------------- sessiyani yakunlash (logout) ----------------
     Barcha rollar uchun umumiy. Sezuvchan ma'lumotlar (profil, ko'rinish,
     keshlangan DOM) to'liq tozalanadi — keyingi foydalanuvchi oldingi
     foydalanuvchining ma'lumotlarini ko'rmasligi SHART.
     Server tomonida ham sessiya `auth/logout` orqali o'chiriladi va
     sid cookie tozalanadi (server.py). */
  let loggingOut = false;

  function clearSessionState() {
    App.me = null;
    App.view = "dashboard";
    App.params = {};
    App.roleNav = {};
    otpStep = false; // 2FA bosqichi qolib ketmasin

    // Himoyalangan sahifa DOM'i va navigatsiya tozalanadi
    const viewEl = document.getElementById("view");
    if (viewEl) viewEl.innerHTML = "";
    const navEl = document.getElementById("sidebar-nav");
    if (navEl) navEl.innerHTML = "";
    ["sidebar-user", "topbar-user"].forEach((id) => {
      const n = document.getElementById(id);
      if (n) n.innerHTML = "";
    });
    const titleEl = document.getElementById("topbar-title");
    if (titleEl) titleEl.textContent = "";

    // Ochiq modallar (boshqa foydalanuvchi ma'lumoti ko'rsatilgan bo'lishi mumkin)
    document.querySelectorAll(".modal-overlay").forEach((o) => o.remove());
    document.body.classList.remove("modal-open");

    // Login formasi tozalanadi
    const pw = document.getElementById("login-password");
    if (pw) pw.value = "";
    const otp = document.getElementById("login-otp");
    if (otp) otp.value = "";
    const otpFld = document.getElementById("fld-otp");
    if (otpFld) otpFld.classList.add("hidden");
    hideLoginAlert();
    ["login", "password", "otp"].forEach(clearFieldErr);
    resetRoleButtons();
  }

  function showLoginScreen() {
    document.getElementById("app-shell").classList.add("hidden");
    document.getElementById("login-screen").classList.remove("hidden");
  }

  /* Serverdan kelgan foydalanuvchi shu tab'ning foydalanuvchisi bilan mos
     kelishi SHART. Mos kelmasa — sessiya almashib qolgan: masalan boshqa
     qurilmada "Barcha qurilmalardan chiqish" qilingan, yoki eski token qolgan.
     Bunday holatda eski ma'lumotni KO'RSATMAYDI — tozalab, qayta kiritishga
     majbur qiladi. Aks holda bir odam boshqa odamning profilini, jadvalini va
     xabarlarini ko'ra oladi (fail-closed). */
  function applyMe(me) {
    const cur = App.me && App.me.user;
    if (cur && me && me.user && me.user.id !== cur.id) {
      clearSessionState();
      showLoginScreen();
      toast(t("session.switched"), "error");
      return false;
    }
    App.me = me;
    return true;
  }

  /* Server sessiyasini ham yakunlaydi. Serverga yetib bormasa ham lokal
     holat (va ko'rinish) tozalanadi — aks holda ekranda eski foydalanuvchi
     ma'lumoti qolib ketardi. */
  App.logout = async function (opts) {
    opts = opts || {};
    if (loggingOut) return;
    loggingOut = true;
    App.me = null; // parallel 401 handlerlar qayta chaqirmasin
    let serverOk = true;
    try {
      await API.post("auth/logout");
    } catch (e) {
      serverOk = false;
    }
    try {
      clearSessionState();
      showLoginScreen();
      if (!serverOk) toast(t("logout.server_error"), "error");
      else if (!opts.silent) toast(t("logout.done"));
    } finally {
      loggingOut = false;
    }
  };

  App.confirmLogout = function () {
    if (loggingOut) return;
    UI.confirmDialog(t("logout.confirm_text"), () => App.logout(), {
      danger: true,
      title: "🚪 " + t("logout.confirm_title"),
      yesText: "🚪 " + t("logout.confirm_yes"),
      noText: t("common.cancel"),
    });
  };

  /* ---------------- shell ---------------- */
  function buildSidebar() {
    const navEl = document.getElementById("sidebar-nav");
    navEl.innerHTML = "";
    const role = App.me.user.role;
    const items = navFor(role);
    App.roleNav = items;
    items.forEach(([view, icon, label]) => {
      const btn = el("button", {
        class: "nav-item", dataset: { view },
        onclick: () => { App.go(view); closeSidebar(); },
      }, [el("span", { class: "nav-icon", icon, "aria-hidden": "true" }), el("span", { text: label })]);
      navEl.append(btn);
    });
    markNav();
    updateNotifBadge();
    fillSidebarUser(App.me.user);
  }

  /* Sidebar pastidagi foydalanuvchi kartasi + tezkor "Chiqish" tugmasi.
     Barcha rollar uchun bir xil ko'rinishda. */
  function fillSidebarUser(user) {
    const su = document.getElementById("sidebar-user");
    if (!su) return;
    su.innerHTML = "";
    su.append(
      avatar(user, 38),
      el("div", { class: "sidebar-user-info" }, [
        el("div", { class: "cell-strong", text: `${user.first_name} ${user.last_name}` }),
        el("div", { class: "muted", style: "font-size:12px", text: roleLabel(user.role) }),
      ]),
      el("button", {
        class: "sidebar-logout", icon: "logout",
        title: t("logout.sidebar"), "aria-label": t("logout.sidebar"),
        onclick: () => App.confirmLogout(),
      }),
    );
  }

  function roleLabel(role) {
    return role === "student" ? t("auth.role_student") : role === "instructor" ? t("auth.role_instructor") : t("auth.role_admin");
  }

  function buildTopbar() {
    const user = App.me.user;
    const tu = document.getElementById("topbar-user");
    tu.innerHTML = "";
    tu.append(el("div", {}, [
      el("div", { class: "cell-strong", text: `${user.first_name} ${user.last_name}` }),
      el("div", { class: "muted", style: "font-size:12px", text: user.login }),
    ]));
    // Sidebar kartasi buildSidebar() tomonidan to'ldiriladi (u rolda ham
    // "Chiqish" tugmasi bor) — bu yerda qayta yozish eski variantni
    // ustiga yozib tugmani yo'q qilardi.
  }

  function markNav() {
    document.querySelectorAll(".nav-item").forEach((b) => {
      b.classList.toggle("active", b.dataset.view === App.view);
    });
  }

  function closeSidebar() {
    document.getElementById("sidebar").classList.remove("open");
  }

  document.getElementById("burger").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });

  /* ---------------- router ---------------- */
  const VF = {
    admin: window.AdminViews,
    instructor: window.InstructorViews,
    student: window.StudentViews,
  };

  App.go = function (view, params) {
    // Route guard: autentifikatsiya yo'q bo'lsa hech qanday himoyalangan
    // bo'limga o'tilmaydi.
    if (!App.me || !App.me.user) { showLoginScreen(); return; }
    /* BAND 4: o'chirilgan sahifalar (masalan talaba "schedule") avtomatik
       "Amaliy mashg'ulotlarim" ga yo'naltiriladi. */
    App.view = resolveRoute(App.me.user.role, view);
    App.params = params || {};
    render();
  };

  App.refreshView = function () {
    render();
  };

  App.refreshMe = async function () {
    try { applyMe(await API.get("auth/me")); } catch (e) {}
    updateNotifBadge();
  };

  async function render() {
    const viewEl = document.getElementById("view");
    // Muhim: avval `App.me` null bo'lsa role "admin" ga tushib qolardi —
    // ya'ni chiqib ketgan foydalanuvchi admin dashboard'ini ko'ra olardi.
    if (!App.me || !App.me.user) { showLoginScreen(); return; }
    const role = App.me.user.role;
    /* BAND 4: o'chirilgan/ko'chirilgan sahifalar avtomatik tuzatiladi
       ("student/schedule" -> "student/lessons"). Frontend Tanlash ham
       backend'dagi ro'l majburiyligiga mos keladi. */
    const wanted = resolveRoute(role, App.view);
    if (wanted !== App.view) {
      App.view = wanted;
      location.hash = "#/" + role + "/" + wanted;
    }
    const views = VF[role];
    const fn = views[App.view] || views.dashboard;
    viewEl.innerHTML = "";
    viewEl.append(UI.spinner());
    updateTitle();
    try {
      const node = await fn(App.params);
      // Kutish paytida chiqib ketilgan bo'lsa, natija ekrana chiqmasin
      if (!App.me || !App.me.user) return;
      viewEl.innerHTML = "";
      viewEl.append(node);
    } catch (e) {
      if (!App.me || !App.me.user) return;
      viewEl.innerHTML = "";
      viewEl.append(UI.emptyState("⚠️", I18N.errorText(e && e.code), String(e && e.message || "")));
    }
    markNav();
  }

  function updateTitle() {
    if (!App.me || !App.me.user) return;
    const role = App.me.user.role;
    const items = navFor(role);
    const item = items.find(([v]) => v === App.view);
    const elT = document.getElementById("topbar-title");
    elT.textContent = item ? item[2] : items[0][2];
  }

  /* ---------------- bildirishnomalar (sidebar bo'limi + badge) ---------------- */
  function updateNotifBadge() {
    const n = App.me && App.me.unread ? App.me.unread : 0;
    document.getElementById("sidebar-nav").querySelectorAll(".nav-item[data-view=notifications] .nav-badge").forEach((b) => b.remove());
    if (!n) return;
    const navBtn = document.getElementById("sidebar-nav").querySelector('.nav-item[data-view="notifications"]');
    if (navBtn) navBtn.append(el("span", { class: "nav-badge", text: n > 99 ? "99+" : String(n) }));
  }

  // API 401 qaytarsa (sessiya serverda bekor qilingan yoki muddati o'tgan)
  // foydalanuvchi darhol login sahifasiga qaytariladi.
  API.on("logout", () => { if (App.me) App.logout({ silent: true }); });

  /* Sahifa har qayta ko'rsatilganda (F5, orqaga qaytish/bfcache) autentifikatsiya
     qayta tekshiriladi — serverda sessiya o'chirilgan bo'lsa, himoyalangan
     bo'limlar qayta ochilmaydi. */
  async function guardAuth() {
    if (!App.me) { showLoginScreen(); return; }
    try {
      // applyMe: server boshqa foydalanuvchini qaytarsa — eski ma'lumotni
      // ko'rsatmaydi, qayta kiritishga majbur qiladi.
      if (applyMe(await API.get("auth/me"))) updateNotifBadge();
    } catch (e) {
      App.logout({ silent: true });
    }
  }
  addEventListener("pageshow", () => { guardAuth(); });
  addEventListener("focus", () => { guardAuth(); });

  /* ---------------- boshlash ---------------- */
  async function boot() {
    // M12: tema (yorug'/tungi) — localStorage va prefers-color-scheme asosida
    Shared.applyTheme();

    document.querySelectorAll("[data-lang]").forEach((b) => {
      b.addEventListener("click", () => {
        setLang(b.dataset.lang);
        applyLangUI();
        if (App.me) { buildSidebar(); updateTitle(); App.refreshView(); }
      });
    });

    // Tilda almashganda navlarni yangilash.
    // Muhim: joriy view ham qayta render bo'lishi kerak, aks holda bo'lim ichidagi
    // dinamik kontent (status matnlari, jadval sarlavhalari, tugmalar) eski tilda qoladi.
    // Modal ochiq bo'lsa — formadagi kiritilgan ma'lumot yo'qolmasin deb view'ni
    // qayta qurmaymiz (modal yopilgach keyingi o'tishda yangi til chiqadi).
    document.addEventListener("langchange", () => {
      if (!App.me) return;
      buildSidebar(); updateTitle();
      const modalOpen = document.querySelector(".modal-overlay:not(.hidden)");
      if (!modalOpen) App.refreshView();
    });

    // Avval login UI ni tayyorlaymiz
    initLogin();
    document.getElementById("app-shell").classList.add("hidden");

    // Session bo'lsa kirish
    try {
      const me = await API.get("auth/me");
      App.me = me;
      document.getElementById("login-screen").classList.add("hidden");
      document.getElementById("app-shell").classList.remove("hidden");
      buildSidebar(); buildTopbar();
      App.go("dashboard");
      if (me.user.must_change_password) {
        Shared.openChangePassword(false);
      }
    } catch (e) {
      // Sessiya yo'q (yoki bekor qilingan) — login sahifasida qolamiz.
      // Himoyalangan bo'limlarga kirish taqiqlanadi (render() guard).
      App.me = null;
      showLoginScreen();
    }
    updateNotifBadge();
    setInterval(async () => { if (App.me) await App.refreshMe(); }, 60000);
  }

  document.addEventListener("DOMContentLoaded", boot);
})();