const authPanel = document.querySelector("#auth-panel");
const memberPanel = document.querySelector("#member-panel");
const authStatus = document.querySelector("#auth-status");
const profileStatus = document.querySelector("#profile-status");

function profileEsc(value = "") {
  return String(value).replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);
}

function profileSafeUrl(value = "") {
  try { const url = new URL(value); return ["http:","https:"].includes(url.protocol) ? url.href : "#"; } catch { return "#"; }
}

function setAuthStatus(message, error = false) {
  authStatus.textContent = message; authStatus.classList.toggle("error", error);
}

document.querySelectorAll("[data-auth-tab]").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll("[data-auth-tab]").forEach(item => item.classList.toggle("active", item === button));
  document.querySelector("#login-form").hidden = button.dataset.authTab !== "login";
  document.querySelector("#register-form").hidden = button.dataset.authTab !== "register";
  setAuthStatus("");
}));

async function submitAuth(form, endpoint) {
  setAuthStatus("Arbetar…");
  try {
    await window.ljusglimtAuth.request(endpoint, {method:"POST", body:JSON.stringify(Object.fromEntries(new FormData(form)))});
    await window.ljusglimtAuth.refresh();
    const next = new URLSearchParams(location.search).get("next");
    if (next && next.startsWith("/") && !next.startsWith("//")) { location.href = next; return; }
    await renderProfile();
  } catch (error) { setAuthStatus(error.message, true); }
}

document.querySelector("#login-form").addEventListener("submit", event => { event.preventDefault(); submitAuth(event.target, "/api/auth/login"); });
document.querySelector("#register-form").addEventListener("submit", event => { event.preventDefault(); submitAuth(event.target, "/api/auth/register"); });

function savedMarkup(article) {
  return `<article class="saved-card"><div><span class="eyebrow">${profileEsc(article.source || "Källa")}</span><h3>${profileEsc(article.title)}</h3><p>${profileEsc(article.summary || "")}</p>
    <div class="saved-actions"><a href="${profileSafeUrl(article.url)}" target="_blank" rel="noopener noreferrer">Läs originalet →</a><button type="button" data-remove-saved="${profileEsc(article.article_id)}">Ta bort</button></div></div></article>`;
}

async function loadSaved() {
  const root = document.querySelector("#saved-list");
  try {
    const data = await window.ljusglimtAuth.request("/api/saved", {method:"GET"});
    document.querySelector("#saved-count").textContent = `${data.articles.length} sparade`;
    root.innerHTML = data.articles.length ? data.articles.map(savedMarkup).join("") : `<div class="empty-saved"><span>♡</span><h3>Din läslista är tom</h3><p>Tryck på Spara vid en nyhet så hamnar den här.</p><a class="button button-primary" href="/">Hitta nyheter</a></div>`;
  } catch (error) { root.innerHTML = `<p>${profileEsc(error.message)}</p>`; }
}

document.querySelector("#saved-list").addEventListener("click", async event => {
  const button = event.target.closest("[data-remove-saved]"); if (!button) return;
  try { await window.ljusglimtAuth.request(`/api/saved/${encodeURIComponent(button.dataset.removeSaved)}`, {method:"DELETE"}); await loadSaved(); }
  catch (error) { profileStatus.textContent = error.message; }
});

async function renderProfile() {
  const user = window.ljusglimtAuth.state.user;
  authPanel.hidden = Boolean(user); memberPanel.hidden = !user;
  if (!user) return;
  document.querySelector("#profile-title").textContent = `Hej ${user.name}`;
  document.querySelector("#profile-lead").textContent = "Här hittar du din profil, dina sparade nyheter och vägen till samtalet.";
  document.querySelector("#profile-name").textContent = user.name;
  document.querySelector("#profile-email").textContent = user.email;
  document.querySelector("#profile-form [name=name]").value = user.name;
  document.querySelector("#profile-avatar").textContent = user.name.slice(0,1).toLocaleUpperCase("sv");
  await loadSaved();
}

document.querySelector("#profile-form").addEventListener("submit", async event => {
  event.preventDefault(); profileStatus.textContent = "Sparar…";
  try {
    const data = await window.ljusglimtAuth.request("/api/profile", {method:"POST", body:JSON.stringify(Object.fromEntries(new FormData(event.target)))});
    window.ljusglimtAuth.state.user = data.user; await window.ljusglimtAuth.refresh(); profileStatus.textContent = "Profilen är sparad."; await renderProfile();
  } catch (error) { profileStatus.textContent = error.message; }
});

document.querySelector("#logout-button").addEventListener("click", async () => {
  await window.ljusglimtAuth.request("/api/auth/logout", {method:"POST", body:"{}"});
  await window.ljusglimtAuth.refresh(); window.location.href = "/";
});

async function setupGoogle() {
  const config = await window.ljusglimtAuth.request("/api/config", {method:"GET"});
  const note = document.querySelector("#google-note");
  if (!config.googleEnabled) {
    note.textContent = "Google-inloggning är förberedd och aktiveras när webbplatsens Google Client ID läggs in.";
    return;
  }
  const script = document.createElement("script"); script.src = "https://accounts.google.com/gsi/client"; script.async = true;
  script.onload = () => {
    google.accounts.id.initialize({client_id:config.googleClientId, callback:async response => {
      try { await window.ljusglimtAuth.request("/api/auth/google", {method:"POST",body:JSON.stringify({credential:response.credential})}); await window.ljusglimtAuth.refresh(); const next=new URLSearchParams(location.search).get("next"); if(next&&next.startsWith("/")&&!next.startsWith("//")){location.href=next;return;} await renderProfile(); }
      catch (error) { setAuthStatus(error.message, true); }
    }});
    google.accounts.id.renderButton(document.querySelector("#google-signin"), {theme:"outline",size:"large",shape:"pill",text:"continue_with",locale:"sv",width:300});
  };
  document.head.appendChild(script);
}

window.ljusglimtAuth.ready.then(() => { renderProfile(); setupGoogle(); });
