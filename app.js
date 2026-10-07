(function () {
  "use strict";
  var PAGE = 20;
  var all = [], shown = PAGE;
  var $ = function (id) { return document.getElementById(id); };
  var els = { q: $("q"), cat: $("cat"), state: $("state"), sort: $("sort"), list: $("list"),
              count: $("count"), more: $("more"), chips: $("chips"), stats: $("stats"), updated: $("updated") };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function safeUrl(u) { return /^https?:\/\//i.test(u || "") ? u : ""; }
  function daysAgo(d) { return Math.floor((Date.now() - new Date(d + "T00:00:00Z").getTime()) / 86400000); }

  function fillSelect(sel, values) {
    values.forEach(function (v) { var o = document.createElement("option"); o.value = v; o.textContent = v; sel.appendChild(o); });
  }
  function uniq(key) {
    var m = {}; all.forEach(function (j) { if (j[key]) m[j[key]] = (m[j[key]] || 0) + 1; });
    return Object.keys(m).sort(function (a, b) { return m[b] - m[a]; });
  }

  function filtered() {
    var q = els.q.value.trim().toLowerCase(), c = els.cat.value, s = els.state.value;
    var out = all.filter(function (j) {
      if (c && j.category !== c) return false;
      if (s && j.state !== s) return false;
      if (q) {
        var hay = (j.title + " " + j.organisation + " " + j.category + " " + j.state + " " + j.summary).toLowerCase();
        return q.split(/\s+/).every(function (w) { return hay.indexOf(w) !== -1; });
      }
      return true;
    });
    if (els.sort.value === "vac") out.sort(function (a, b) { return (+b.vacancies || 0) - (+a.vacancies || 0); });
    return out;
  }

  function card(j) {
    var apply = safeUrl(j.apply_url), notif = safeUrl(j.notification_url), src = safeUrl(j.source_url);
    var age = daysAgo(j.posted);
    var h = '<article class="job"><h2>' + esc(j.title) + "</h2>";
    h += '<div class="meta"><span class="tag">' + esc(j.category) + "</span>";
    if (age <= 2) h += '<span class="tag new">NEW</span>';
    h += "<span>📍 " + esc(j.state) + "</span><span>🗓 Posted " + esc(j.posted) + "</span>";
    h += j.official ? '<span class="off">✔ Official link</span>' : (apply ? '<span class="unv">Link from source – verify before applying</span>' : '<span class="unv">Official link not found – check source</span>');
    h += "</div>";
    if (j.summary) h += '<p class="sum">' + esc(j.summary) + "</p>";
    h += '<div class="facts">';
    if (j.organisation) h += "<span>🏛 <b>" + esc(j.organisation) + "</b></span>";
    if (j.vacancies) h += "<span>👥 Vacancies: <b>" + esc(j.vacancies) + "</b></span>";
    if (j.last_date) h += "<span>⏳ Last date: <b>" + esc(j.last_date) + "</b></span>";
    h += "</div><div class=\"btns\">";
    if (apply) h += '<a class="btn main" href="' + esc(apply) + '" target="_blank" rel="noopener noreferrer">Apply / Official site</a>';
    if (notif) h += '<a class="btn" href="' + esc(notif) + '" target="_blank" rel="noopener noreferrer">Notification PDF</a>';
    if (src) h += '<a class="btn" href="' + esc(src) + '" target="_blank" rel="noopener noreferrer">Full details (' + esc(j.source_name) + ")</a>";
    h += "</div></article>";
    return h;
  }

  function render() {
    var f = filtered();
    els.count.textContent = f.length + " job" + (f.length === 1 ? "" : "s") + " found";
    if (!f.length) {
      els.list.innerHTML = '<div class="empty">' + (all.length ? "No jobs match your filters." :
        "No jobs yet. The daily update has not run – see README (run the GitHub Action once).") + "</div>";
      els.more.hidden = true; return;
    }
    els.list.innerHTML = f.slice(0, shown).map(card).join("");
    els.more.hidden = shown >= f.length;
  }

  function reset() { shown = PAGE; render(); }

  function buildChips() {
    var cats = uniq("category").slice(0, 8);
    els.chips.innerHTML = "";
    cats.forEach(function (c) {
      var b = document.createElement("button");
      b.className = "chip"; b.textContent = c;
      b.onclick = function () {
        els.cat.value = els.cat.value === c ? "" : c;
        Array.prototype.forEach.call(els.chips.children, function (x) { x.classList.toggle("on", x.textContent === els.cat.value); });
        reset();
      };
      els.chips.appendChild(b);
    });
  }

  fetch("data/jobs.json?v=" + Date.now())
    .then(function (r) { return r.json(); })
    .then(function (d) {
      all = d.jobs || [];
      els.updated.textContent = d.generated_at || "–";
      var today = all.filter(function (j) { return daysAgo(j.posted) <= 1; }).length;
      els.stats.innerHTML = "<div><b>" + all.length + "</b> total jobs</div><div><b>" + today + "</b> added in last 2 days</div>";
      fillSelect(els.cat, uniq("category")); fillSelect(els.state, uniq("state"));
      buildChips(); render();
    })
    .catch(function () { els.list.innerHTML = '<div class="empty">Could not load jobs. Please refresh.</div>'; });

  ["input", "change"].forEach(function (ev) {
    [els.q, els.cat, els.state, els.sort].forEach(function (e) { e.addEventListener(ev, reset); });
  });
  els.more.addEventListener("click", function () { shown += PAGE; render(); });
})();
