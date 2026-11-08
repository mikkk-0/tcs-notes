const LABELS = {
  notes: ["Конспект", "Теория и доказательства", "≡"],
  assignments: ["Задачи", "Листок упражнений", "✎"],
  hints: ["Подсказки", "Открывайте постепенно", "?"],
  solutions: ["Решения", "Полные разборы", "✓"],
};

const content = document.getElementById("content");
const nav = document.getElementById("course-nav");
let courses = [];

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function route() { return decodeURIComponent(location.hash.slice(1) || "/").split("/").filter(Boolean); }
function link(path, label) { return `<a href="#/${path}">${esc(label)}</a>`; }
function crumbs(parts) { return `<nav class="breadcrumbs" aria-label="Навигационная цепочка">${parts.map((p, i) => `${i ? '<span class="sep">/</span>' : ""}${p}`).join("")}</nav>`; }
function pdfLink(path, title, detail, symbol = "PDF") {
  return `<a class="doc" href="${esc(path)}" target="_blank" rel="noopener" aria-label="Открыть PDF: ${esc(title)}"><span class="doc-icon" aria-hidden="true">${symbol}</span><span class="doc-copy"><strong>${esc(title)}</strong><small>${esc(detail)} · PDF</small></span><span class="doc-action" aria-hidden="true">↗</span></a>`;
}
function renderHome() {
  document.title = "Конспекты по TCS";
  content.innerHTML = `${crumbs(["Главная"])}<span class="eyebrow">Библиотека курсов</span><h1>Конспекты по теоретической информатике</h1><p class="intro">Все материалы курса в одном месте: откройте тему и читайте конспект, решайте задачи или смотрите разборы прямо с телефона.</p><div class="section-head"><h2>Курсы</h2></div><div class="grid">${courses.map(c => `<a class="card" href="#/course/${esc(c.id)}"><div><span class="card-kicker">Курс · ${c.lessons.length} тем</span><h3>${esc(c.name)}</h3><p>${esc(c.subtitle)}</p></div><div class="card-bottom"><span>Открыть темы</span><span class="card-arrow" aria-hidden="true">→</span></div></a>`).join("")}</div>`;
}
function renderCourse(course) {
  document.title = `${course.name} — Конспекты TCS`;
  content.innerHTML = `${crumbs([link("", "Главная"), esc(course.name)])}<span class="eyebrow">Курс · ${course.lessons.length} тем</span><h1>${esc(course.name)}</h1><p class="intro">${esc(course.subtitle)}. Выберите тему, чтобы открыть PDF с конспектом, задачами${course.hasHints ? ", подсказками" : ""} и решениями.</p><div class="section-head"><h2>Темы</h2><span class="count" id="topic-count">${course.lessons.length}</span></div><div class="search-row"><label for="topic-search">Найти тему</label><input id="topic-search" type="search" placeholder="Название или номер" autocomplete="off"></div><div class="grid topic-grid" id="topic-grid"></div><section class="extras" id="extras"></section>`;
  const grid = document.getElementById("topic-grid");
  const search = document.getElementById("topic-search");
  const update = () => {
    const query = search.value.trim().toLocaleLowerCase("ru");
    const found = course.lessons.filter(t => `${t.number} ${t.title}`.toLocaleLowerCase("ru").includes(query));
    document.getElementById("topic-count").textContent = `${found.length} из ${course.lessons.length}`;
    grid.innerHTML = found.length ? found.map(t => `<a class="card" href="#/course/${esc(course.id)}/lesson/${esc(t.slug)}"><div><span class="card-kicker">Тема ${String(t.number).padStart(2, "0")}</span><h3>${esc(t.title)}</h3></div><div class="card-bottom"><span>Материалы темы</span><span class="card-arrow" aria-hidden="true">→</span></div></a>`).join("") : '<p class="empty">Темы не найдены. Попробуйте другое название.</p>';
  };
  search.addEventListener("input", update);
  update();
  document.getElementById("extras").innerHTML = course.extras.length ? `<div class="section-head" style="margin-top:42px"><h2>Итоговые материалы</h2></div><div class="docs">${course.extras.map(x => pdfLink(x.path, x.title, "Материалы курса", "PDF")).join("")}</div>` : "";
}
function renderLesson(course, lesson) {
  document.title = `${lesson.title} — ${course.name}`;
  const index = course.lessons.indexOf(lesson);
  const docs = Object.entries(lesson.files).filter(([, path]) => path).map(([kind, path]) => pdfLink(path, LABELS[kind][0], LABELS[kind][1], LABELS[kind][2])).join("");
  const prev = course.lessons[index - 1], next = course.lessons[index + 1];
  content.innerHTML = `${crumbs([link("", "Главная"), link(`course/${course.id}`, course.name), `Тема ${String(lesson.number).padStart(2, "0")}`])}<span class="eyebrow">${esc(course.name)} · тема ${String(lesson.number).padStart(2, "0")}</span><h1>${esc(lesson.title)}</h1><p class="intro">Выберите документ. PDF откроется в новой вкладке браузера.</p><div class="section-head"><h2>Материалы темы</h2></div><div class="docs">${docs}</div>${lesson.files.solutions ? '<p class="callout">Решения лучше открывать после самостоятельной попытки. Если в курсе есть подсказки, начните с них.</p>' : ""}<nav class="next-prev" aria-label="Соседние темы"><span>${prev ? link(`course/${course.id}/lesson/${prev.slug}`, `← Тема ${String(prev.number).padStart(2, "0")}`) : ""}</span><span>${next ? link(`course/${course.id}/lesson/${next.slug}`, `Тема ${String(next.number).padStart(2, "0")} →`) : ""}</span></nav>`;
}
function render() {
  const parts = route();
  const course = parts[0] === "course" ? courses.find(c => c.id === parts[1]) : null;
  nav.innerHTML = `<a class="nav-link ${parts.length ? "" : "active"}" href="#/">Главная</a>${courses.map(c => `<a class="nav-link ${course === c ? "active" : ""}" href="#/course/${esc(c.id)}">${esc(c.name)}</a>`).join("")}`;
  if (!parts.length) renderHome();
  else if (course && parts.length === 2) renderCourse(course);
  else if (course && parts[2] === "lesson" && course.lessons.some(t => t.slug === parts[3])) renderLesson(course, course.lessons.find(t => t.slug === parts[3]));
  else content.innerHTML = `${crumbs([link("", "Главная")])}<h1>Страница не найдена</h1><p class="intro">Вернитесь к списку курсов.</p>`;
  window.scrollTo(0, 0);
}
if (Array.isArray(window.TCS_COURSES)) {
  courses = window.TCS_COURSES;
  render();
  window.addEventListener("hashchange", render);
} else {
  content.innerHTML = '<h1>Не удалось открыть каталог</h1><p>Проверьте, что файл catalogue.js находится рядом с index.html.</p>';
}
