const topicsRoot = document.querySelector("#forum-topics");
const topicForm = document.querySelector("#topic-form");
const statusNode = document.querySelector("#forum-status");
let forumTopics = [];
let forumFilter = "Alla";

function esc(value = "") {
  return String(value).replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);
}
function displayDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "Nyligen" : new Intl.DateTimeFormat("sv-SE", {day:"numeric",month:"short"}).format(date);
}
function initials(name = "L") { return name.split(/\s+/).slice(0,2).map(part => part[0]).join("").toLocaleUpperCase("sv"); }

function avatarMarkup(name, url) {
  return url ? `<img class="member-avatar" src="${esc(url)}" alt="">` : `<span class="member-avatar fallback">${esc(initials(name))}</span>`;
}

function topicMarkup(topic) {
  const user = window.ljusglimtAuth.state.user;
  const replies = (topic.replies || []).map(reply => `<div class="reply member-row">${avatarMarkup(reply.author, reply.avatarUrl)}<div><strong>${esc(reply.author)}</strong>${reply.status !== "published" ? `<span class="pending-badge">Väntar på granskning</span>` : ""}<p>${esc(reply.body)}</p></div></div>`).join("");
  const replyBox = user ? `<form class="reply-form stack-form" data-topic="${esc(topic.id)}"><label>Ditt svar <textarea name="body" required minlength="10" maxlength="1600" rows="3"></textarea></label><button class="button button-outline" type="submit">Skicka svar</button><p class="form-status" role="status"></p></form>` : `<p class="login-prompt"><a href="/profil?next=/forum">Logga in</a> för att svara.</p>`;
  return `<article class="topic-card"><div class="topic-meta"><span>${esc(topic.category)}</span><span>${displayDate(topic.createdAt)}</span></div>
    <div class="topic-author">${avatarMarkup(topic.author, topic.avatarUrl)}<span>${esc(topic.author)}</span>${topic.status !== "published" ? `<span class="pending-badge">Din tråd väntar</span>` : ""}</div>
    <h3>${esc(topic.title)}</h3><p>${esc(topic.body)}</p><div class="topic-actions"><small>${(topic.replies || []).length} svar</small>${user && topic.status === "published" ? `<button type="button" data-report-topic="${esc(topic.id)}">Rapportera</button>` : ""}</div>
    <details><summary>Visa samtalet</summary>${replies || "<p>Inga publicerade svar ännu.</p>"}${replyBox}</details></article>`;
}

function renderTopics() {
  const visible = forumFilter === "Alla" ? forumTopics : forumTopics.filter(topic => topic.category === forumFilter);
  topicsRoot.innerHTML = visible.length ? visible.map(topicMarkup).join("") : `<div class="empty-saved"><h3>Inga samtal här ännu</h3><p>Starta gärna den första tråden i kategorin.</p></div>`;
}

async function loadTopics() {
  try { const data = await window.ljusglimtAuth.request("/api/forum/topics", {method:"GET"}); forumTopics = data.topics || []; renderTopics(); }
  catch { topicsRoot.innerHTML = "<p>Kunde inte läsa forumet just nu.</p>"; }
}

async function send(url, payload, status) {
  status.textContent = "Skickar…";
  try { const data = await window.ljusglimtAuth.request(url, {method:"POST",body:JSON.stringify(payload)}); status.textContent = data.message || "Klart."; return true; }
  catch (error) { status.textContent = error.message; if (error.code === "AUTH_REQUIRED") setTimeout(() => location.href="/profil?next=/forum",700); return false; }
}

function renderIdentity() {
  const user = window.ljusglimtAuth.state.user;
  const note = document.querySelector("#forum-identity");
  topicForm.querySelectorAll("input,select,textarea,button").forEach(control => control.disabled = !user);
  note.innerHTML = user ? `Du skriver som <strong>${esc(user.name)}</strong>.` : `<a href="/profil?next=/forum">Logga in eller skapa konto</a> för att starta en tråd.`;
}

topicForm.addEventListener("submit", async event => {
  event.preventDefault(); const payload = Object.fromEntries(new FormData(topicForm));
  if (await send("/api/forum/topics", payload, statusNode)) { topicForm.reset(); await loadTopics(); }
});

topicsRoot.addEventListener("submit", async event => {
  if (!event.target.matches(".reply-form")) return; event.preventDefault();
  const form = event.target; const payload = {...Object.fromEntries(new FormData(form)),topicId:form.dataset.topic};
  if (await send("/api/forum/replies", payload, form.querySelector(".form-status"))) { form.reset(); await loadTopics(); }
});

topicsRoot.addEventListener("click", async event => {
  const button = event.target.closest("[data-report-topic]"); if (!button) return;
  if (!confirm("Vill du rapportera tråden till moderatorerna?")) return;
  try { const data = await window.ljusglimtAuth.request("/api/forum/report", {method:"POST",body:JSON.stringify({topicId:button.dataset.reportTopic,reason:"Användarrapport"})}); alert(data.message); }
  catch (error) { alert(error.message); }
});

document.querySelectorAll("[data-forum-filter]").forEach(button => button.addEventListener("click", () => {
  forumFilter = button.dataset.forumFilter; document.querySelectorAll("[data-forum-filter]").forEach(item => item.classList.toggle("active",item===button)); renderTopics();
}));

window.ljusglimtAuth.ready.then(() => { renderIdentity(); loadTopics(); });
