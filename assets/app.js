const categoryImages = {
  miljo: "https://images.unsplash.com/photo-1497250681960-ef046c08a56e?auto=format&fit=crop&w=1200&q=82",
  forskning: "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?auto=format&fit=crop&w=1200&q=82",
  manniskor: "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=1200&q=82",
  kultur: "https://images.unsplash.com/photo-1521587760476-6c12a4b040da?auto=format&fit=crop&w=1200&q=82"
};

let articles = [];
let activeFilter = "alla";
let searchTerm = "";
let visibleCount = 6;
const savedIds = new Set();

const newsGrid = document.querySelector("#news-grid");
const emptyState = document.querySelector("#empty-state");
const loadMoreButton = document.querySelector("#load-more");
const dialog = document.querySelector("#article-dialog");
const dialogContent = document.querySelector("#dialog-content");
const toast = document.querySelector("#toast");

function escapeHTML(value = "") {
  return String(value).replace(/[&<>'"]/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[char]);
}

function safeUrl(value = "") {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch { return "#"; }
}

function categoryInfo(label = "Människor") {
  const text = label.toLocaleLowerCase("sv");
  if (/miljö|natur|energi|klimat|conservation|renewable/.test(text)) return ["miljo", "Miljö & natur"];
  if (/forsk|vetenskap|hälsa|rymd|discovery|health|science/.test(text)) return ["forskning", "Forskning & hälsa"];
  if (/kultur|konst|musik|museum|culture/.test(text)) return ["kultur", "Kultur"];
  return ["manniskor", "Människor"];
}

function dateLabel(value) {
  if (!value) return "Nyligen";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "Nyligen" : new Intl.DateTimeFormat("sv-SE", {day: "numeric", month: "short", year: "numeric"}).format(date);
}

function normalizeSeed(item) {
  const [category, label] = categoryInfo(item.category);
  return {
    id: item.id, category, label, title: item.title, excerpt: item.summary,
    date: dateLabel(item.publishedAt), time: `${item.readTimeMinutes || 3} min`,
    image: categoryImages[category], source: item.source?.name || "Originalkälla",
    url: safeUrl(item.source?.url), isDemo: true, location: item.location || ""
  };
}

function normalizeBot(item) {
  const [category, label] = categoryInfo(`${item.title} ${item.positive_signals?.join(" ") || ""}`);
  return {
    id: `bot-${item.id}`, category, label, title: item.title,
    excerpt: item.agent_summary || item.source_excerpt || "Öppna originalkällan för att läsa mer.",
    date: dateLabel(item.published_at), time: "Källnotis", image: categoryImages[category],
    source: item.source || "RSS-källa", url: safeUrl(item.url), isDemo: false,
    location: "Automatiskt källhämtad"
  };
}

async function loadArticles() {
  try {
    const [seedResponse, botResponse] = await Promise.all([
      fetch("/data/seed-news.json"), fetch("/data/news.json")
    ]);
    const seed = seedResponse.ok ? await seedResponse.json() : {articles: []};
    const bot = botResponse.ok ? await botResponse.json() : {items: []};
    articles = [
      ...(seed.articles || []).map(normalizeSeed),
      ...(bot.items || []).map(normalizeBot)
    ];
  } catch (error) {
    console.error("Kunde inte läsa nyhetsdata", error);
  }
  renderArticles();
}

function filteredArticles() {
  return articles.filter(article => {
    const categoryMatch = activeFilter === "alla" || article.category === activeFilter;
    const haystack = `${article.title} ${article.excerpt} ${article.label} ${article.source}`.toLocaleLowerCase("sv");
    return categoryMatch && haystack.includes(searchTerm.toLocaleLowerCase("sv"));
  });
}

function articleCard(article) {
  const badge = article.isDemo ? "Demo · " : "Källhämtad · ";
  return `<article class="news-card">
    <div class="card-image"><img src="${article.image}" alt="" loading="lazy"><span class="card-category">${escapeHTML(article.label)}</span>
    <button class="card-save ${savedIds.has(article.id) ? "saved" : ""}" type="button" data-save-article="${escapeHTML(article.id)}" aria-label="${savedIds.has(article.id) ? "Ta bort från sparade" : "Spara nyheten"}">${savedIds.has(article.id) ? "♥" : "♡"}</button></div>
    <div class="card-content">
      <h3>${escapeHTML(article.title)}</h3><p>${escapeHTML(article.excerpt)}</p>
      <div class="card-footer"><span>${badge}${escapeHTML(article.date)}</span>
      <button class="read-link article-open" type="button" data-article="${escapeHTML(article.id)}">Läs mer →</button></div>
    </div></article>`;
}

function renderArticles() {
  const matches = filteredArticles();
  newsGrid.innerHTML = matches.slice(0, visibleCount).map(articleCard).join("");
  emptyState.hidden = matches.length !== 0;
  loadMoreButton.hidden = matches.length <= visibleCount;
}

function openArticle(id) {
  const article = articles.find(item => item.id === id);
  if (!article) return;
  dialogContent.innerHTML = `<img class="dialog-hero" src="${article.image}" alt="">
    <article class="dialog-body"><span class="eyebrow">${escapeHTML(article.label)}</span>
    <h2>${escapeHTML(article.title)}</h2><p class="dialog-lead">${escapeHTML(article.excerpt)}</p>
    <p>${article.isDemo ? "Det här är en nyskriven demosammanfattning av den länkade originalkällan." : "Notisen är automatiskt hämtad från ett offentligt flöde och ska alltid läsas tillsammans med originalkällan."}</p>
    <div class="dialog-source"><strong>Källa:</strong> ${escapeHTML(article.source)} · ${escapeHTML(article.date)}</div>
    <div class="dialog-actions"><a class="button button-primary" href="${article.url}" target="_blank" rel="noopener noreferrer">Läs originalkällan →</a>
    <button class="button button-outline" type="button" data-save-article="${escapeHTML(article.id)}">${savedIds.has(article.id) ? "♥ Sparad" : "♡ Spara"}</button></div></article>`;
  if (!dialog.open) dialog.showModal();
}

async function loadSavedIds() {
  await window.ljusglimtAuth.ready;
  if (!window.ljusglimtAuth.state.user) return;
  try {
    const data = await window.ljusglimtAuth.request("/api/saved", {method:"GET"});
    data.articles.forEach(article => savedIds.add(article.article_id));
    renderArticles();
  } catch {}
}

async function toggleSaved(id) {
  const article = articles.find(item => item.id === id); if (!article) return;
  if (!window.ljusglimtAuth.state.user) {
    window.location.href = `/profil?next=${encodeURIComponent(location.pathname)}`; return;
  }
  try {
    if (savedIds.has(id)) {
      await window.ljusglimtAuth.request(`/api/saved/${encodeURIComponent(id)}`, {method:"DELETE"});
      savedIds.delete(id); showToast("Nyheten togs bort från din profil.");
    } else {
      await window.ljusglimtAuth.request("/api/saved", {method:"POST", body:JSON.stringify(article)});
      savedIds.add(id); showToast("Nyheten sparades till din profil.");
    }
    renderArticles();
    if (dialog.open) openArticle(id);
  } catch (error) { showToast(error.message); }
}

document.addEventListener("click", event => {
  const saver = event.target.closest("[data-save-article]");
  if (saver) { event.preventDefault(); toggleSaved(saver.dataset.saveArticle); return; }
  const opener = event.target.closest(".article-open");
  if (opener) openArticle(opener.dataset.article);
});

document.querySelectorAll(".filter-chip").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".filter-chip").forEach(item => { item.classList.remove("active"); item.setAttribute("aria-pressed", "false"); });
  button.classList.add("active"); button.setAttribute("aria-pressed", "true");
  activeFilter = button.dataset.filter; visibleCount = 6; renderArticles();
}));

