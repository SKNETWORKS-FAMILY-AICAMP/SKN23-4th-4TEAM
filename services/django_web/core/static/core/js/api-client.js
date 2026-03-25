(function setupApiClient(global) {
  const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

  function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const rawCookie of cookies) {
      const cookie = rawCookie.trim();
      if (cookie.startsWith(name + "=")) {
        return decodeURIComponent(cookie.slice(name.length + 1));
      }
    }
    return "";
  }

  function getCsrfToken() {
    const meta = document.querySelector("meta[name='csrf-token']");
    if (meta) {
      const value = meta.getAttribute("content") || "";
      if (value && value !== "NOTPROVIDED") {
        return value;
      }
    }
    return getCookie("csrftoken");
  }

  function normalizeError(status, payload) {
    if (payload && typeof payload === "object" && typeof payload.error === "string") {
      return { status, code: "api_error", message: payload.error };
    }
    if (status === 403) {
      return { status, code: "forbidden", message: "권한이 없거나 요청 토큰이 유효하지 않습니다." };
    }
    if (status >= 500) {
      return { status, code: "server_error", message: "서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요." };
    }
    return { status, code: "request_error", message: "요청 처리 중 오류가 발생했습니다." };
  }

  async function request(url, options) {
    const opts = options || {};
    const method = (opts.method || "GET").toUpperCase();
    const headers = new Headers(opts.headers || {});
    const timeoutMs = Number(opts.timeoutMs || 9000);

    if (!headers.has("Accept")) {
      headers.set("Accept", "application/json");
    }

    const fetchOptions = {
      method,
      headers,
      credentials: "same-origin",
    };

    if (opts.body !== undefined) {
      if (!headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      fetchOptions.body = typeof opts.body === "string" ? opts.body : JSON.stringify(opts.body);
    }

    if (!SAFE_METHODS.has(method)) {
      const csrfToken = getCsrfToken();
      if (csrfToken) {
        headers.set("X-CSRFToken", csrfToken);
      }
    }

    const controller = new AbortController();
    const timer = setTimeout(function onTimeout() {
      controller.abort();
    }, timeoutMs);

    fetchOptions.signal = controller.signal;

    try {
      const response = await fetch(url, fetchOptions);
      const contentType = response.headers.get("Content-Type") || "";
      let payload = null;

      if (contentType.includes("application/json")) {
        payload = await response.json();
      } else {
        const textPayload = await response.text();
        payload = { text: textPayload };
      }

      if (!response.ok) {
        throw normalizeError(response.status, payload);
      }

      return payload;
    } catch (err) {
      if (err && err.name === "AbortError") {
        throw { status: 408, code: "timeout", message: "요청 시간이 초과되었습니다." };
      }

      if (err && typeof err === "object" && "code" in err) {
        throw err;
      }

      throw { status: 0, code: "network", message: "네트워크 연결을 확인해주세요." };
    } finally {
      clearTimeout(timer);
    }
  }

  global.apiClient = { request: request, getCookie: getCookie, getCsrfToken: getCsrfToken };
})(window);
