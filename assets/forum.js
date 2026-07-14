const forumRoot = document.querySelector("#forum-app");
const route = new URLSearchParams(location.search);
let currentSection = null;
let sectionTopics = [];

function esc(value = "") {
  return String(value).replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);
}

function formatDate(value, withTime = false) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Nyligen";
  return new Intl.DateTimeFormat("sv-SE", withTime
    ? {day:"numeric", month:"short", year:"numeric", hour:"2-digit", minute:"2-digit"}
    : {day:"numeric", month:"short", year:"numeric"}).format(date);
}

function initials(name = "L") {
  return name.split(/\s+/).slice(0, 2).map(part => part[0]).join("").toLocaleUpperCase("sv");
}

function avatar(name, url, large = false) {
  const size = large ? " large" : "";
  return url
    ? `<img class="member-avatar${size}" src="${esc(url)}" alt="">`
    : `<span class="member-avatar fallback${size}">${esc(initials(name))}</span>`;
}

function breadcrumbs(items) {
  return `<nav class="forum-breadcrumbs" aria-label="Brödsmulor"><a href="/forum">Forum</a>${items.map(item =>
    `<span aria-hidden="true">›</span>${item.href ? `<a href="${esc(item.href)}">${esc(item.label)}</a>` : `<strong>${esc(item.label)}</strong>`}`
  ).join("")}</nav>`;
}

function forumError(message) {
  forumRoot.innerHTML = `<div class="forum-empty"><span>☁</span><h2>Något gick snett</h2><p>${esc(message)}</p><a class="button button-primary" href="/forum">Till forumstarten</a></div>`;
}

function latestMarkup(item) {
  return `<li><a href="/forum?topic=${encodeURIComponent(item.id)}"><strong>${esc(item.title)}</strong><span>${esc(item.sectionTitle)} · ${esc(item.author)} · ${formatDate(item.createdAt, true)}</span></a></li>`;
}

function renderIndex(data) {
  const groups = (data.groups || []).map(group => `<section class="forum-group">
    <header class="forum-group-header"><div><h2>${esc(group.title)}</h2><p>${esc(group.description)}</p></div><span>${group.sections.length} avdelningar</span></header>
    <div class="forum-section-table">
      ${(group.sections || []).map(section => `<article class="forum-section-row">
        <a class="forum-section-main" href="/forum?section=${encodeURIComponent(section.id)}">
          <span class="forum-section-icon" aria-hidden="true">${esc(section.icon)}</span>
          <span><strong>${esc(section.title)}</strong><small>${esc(section.description)}</small></span>
        </a>
        <div class="forum-section-counts" aria-label="Forumstatistik"><span><strong>${section.topicCount}</strong> trådar</span><span><strong>${section.postCount}</strong> inlägg</span></div>
        <div class="forum-section-latest">${section.latest
          ? `<a href="/forum?topic=${encodeURIComponent(section.latest.id)}"><strong>${esc(section.latest.title)}</strong><span>${esc(section.latest.author)} · ${formatDate(section.latest.createdAt, true)}</span></a>`
          : `<span class="forum-no-posts">Bli först att skriva</span>`}</div>
      </article>`).join("")}
    </div>
  </section>`).join("");
  forumRoot.innerHTML = `<div class="forum-index-layout"><div>${groups}</div><aside class="forum-side-stack">
    <section class="forum-side-card"><span class="eyebrow">Senaste aktivitet</span><h2>Nytt i forumet</h2><ul class="forum-latest-list">${(data.latest || []).length ? data.latest.map(latestMarkup).join("") : "<li>Inga publicerade trådar ännu.</li>"}</ul></section>
    <section class="forum-side-card forum-stats-card"><span class="eyebrow">Gemenskapen</span><div><strong>${data.stats?.topics || 0}</strong><span>trådar</span></div><div><strong>${data.stats?.posts || 0}</strong><span>inlägg</span></div><div><strong>${data.stats?.members || 0}</strong><span>medlemmar</span></div></section>
    <section class="forum-side-card forum-rules"><h2>Forumregler</h2><ol><li>Var vänlig och saklig.</li><li>Skydda personuppgifter.</li><li>Länka källan vid faktapåståenden.</li></ol><p>Använd Rapportera om något behöver granskas.</p></section>
  </aside></div>`;
}

function topicRow(topic) {
  const flags = `${topic.pinned ? '<span class="topic-flag">Fäst</span>' : ""}${topic.locked ? '<span class="topic-flag muted">Låst</span>' : ""}${topic.status !== "published" ? '<span class="pending-badge">Väntar på granskning</span>' : ""}`;
  return `<article class="forum-topic-row" data-search-text="${esc(`${topic.title} ${topic.author} ${topic.body}`.toLocaleLowerCase("sv"))}">
    <a class="forum-topic-main" href="/forum?topic=${encodeURIComponent(topic.id)}">
      ${avatar(topic.author, topic.avatarUrl)}
      <span><strong>${esc(topic.title)} ${flags}</strong><small>Startad av ${esc(topic.author)} · ${formatDate(topic.createdAt, true)}</small></span>
    </a>
    <div class="forum-topic-counts"><span><strong>${topic.replyCount}</strong> svar</span><span><strong>${topic.views}</strong> visningar</span></div>
    <div class="forum-topic-last"><strong>Senaste aktivitet</strong><span>${formatDate(topic.lastActivity, true)}</span></div>
  </article>`;
}

