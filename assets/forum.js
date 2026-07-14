const topicsRoot = document.querySelector("#forum-topics");
const topicForm = document.querySelector("#topic-form");
const statusNode = document.querySelector("#forum-status");

function esc(value = "") {
  return String(value).replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);
}

function displayDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "Nyligen" : new Intl.DateTimeFormat("sv-SE", {day:"numeric", month:"short"}).format(date);
}

function topicMarkup(topic) {
  const replies = (topic.replies || []).map(reply => `<div class="reply"><strong>${esc(reply.author)}</strong><p>${esc(reply.body)}</p></div>`).join("");
  return `<article class="topic-card"><div class="topic-meta"><span>${esc(topic.category)}</span><span>${displayDate(topic.createdAt)}</span></div>
    <h3>${esc(topic.title)}</h3><p>${esc(topic.body)}</p><small>Startad av ${esc(topic.author)} · ${(topic.replies || []).length} svar</small>
    <details><summary>Visa samtal och svara</summary>${replies || "<p>Inga publicerade svar ännu.</p>"}
      <form class="reply-form stack-form" data-topic="${esc(topic.id)}"><label>Namn <input name="author" maxlength="40"></label>
      <label>Ditt svar <textarea name="body" required minlength="10" maxlength="1600" rows="3"></textarea></label>
      <input class="honeypot" name="website" tabindex="-1" autocomplete="off"><button class="button button-outline" type="submit">Skicka svar</button><p class="form-status" role="status"></p></form>
    </details></article>`;
}

async function loadTopics() {
  try {
    const response = await fetch("/api/forum/topics");
    const data = await response.json();
    topicsRoot.innerHTML = data.topics?.length ? data.topics.map(topicMarkup).join("") : "<p>Inga publicerade samtal ännu.</p>";
  } catch {
    topicsRoot.innerHTML = "<p>Forumet behöver köras via <code>python server.py</code>.</p>";
  }
}

async function send(url, payload, status) {
  status.textContent = "Skickar…";
  try {
    const response = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
    const result = await response.json();
    status.textContent = result.message || result.error || "Klart.";
    return response.ok;
  } catch { status.textContent = "Kunde inte nå servern."; return false; }
}

topicForm.addEventListener("submit", async event => {
  event.preventDefault(); const payload = Object.fromEntries(new FormData(topicForm));
  if (await send("/api/forum/topics", payload, statusNode)) topicForm.reset();
});

topicsRoot.addEventListener("submit", async event => {
  if (!event.target.matches(".reply-form")) return;
  event.preventDefault(); const form = event.target;
  const payload = {...Object.fromEntries(new FormData(form)), topicId: form.dataset.topic};
  if (await send("/api/forum/replies", payload, form.querySelector(".form-status"))) form.reset();
});

loadTopics();