loadMoreButton.addEventListener("click", () => { visibleCount += 6; renderArticles(); });
document.querySelector(".dialog-close").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });

const searchPanel = document.querySelector(".search-panel");
document.querySelector(".search-toggle").addEventListener("click", () => {
  searchPanel.hidden = !searchPanel.hidden;
  if (!searchPanel.hidden) document.querySelector("#site-search").focus();
});
searchPanel.addEventListener("submit", event => {
  event.preventDefault(); searchTerm = document.querySelector("#site-search").value.trim();
  visibleCount = 30; renderArticles(); document.querySelector("#nyheter").scrollIntoView({behavior: "smooth"});
});

const menuButton = document.querySelector(".menu-button");
menuButton.addEventListener("click", () => {
  const open = menuButton.getAttribute("aria-expanded") === "true";
  menuButton.setAttribute("aria-expanded", String(!open));
  document.querySelector(".main-nav").classList.toggle("open", !open);
});

function showToast(message) {
  toast.textContent = message; toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 4200);
}

document.querySelector("#newsletter-form").addEventListener("submit", async event => {
  event.preventDefault();
  const email = document.querySelector("#email").value;
  try {
    const response = await fetch("/api/newsletter", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({email})});
    const result = await response.json();
    showToast(result.message || result.error || "Tack!");
    if (response.ok) event.target.reset();
  } catch { showToast("Demo: formuläret fungerar när server.py körs."); }
});

document.querySelector(".demo-action")?.addEventListener("click", () => { window.location.href = "/forum"; });
Promise.all([loadArticles(), loadSavedIds()]);