function newTopicPanel(section) {
  const user = window.ljusglimtAuth.state.user;
  if (!user) return `<div class="forum-compose-login"><strong>Vill du starta en tråd?</strong><span>Logga in eller skapa ett gratis konto först.</span><a class="button button-primary" href="/profil?next=${encodeURIComponent(`/forum?section=${section.id}`)}">Logga in</a></div>`;
  return `<details class="forum-compose" id="new-topic"><summary class="button button-primary">+ Ny tråd</summary>
    <form id="topic-form" class="stack-form">
      <div class="compose-heading"><span class="forum-section-icon">${esc(section.icon)}</span><div><strong>Ny tråd i ${esc(section.title)}</strong><small>Du skriver som ${esc(user.name)}</small></div></div>
      <input type="hidden" name="sectionId" value="${esc(section.id)}">
      <label>Rubrik <input name="title" required minlength="5" maxlength="100" placeholder="En tydlig rubrik"></label>
      <label>Inlägg <textarea name="body" required minlength="10" maxlength="2000" rows="7" placeholder="Berätta konkret och respektfullt. Lägg gärna till en källa."></textarea></label>
      <label class="honeypot" aria-hidden="true">Webbplats <input name="website" tabindex="-1" autocomplete="off"></label>
      <div class="compose-actions"><button class="button button-primary" type="submit">Skicka till moderering</button><span class="form-status" role="status"></span></div>
    </form></details>`;
}

function renderSection(data) {
  currentSection = data.section;
  sectionTopics = data.topics || [];
  document.title = `${data.section.title} – Ljusglimt Forum`;
  forumRoot.innerHTML = `${breadcrumbs([{label:data.section.groupTitle}, {label:data.section.title}])}
    <header class="forum-section-heading"><div class="forum-section-title"><span class="forum-section-icon large">${esc(data.section.icon)}</span><div><span class="eyebrow">${esc(data.section.groupTitle)}</span><h2>${esc(data.section.title)}</h2><p>${esc(data.section.description)}</p></div></div>${newTopicPanel(data.section)}</header>
    <div class="forum-toolbar"><label><span class="sr-only">Sök i avdelningen</span><input id="forum-topic-search" type="search" placeholder="Sök bland trådarna…"></label><span>${sectionTopics.length} trådar</span></div>
    <section id="section-topic-list" class="forum-topic-list" aria-label="Trådar">${sectionTopics.length ? sectionTopics.map(topicRow).join("") : `<div class="forum-empty"><span>${esc(data.section.icon)}</span><h2>Här är det lugnt än så länge</h2><p>Starta den första tråden i avdelningen.</p></div>`}</section>`;
}

function roleLabel(role) {
  return role === "admin" ? "Administratör" : role === "moderator" ? "Moderator" : "Medlem";
}

