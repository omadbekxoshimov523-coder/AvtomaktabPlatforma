/* API klienti: cookie-sessiya, CSRF himoyasi, xatolarni tahlil qilish */
const API = (function () {
  async function req(method, url, body) {
    const opts = { method, credentials: "same-origin", headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    if (method !== "GET") {
      opts.headers["X-Requested-With"] = "Avtomaktab";
    }
    const res = await fetch("/api/" + url, opts);
    const ct = res.headers.get("Content-Type") || "";
    if (ct.includes("application/json")) {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (res.status === 401) {
          emit("logout");
        }
        const e = new Error(data.error || "err.generic");
        e.code = data.error;
        e.params = data.params || {};
        throw e;
      }
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
    on, emit,
  };
})();