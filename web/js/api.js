/* API klienti: cookie-sessiya, tab-ga xos kalit, CSRF himoyasi, xatolarni tahlil qilish */
const API = (function () {
  /* Tab'ga xos kalit.
     Muammo: sessiya bitta `sid` cookie'siga bog'langan edi. Cookie esa bir
     brauzer bo'ylab umumiy — ikki tab' bir xil qiymatni ko'radi. Shuning uchun
     bir brauzerda ikki odam (masalan instruktor va talaba) kirsa, ikkinchisi
     birinchisining sessiyasini almashtirib yuborardi va birinchi oyna boshqa
     odamning ma'lumotini ko'ra boshlardi.

     Yechim: kalit ikki qismdan yig'iladi —
       * qurilma kaliti: HttpOnly cookie (JS uni ko'ra olmaydi),
       * tab kaliti: shu quyidagi `X-Avto-Tab` sarlavhasi (sessionStorage,
         faqat shu tab'ga xos).
     Serverda ularning kombinatsiyasi saqlanadi, shuning uchun bu kalitning
     o'zi credential hisoblanmaydi va uni alohida o'girmish hech naga
     imkon bermaydi. */
  const TAB_KEY = "avto_tab";
  function tabId() {
    let id = null;
    try { id = sessionStorage.getItem(TAB_KEY); } catch (e) { /* bloklangan bo'lishi mumkin */ }
    if (id) return id;
    const c = (typeof crypto !== "undefined" && crypto) ? crypto : null;
    if (c && c.randomUUID) {
      id = c.randomUUID();
    } else if (c && c.getRandomValues) {
      const buf = new Uint8Array(16);
      c.getRandomValues(buf);
      id = Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
    } else {
      // Juda eski brauzerlar uchun (crypto yo'q) — baribir har bir tab'ga
      // alohida bo'ladi, chunki bu qiymat faqat indeks.
      id = "t" + Date.now().toString(36) + Math.random().toString(36).slice(2, 14);
    }
    try { sessionStorage.setItem(TAB_KEY, id); } catch (e) {}
    return id;
  }

  /* ------------------------------------------------------------------ CSRF
     BAND 6: CSRF token `sid` cookie'sida EMAS (u HttpOnly, JS ko'ra olmaydi).
     Server tokeni javob tanasida qaytaradi (`auth/login` va `GET /api/auth/me`),
     frontend uni `sessionStorage` da saqlaydi va har bir o'zgartiruvchi
     so'rovda `X-CSRF-Token` sarlavhasi orqali yuboradi.

     Nima uchun shunday:
       * `<form>` yoki `<img>` orqali so'rov yuborish mumkin emas
         (`X-Requested-With` qo'shilmaydi) — 1-qatlam;
       * token sessiyaga bog'langan — boshqa sayt/sessiya uchun ishlamaydi
         (`hmac.compare_digest` bilan solishtiriladi) — 2-qatlam.

     Token `sessionStorage` da: brauzer yopilsa yo'qoladi, lekin shunda
     sessiya ham (`session cookie`) yo'qoladi — "eslab qolish" bilan
     kirilganda login javobidan yangi token olinadi. */
  const CSRF_KEY = "avto_csrf";
  function csrfToken() {
    try { return sessionStorage.getItem(CSRF_KEY) || ""; } catch (e) { return ""; }
  }
  function setCsrfToken(v) {
    if (!v) return;
    try { sessionStorage.setItem(CSRF_KEY, v); } catch (e) { /* bloklangan */ }
  }
  function clearCsrfToken() {
    try { sessionStorage.removeItem(CSRF_KEY); } catch (e) { /* bloklangan */ }
  }

  async function req(method, url, body) {
    const opts = { method, credentials: "same-origin", headers: { "X-Avto-Tab": tabId() } };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    if (method !== "GET") {
      opts.headers["X-Requested-With"] = "Avtomaktab";
      const tok = csrfToken();
      if (tok) opts.headers["X-CSRF-Token"] = tok;
    }
    const res = await fetch("/api/" + url, opts);
    const ct = res.headers.get("Content-Type") || "";
    if (ct.includes("application/json")) {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (res.status === 401) {
          /* Sessiya tugagan — token ham ma'nosiz. */
          clearCsrfToken();
          emit("logout");
        }
        const e = new Error(data.error || "err.generic");
        e.code = data.error;
        e.params = data.params || {};
        throw e;
      }
      /* Server yangilangan CSRF token yuborsa — darhol qabul qilamiz
         (sessiya yangilansa eskirgan token bilan so'rov yubormaslik). */
      if (data && data.csrf) setCsrfToken(data.csrf);
      return data;
    }
    if (!res.ok) {
      throw new Error("err.server_error");
    }
    return await res.blob();
  }

  const listeners = {};
  function on(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); }
  function emit(ev, payload) { (listeners[ev] || []).forEach((fn) => fn(payload)); }

  return {
    get: (url) => req("GET", url),
    post: (url, body = {}) => req("POST", url, body),
    put: (url, body = {}) => req("PUT", url, body),
    del: (url) => req("DELETE", url),
    /* CSRF token — login va `GET /api/auth/me` javobida server beradi */
    setCsrf: setCsrfToken, csrf: csrfToken, clearCsrf: clearCsrfToken,
    on, emit,
  };
})();