function postMarkup(post, index, topic) {
  const isOpening = index === 0;
  const author = post.author || {};
  return `<article class="forum-post${post.status !== "published" ? " pending" : ""}" id="post-${index}">
    <aside class="forum-post-author">${avatar(author.name, author.avatarUrl, true)}<strong>${esc(author.name)}</strong><span>${roleLabel(author.role)}</span>${author.memberSince ? `<small>Medlem sedan ${formatDate(author.memberSince)}</small>` : ""}</aside>
    <div class="forum-post-content"><header><span>${isOpening ? "Trådstart" : `Svar #${index}`}</span><time datetime="${esc(post.createdAt)}">${formatDate(post.createdAt, true)}</time></header>
      ${post.status !== "published" ? '<div class="pending-notice">Det här inlägget syns bara för dig tills det har granskats.</div>' : ""}
      ${isOpening ? `<h1>${esc(topic.title)}</h1>` : ""}<p>${esc(post.body)}</p>
    </div>
  </article>`;
}

function replyPanel(topic) {
  if (topic.locked) return `<div class="forum-locked">🔒 Tråden är låst för nya svar.</div>`;
  const user = window.ljusglimtAuth.state.user;
  if (!user) return `<div class="forum-compose-login"><strong>Delta i samtalet</strong><span>Logga in för att skriva ett svar eller följa tråden.</span><a class="button button-primary" href="/profil?next=${encodeURIComponent(`/forum?topic=${topic.id}`)}">Logga in</a></div>`;
  return `<form id="reply-form" class="forum-reply-editor stack-form"><label>Svara som ${esc(user.name)}<textarea name="body" required minlength="10" maxlength="1600" rows="6" placeholder="Skriv ett vänligt och konstruktivt svar."></textarea></label><input type="hidden" name="topicId" value="${esc(topic.id)}"><div class="compose-actions"><button class="button button-primary" type="submit">Skicka till moderering</button><span class="form-status" role="status"></span></div></form>`;
}

function renderTopic(data) {
  const {topic, section} = data;
  document.title = `${topic.title} – Ljusglimt Forum`;
  const opening = {body:topic.body, createdAt:topic.createdAt, status:topic.status, author:topic.author};
  const posts = [opening, ...(topic.replies || [])];
  const user = window.ljusglimtAuth.state.user;
  forumRoot.innerHTML = `${breadcrumbs([{label:section.groupTitle}, {label:section.title, href:`/forum?section=${encodeURIComponent(section.id)}`}, {label:topic.title}])}
    <header class="forum-thread-heading"><div><span class="eyebrow">${esc(section.title)}</span><h2>${esc(topic.title)}</h2><p>${posts.length} inlägg · ${topic.views} visningar</p></div><div class="thread-buttons">${user && topic.status === "published" ? `<button class="button button-outline" id="follow-topic" data-followed="${topic.followed}">${topic.followed ? "✓ Följer" : "+ Följ tråden"}</button><button class="text-button" id="report-topic">Rapportera</button>` : ""}</div></header>
    <section class="forum-post-list">${posts.map((post, index) => postMarkup(post, index, topic)).join("")}</section>
    ${replyPanel(topic)}
    <div class="forum-back-row"><a href="/forum?section=${encodeURIComponent(section.id)}">← Tillbaka till ${esc(section.title)}</a></div>`;
}

async function send(url, payload, statusNode, method = "POST") {
  if (statusNode) statusNode.textContent = "Skickar…";
  try {
    const data = await window.ljusglimtAuth.request(url, {method, body: payload ? JSON.stringify(payload) : undefined});
    if (statusNode) statusNode.textContent = data.message || "Klart.";
    return data;
  } catch (error) {
    if (statusNode) statusNode.textContent = error.message;
    if (error.code === "AUTH_REQUIRED") setTimeout(() => location.href = `/profil?next=${encodeURIComponent(location.pathname + location.search)}`, 700);
    return null;
  }
}

async function loadForum() {
  try {
    const topicId = route.get("topic");
    const sectionId = route.get("section");
    if (topicId) return renderTopic(await window.ljusglimtAuth.request(`/api/forum/topic?id=${encodeURIComponent(topicId)}`, {method:"GET"}));
    if (sectionId) return renderSection(await window.ljusglimtAuth.request(`/api/forum/topics?section=${encodeURIComponent(sectionId)}`, {method:"GET"}));
    renderIndex(await window.ljusglimtAuth.request("/api/forum/index", {method:"GET"}));
  } catch (error) {
    forumError(error.message || "Forumet kunde inte laddas just nu.");
  }
}

forumRoot.addEventListener("input", event => {
  if (event.target.id !== "forum-topic-search") return;
  const term = event.target.value.trim().toLocaleLowerCase("sv");
  document.querySelectorAll(".forum-topic-row").forEach(row => { row.hidden = !row.dataset.searchText.includes(term); });
});

forumRoot.addEventListener("submit", async event => {
  if (event.target.id === "topic-form") {
    event.preventDefault();
    const form = event.target;
    const data = await send("/api/forum/topics", Object.fromEntries(new FormData(form)), form.querySelector(".form-status"));
    if (data) { form.reset(); setTimeout(loadForum, 500); }
  }
  if (event.target.id === "reply-form") {
    event.preventDefault();
    const form = event.target;
    const data = await send("/api/forum/replies", Object.fromEntries(new FormData(form)), form.querySelector(".form-status"));
    if (data) { form.reset(); setTimeout(loadForum, 500); }
  }
});

forumRoot.addEventListener("click", async event => {
  const follow = event.target.closest("#follow-topic");
  if (follow) {
    const topicId = route.get("topic");
    const followed = follow.dataset.followed === "true";
    follow.disabled = true;
    const data = followed
      ? await send(`/api/forum/follow/${encodeURIComponent(topicId)}`, null, null, "DELETE")
      : await send("/api/forum/follow", {topicId}, null);
    if (data) { follow.dataset.followed = String(data.followed); follow.textContent = data.followed ? "✓ Följer" : "+ Följ tråden"; }
    follow.disabled = false;
  }
  if (event.target.closest("#report-topic")) {
    if (!confirm("Vill du rapportera tråden till moderatorerna?")) return;
    const data = await send("/api/forum/report", {topicId:route.get("topic"), reason:"Användarrapport"}, null);
    if (data) alert(data.message);
  }
});

window.ljusglimtAuth.ready.then(loadForum);
