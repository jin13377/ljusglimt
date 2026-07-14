const authState = { user: null };

async function authRequest(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers: {"Content-Type": "application/json", ...(options.headers || {})}
  });
  let data = {};
  try { data = await response.json(); } catch {}
  if (!response.ok) {
    const error = new Error(data.error || "Något gick fel.");
    error.code = data.code;
    error.status = response.status;
    throw error;
  }
  return data;
}

async function loadCurrentUser() {
  try {
    const data = await authRequest("/api/auth/me", {method: "GET"});
    authState.user = data.user;
  } catch { authState.user = null; }
  document.querySelectorAll("[data-auth-link]").forEach(link => {
    link.textContent = authState.user ? authState.user.name : "Logga in";
    link.classList.toggle("is-signed-in", Boolean(authState.user));
  });
  document.dispatchEvent(new CustomEvent("ljusglimt:auth", {detail: authState}));
  return authState.user;
}

const authReady = loadCurrentUser();
window.ljusglimtAuth = {state: authState, ready: authReady, request: authRequest, refresh: loadCurrentUser};
