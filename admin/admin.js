/* TotalMant Admin – console for whoever runs the server. Plain JavaScript, no build step.
   Talks to /api on the admin server (its own port), logged in with the ADMIN_PASSWORD cookie. */
"use strict";

// ---------------------------------------------------------------- helpers
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// ---------------------------------------------------------------- language (it / en / no)
const LANGS = ["it", "en", "no"];
function pickLang() {
  let l = null;
  try { l = localStorage.getItem("tma_lang"); } catch { /* storage off */ }
  if (LANGS.includes(l)) return l;
  const nav = (navigator.language || "").toLowerCase();
  return nav.startsWith("it") ? "it" : /^(nb|nn|no)/.test(nav) ? "no" : "en";
}
let LANG = pickLang();
let LOCALE = ADMIN_I18N[LANG]._locale;
function T(key, ...a) {
  const v = ADMIN_I18N[LANG]?.[key] ?? ADMIN_I18N.en[key] ?? key;
  return typeof v === "function" ? v(...a) : v;
}
function setLang(l) {
  if (!LANGS.includes(l)) return;
  LANG = l; LOCALE = ADMIN_I18N[l]._locale;
  try { localStorage.setItem("tma_lang", l); } catch { /* storage off */ }
  document.documentElement.lang = l === "no" ? "nb" : l;
}
const langSwitch = () => `<div class="lang" role="group" aria-label="${esc(T("language"))}">${LANGS.map((l) =>
  `<button type="button" class="${l === LANG ? "on" : ""}" data-lang="${l}" title="${esc(ADMIN_I18N[l]._name)}">${l.toUpperCase()}</button>`).join("")}</div>`;
function wireLang(root, after) {
  $$("[data-lang]", root).forEach((b) => b.onclick = () => { setLang(b.dataset.lang); after(); });
}
// The server answers in English; known messages are translated here.
const SERVER_ERRORS = [
  [/^TotalMant Admin only answers/, () => T("err_network")],
  [/^Log in$/, () => T("err_login")],
  [/^Session expired/, () => T("err_expired")],
  [/^The admin password has changed/, () => T("err_pw_changed")],
  [/^Set ADMIN_PASSWORD/, () => T("err_not_set")],
  [/^Too many wrong passwords: wait (\d+)/, (m) => T("err_locked", m[1])],
  [/^Wrong password$/, () => T("err_wrong_pw")],
  [/^Family not found$/, () => T("err_no_family")],
  [/^Account not found$/, () => T("err_no_account")],
  [/^Invitation not found$/, () => T("err_no_invite")],
  [/^The code needs at least 4/, () => T("err_code_short")],
  [/^pg_dump is not installed/, () => T("err_no_pgdump")],
  [/^Backup failed: (.*)$/s, (m) => T("err_backup", m[1])],
  [/^Bad file name$/, () => T("err_bad_name")],
  [/^Backup not found$/, () => T("err_no_backup")],
  [/^(.+) is the only owner of (.+), which has other members/s, (m) => ADMIN_I18N[LANG].err_only_owner ? T("err_only_owner", m[1], m[2]) : m[0]],
];
function trError(msg) {
  for (const [re, f] of SERVER_ERRORS) { const m = re.exec(msg); if (m) return f(m); }
  return msg;
}
const n = (x) => (x ?? 0).toLocaleString(LOCALE);
const bytes = (b) => {
  if (b == null) return "–";
  const u = ["B", "kB", "MB", "GB", "TB"]; let i = 0; let v = b;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toLocaleString(LOCALE, { maximumFractionDigits: i ? 1 : 0 })} ${u[i]}`;
};
const dt = (iso) => iso ? new Date(iso).toLocaleString(LOCALE, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "–";
const day = (iso) => iso ? new Date(iso).toLocaleDateString(LOCALE, { day: "numeric", month: "short", year: "numeric" }) : "–";
function ago(iso) {
  if (!iso) return T("never");
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 60) return T("just_now");
  if (s < 3600) return T("min_ago", Math.floor(s / 60));
  if (s < 86400) return T("h_ago", Math.floor(s / 3600));
  if (s < 86400 * 30) return T("d_ago", Math.floor(s / 86400));
  return day(iso);
}
function timeShort(iso) {
  const d = new Date(iso), today = new Date();
  return d.toDateString() === today.toDateString()
    ? d.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString(LOCALE, { day: "numeric", month: "short" });
}

const svg = (p) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${p}</svg>`;
const I = {
  dash: svg('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'),
  family: svg('<path d="M3 10.5 12 4l9 6.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>'),
  users: svg('<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6"/>'),
  invite: svg('<path d="M3 6h18v12H3z"/><path d="m3 7 9 6 9-6"/>'),
  mail: svg('<path d="M4 4h16v16H4z"/><path d="M4 9h16M9 4v5"/>'),
  settings: svg('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>'),
  backup: svg('<path d="M4 7c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z"/><path d="M4 7v10c0 1.7 3.6 3 8 3s8-1.3 8-3V7M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>'),
  db: svg('<path d="M3 5h18v14H3zM3 10h18M9 10v9"/>'),
  log: svg('<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h7"/>'),
  info: svg('<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>'),
  refresh: svg('<path d="M20 11a8 8 0 0 0-14.6-4.5L4 8M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5L20 16M20 20v-4h-4"/>'),
  menu: svg('<path d="M4 6h16M4 12h16M4 18h16"/>'),
  plus: svg('<path d="M12 5v14M5 12h14"/>'),
  send: svg('<path d="m4 12 16-8-6 16-2-7z"/>'),
  key: svg('<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l3 3"/>'),
  arrow: svg('<path d="M5 12h14M13 6l6 6-6 6"/>'),
  ext: svg('<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>'),
};

async function api(path, { method = "GET", body } = {}) {
  const opt = { method, headers: {}, credentials: "same-origin" };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  let res;
  try { res = await fetch(`/api${path}`, opt); } catch { throw new Error(T("no_answer")); }
  if (res.status === 401 && path !== "/login") { state.authed = false; render(); throw new Error(T("login_again")); }
  const data = (res.headers.get("content-type") || "").includes("json") ? await res.json() : null;
  if (!res.ok) throw new Error(data?.detail && typeof data.detail === "string" ? trError(data.detail) : T("error_n", res.status));
  return data;
}

let toastTimer;
function toast(msg, err = false) {
  $(".toast")?.remove();
  const t = document.createElement("div");
  t.className = `toast${err ? " err" : ""}`; t.textContent = msg;
  document.body.append(t);
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.remove(), err ? 6000 : 3000);
}
const fail = (e) => toast(e.message || String(e), true);

function modal(title, html, buttons = `<button class="btn" data-close>${esc(T("close"))}</button>`) {
  closeModal();
  const back = document.createElement("div");
  back.className = "back";
  back.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}"><header>${esc(title)}</header>
    <div class="c">${html}</div><footer>${buttons}</footer></div>`;
  back.addEventListener("click", (e) => { if (e.target === back || e.target.closest("[data-close]")) closeModal(); });
  document.body.append(back);
  return back;
}
const closeModal = () => $(".back")?.remove();
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

function confirmBox(title, text, okLabel, danger = true) {
  return new Promise((resolve) => {
    const b = modal(title, `<p style="margin:0">${text}</p>`,
      `<button class="btn" data-close>${esc(T("cancel"))}</button><button class="btn ${danger ? "danger" : "primary"}" data-ok>${esc(okLabel)}</button>`);
    $("[data-ok]", b).onclick = () => { closeModal(); resolve(true); };
    b.addEventListener("click", (e) => { if (e.target === b || e.target.closest("[data-close]")) resolve(false); });
  });
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast(T("copied")); }
  catch { prompt(T("copy_prompt"), text); }
}

function linkModal(title, text, link) {
  const b = modal(title, `<p style="margin-top:0">${esc(text)}</p><input readonly value="${esc(link)}">`,
    `<button class="btn" data-close>${esc(T("close"))}</button><button class="btn primary" data-copy>${esc(T("copy_link"))}</button>`);
  $("[data-copy]", b).onclick = () => copy(link);
  $("input", b).onfocus = (e) => e.target.select();
}

// deltas: "↗ 6 %" like a report; bad=true when going up is bad (errors)
function delta(now, before, bad = false) {
  if (!before && !now) return `<span class="d same">–</span>`;
  if (!before) return `<span class="d up${bad ? " bad" : ""}">${esc(T("new_"))}</span>`;
  const p = Math.round(((now - before) / before) * 100);
  if (p === 0) return `<span class="d same">${esc(T("stable"))}</span>`;
  return `<span class="d ${p > 0 ? "up" : "down"}${bad ? " bad" : ""}">${p > 0 ? "↗" : "↘"} ${Math.abs(p)} %</span>`;
}
const kpi = (label, now, before, bad, fmt = n) =>
  `<div class="kpi"><span class="l">${esc(label)}</span><span class="v">${fmt(now)}</span>${before === null ? "<span></span>" : delta(now, before, bad)}</div>`;

const kindLabel = (k) => (ADMIN_I18N[LANG]?.[`kind_${k}`] ?? ADMIN_I18N.en[`kind_${k}`] ?? k);
const feed = (list, empty = T("nothing_yet")) => list.length
  ? `<ul class="feed">${list.map((e) => `<li><time title="${esc(dt(e.at))}">${esc(timeShort(e.at))}</time>
      <div><span class="k k-${esc(e.kind)}">${esc(kindLabel(e.kind))}</span>${esc(e.text)}
      ${e.group_name && e.group_id ? ` · <a href="#/families/${e.group_id}">${esc(e.group_name)}</a>` : ""}</div></li>`).join("")}</ul>`
  : `<div class="empty">${esc(empty)}</div>`;

// ---------------------------------------------------------------- state & router
const state = { authed: null, dash: null, timer: null, countdown: 60 };
const NAV = [
  ["#/", "nav_dash", "dash"], ["#/families", "nav_families", "family"], ["#/users", "nav_users", "users"],
  ["#/invitations", "nav_invites", "invite"], ["#/mail", "nav_mail", "mail"], ["#/settings", "nav_settings", "settings"],
];
const NAV_SYS = [["#/backups", "nav_backups", "backup"], ["#/database", "nav_database", "db"], ["#/log", "nav_log", "log"], ["#/system", "nav_system", "info"]];
const TITLES = { "": "nav_dash", families: "nav_families", users: "nav_users", invitations: "nav_invites", mail: "nav_mail",
  settings: "nav_settings", backups: "nav_backups", database: "nav_database", log: "nav_log", system: "nav_system" };

async function render() {
  clearInterval(state.timer);
  if (state.authed === null) {
    try { await api("/dashboard"); state.authed = true; } catch { state.authed = false; }
  }
  if (!state.authed) return renderLogin();
  const [, route = "", id] = (location.hash || "#/").split("/");
  if (!$(".shell")) renderShell();
  $$(".nav a").forEach((a) => a.classList.toggle("on", a.getAttribute("href") === `#/${route}`));
  $(".top h1").textContent = TITLES[route] ? T(TITLES[route]) : "TotalMant Admin";
  $(".top .refresh").hidden = route !== "";
  $(".shell").classList.remove("open");
  const main = $("#page");
  main.innerHTML = `<div class="muted" style="padding:20px 0">${esc(T("loading"))}</div>`;
  try {
    $(".top .refresh").hidden = route !== "";
    const page = { "": pageDash, families: id ? (el) => pageFamily(el, Number(id)) : pageFamilies, users: pageUsers,
      invitations: pageInvites, mail: pageMail, settings: pageSettings, backups: pageBackups, database: pageDatabase,
      log: pageLog, system: pageSystem }[route];
    if (!page) { location.hash = "#/"; return; }
    await page(main);
  } catch (e) { main.innerHTML = `<div class="panel"><div class="empty">${esc(e.message)}</div></div>`; }
}
window.addEventListener("hashchange", () => { closeModal(); render(); window.scrollTo(0, 0); });

function renderShell() {
  const link = ([h, l, i]) => `<a href="${h}">${I[i]}<span>${esc(T(l))}</span>${h === "#/invitations" ? `<span class="badge" id="badgeInv" hidden></span>` : ""}</a>`;
  $("#app").innerHTML = `<div class="shell">
    <aside class="side"><div class="brand"><img src="icon.svg" alt=""><div>TotalMant Admin<small>${esc(T("subtitle"))}</small></div></div>
      <nav class="nav">${NAV.map(link).join("")}<h6>${esc(T("nav_system_head"))}</h6>${NAV_SYS.map(link).join("")}</nav>
      <div class="foot">${langSwitch()}<div id="ver"></div><button id="logout">${esc(T("log_out"))}</button></div></aside>
    <main class="main"><div class="top"><button class="iconbtn menu-btn" id="menu" aria-label="${esc(T("menu"))}">${I.menu}</button>
      <h1>${esc(T("nav_dash"))}</h1><span class="date">${esc(new Date().toLocaleDateString(LOCALE, { weekday: "long", day: "numeric", month: "long" }))}</span>
      <span class="grow"></span>
      <span class="refresh"><span id="countdown"></span><button class="iconbtn" id="reload" title="${esc(T("refresh"))}" aria-label="${esc(T("refresh"))}">${I.refresh}</button></span></div>
      <div id="page"></div></main></div>`;
  $("#logout").onclick = async () => { try { await api("/logout", { method: "POST" }); } catch { /* gone anyway */ } state.authed = false; render(); };
  $("#menu").onclick = () => $(".shell").classList.toggle("open");
  $("#reload").onclick = () => render();
  wireLang($(".side"), () => { $("#app").innerHTML = ""; render(); });
}

function renderLogin() {
  $("#app").innerHTML = `<div class="login"><form class="box" id="lf">
    <div class="brand"><img src="icon.svg" alt=""><div>TotalMant Admin<small>${esc(T("subtitle"))}</small></div></div>
    <p>${esc(T("login_lead"))}</p>
    <label class="field"><span>${esc(T("admin_password"))}</span><input type="password" name="pw" autocomplete="current-password" required autofocus></label>
    <button class="btn primary">${esc(T("enter"))}</button>
    <div class="note" id="note">${T("login_note")}</div>${langSwitch()}</form></div>`;
  wireLang($("#lf"), renderLogin);
  api("/status").then((s) => {
    if (!s.configured) $("#note").innerHTML = T("login_not_set");
  }).catch(() => {});
  $("#lf").onsubmit = async (e) => {
    e.preventDefault();
    try { await api("/login", { method: "POST", body: { password: e.target.pw.value } }); state.authed = true; $("#app").innerHTML = ""; render(); }
    catch (err) { fail(err); e.target.pw.select(); }
  };
}

// ---------------------------------------------------------------- dashboard
async function pageDash(main) {
  const d = await api("/dashboard");
  const t = d.today, mo = d.month, tot = d.totals, sv = d.server;
  $("#ver").textContent = T("version_n", sv.version);
  const inv = $("#badgeInv"); if (inv) { inv.textContent = tot.open_invites; inv.hidden = !tot.open_invites; }
  const monthName = new Date().toLocaleDateString(LOCALE, { month: "long" });
  const signup = { open: T("signup_open"), code: T("signup_code"), closed: T("signup_closed") }[sv.signup] || sv.signup;
  main.innerHTML = `<div class="grid2">
    <div class="stack">
      <section class="panel"><header><h2>${esc(T("today"))}</h2><span class="sub">${esc(T("vs_yesterday"))}</span></header>
        <div class="kpis">
          ${kpi(T("new_families"), t.families.now, t.families.before)}
          ${kpi(T("logins"), t.logins.now, t.logins.before)}
          ${kpi(T("new_users"), t.users.now, t.users.before)}
          ${kpi(T("tasks_done"), t.tasks_done.now, t.tasks_done.before)}
          ${kpi(T("mails_sent"), t.mails.now, t.mails.before)}
          ${kpi(T("mails_failed"), t.mail_errors.now, t.mail_errors.before, true)}
        </div></section>
      <section class="panel"><header><h2>${esc(T("go_to"))}</h2></header>
        <div class="tiles">
          <a class="tile" href="#/families">${I.family}${esc(T("families"))}</a><a class="tile" href="#/users">${I.users}${esc(T("users"))}</a>
          <a class="tile" href="#/invitations">${I.invite}${esc(T("tile_invites"))}</a><a class="tile" href="#/mail">${I.mail}${esc(T("nav_mail"))}</a>
          <a class="tile" href="#/backups">${I.backup}${esc(T("nav_backups"))}</a><a class="tile" href="#/database">${I.db}${esc(T("nav_database"))}</a>
          <a class="tile" href="#/settings">${I.settings}${esc(T("nav_settings"))}</a><a class="tile" href="#/log">${I.log}${esc(T("tile_log"))}</a>
        </div></section>
      <section class="panel"><header><h2>${esc(T("recent"))}</h2><span class="grow"></span><a class="small" href="#/log">${esc(T("whole_log"))}</a></header>
        ${feed(d.recent, T("recent_empty"))}</section>
    </div>
    <div class="stack">
      <section class="panel"><header><h2>${esc(T("so_far_in", monthName))}</h2><span class="sub">${esc(T("vs_last_month"))}</span></header>
        <div class="kpis one">
          ${kpi(T("active_families"), mo.active_families.now, mo.active_families.before)}
          ${kpi(T("new_families"), mo.new_families.now, mo.new_families.before)}
          ${kpi(T("new_users"), mo.new_users.now, mo.new_users.before)}
          ${kpi(T("tasks_done"), mo.tasks_done.now, mo.tasks_done.before)}
        </div></section>
      <section class="panel"><header><h2>${esc(T("totals"))}</h2></header>
        <div class="kpis one">
          ${kpi(T("families"), tot.families, null)}${kpi(T("users"), tot.users, null)}
          ${tot.blocked ? kpi(T("blocked_users"), tot.blocked, null) : ""}
          ${kpi(T("things_long"), tot.things, null)}${kpi(T("active_tasks"), tot.tasks, null)}
          ${kpi(T("open_invites"), tot.open_invites, null)}
          ${kpi(T("attachments_n", n(tot.files)), tot.files_size, null, false, bytes)}
        </div></section>
      <section class="panel"><header><h2>${esc(T("server"))}</h2></header>
        <div class="links">
          <a href="#/settings">${I.settings}${esc(T("signup_label"))} <b>&nbsp;${esc(signup)}</b></a>
          <a href="#/mail">${I.mail}${esc(T("smtp_label"))} <b>&nbsp;${esc(sv.mail ? T("smtp_on") : T("smtp_off"))}</b></a>
          <a href="#/backups">${I.backup}${esc(T("last_backup"))} <b>&nbsp;${esc(ago(sv.last_backup))}</b></a>
          <a href="#/log">${I.log}${esc(T("last_reminders"))} <b>&nbsp;${esc(ago(sv.last_reminders))}</b></a>
        </div></section>
      <section class="panel"><header><h2>${esc(T("quick"))}</h2></header>
        <div class="actions">
          <button class="btn primary" id="qBackup">${I.backup}${esc(T("backup_now"))}</button>
          <button class="btn" id="qMail">${I.send}${esc(T("test_mail"))}</button>
          <button class="btn" id="qCode">${I.key}${esc(T("new_code"))}</button>
        </div></section>
    </div></div>`;
  $("#qBackup").onclick = () => doBackup();
  $("#qMail").onclick = () => testMailDialog();
  $("#qCode").onclick = () => newCodeDialog();
  // refresh every minute, like a control room
  state.countdown = 60;
  const cd = $("#countdown");
  state.timer = setInterval(() => {
    state.countdown -= 1;
    if (cd) cd.textContent = T("refresh_in", state.countdown);
    if (state.countdown <= 0 && !$(".back")) render();
  }, 1000);
}

async function doBackup() {
  toast(T("backup_running"));
  try { const r = await api("/backups", { method: "POST" }); toast(T("backup_done", r.name, bytes(r.size))); render(); }
  catch (e) { fail(e); }
}

function testMailDialog() {
  const b = modal(T("test_mail"), `<label class="field"><span>${esc(T("send_to"))}</span><input type="email" id="to" placeholder="nome@esempio.no"></label>`,
    `<button class="btn" data-close>${esc(T("cancel"))}</button><button class="btn primary" data-ok>${esc(T("send"))}</button>`);
  $("#to", b).focus();
  $("[data-ok]", b).onclick = async () => {
    const to = $("#to", b).value.trim(); if (!to) return;
    try { const r = await api("/mail/test", { method: "POST", body: { to } }); closeModal(); r.ok ? toast(T("sent_to", to)) : fail(new Error(r.error)); }
    catch (e) { fail(e); }
  };
}

async function newCodeDialog() {
  try {
    const { code } = await api("/settings/new-code");
    const ok = await confirmBox(T("new_code"), T("new_code_text", esc(code)), T("activate_code"), false);
    if (!ok) return;
    await api("/settings/signup", { method: "PUT", body: { mode: "code", code } });
    copy(code);
    render();
  } catch (e) { fail(e); }
}

// ---------------------------------------------------------------- families
function searchBox(main, placeholder, rows) {
  const input = $(".toolbar input", main);
  input.placeholder = placeholder;
  input.oninput = () => {
    const q = input.value.trim().toLowerCase();
    $$("tbody tr", main).forEach((tr, i) => { tr.hidden = q && !rows[i].toLowerCase().includes(q); });
  };
}

async function pageFamilies(main) {
  const list = await api("/families");
  main.innerHTML = `<div class="toolbar"><input type="search"><span class="muted small">${esc(T("n_families", n(list.length)))}</span></div>
    <section class="panel"><div class="tablewrap"><table class="t"><thead><tr><th>${esc(T("family"))}</th><th>${esc(T("owner"))}</th>
      <th class="num">${esc(T("members"))}</th><th class="num">${esc(T("things"))}</th><th class="num">${esc(T("tasks"))}</th><th>${esc(T("created"))}</th><th>${esc(T("last_activity"))}</th></tr></thead>
      <tbody>${list.map((f) => `<tr class="click" data-id="${f.id}"><td><b>${esc(f.name)}</b></td>
        <td>${f.owner ? `${esc(f.owner.name)}<div class="small muted">${esc(f.owner.email)}</div>` : `<span class="pill bad">${esc(T("no_owner"))}</span>`}</td>
        <td class="num">${f.members}</td><td class="num">${f.things}</td><td class="num">${f.tasks}</td>
        <td>${day(f.created_at)}</td><td>${esc(ago(f.last_activity))}</td></tr>`).join("")}</tbody></table></div>
      ${list.length ? "" : `<div class="empty">${esc(T("no_families"))}</div>`}</section>`;
  searchBox(main, T("search_families"), list.map((f) => `${f.name} ${f.owner?.name || ""} ${f.owner?.email || ""}`));
  $$("tr[data-id]", main).forEach((tr) => tr.onclick = () => { location.hash = `#/families/${tr.dataset.id}`; });
}

async function pageFamily(main, id) {
  const f = await api(`/families/${id}`);
  const c = f.counts;
  const kinds = Object.entries(c.things_by_kind).map(([k, v]) => `${v} ${esc(T(`thing_${k}`))}`).join(", ");
  $(".top h1").textContent = f.name;
  main.innerHTML = `<a class="crumb" href="#/families">← ${esc(T("families"))}</a>
    <div class="headline"><h2>${esc(f.name)}</h2><span class="muted">${esc(T("created_on", day(f.created_at)))}</span><span class="grow" style="flex:1"></span>
      <button class="btn danger" id="del">${esc(T("delete_family"))}</button></div>
    <div class="grid2"><div class="stack">
      <section class="panel"><header><h2>${esc(T("members"))}</h2><span class="sub">${f.members.length}</span></header>
        <div class="tablewrap"><table class="t"><thead><tr><th>${esc(T("name"))}</th><th>${esc(T("role"))}</th><th>${esc(T("last_login"))}</th><th></th></tr></thead><tbody>
        ${f.members.map((u) => `<tr><td><b>${esc(u.name)}</b>${u.blocked ? ` <span class="pill blocked">${esc(T("blocked"))}</span>` : ""}
            <div class="small muted">${esc(u.email)}${u.other_families ? ` · ${esc(T("also_in", u.other_families))}` : ""}</div></td>
          <td><span class="pill ${u.role_key === "owner" ? "owner" : ""}">${esc(u.role)}</span></td>
          <td>${esc(ago(u.last_login))}</td><td class="act"><a href="#/users" data-find="${esc(u.email)}">${esc(T("user_link"))}</a></td></tr>`).join("")}
        </tbody></table></div></section>
      <section class="panel"><header><h2>${esc(T("family_events"))}</h2></header>${feed(f.events)}</section>
    </div><div class="stack">
      <section class="panel"><header><h2>${esc(T("content"))}</h2><span class="sub">${esc(T("numbers_only"))}</span></header>
        <div class="kpis one">${kpi(T("things"), c.things, null)}${kinds ? `<div class="kpi"><span class="l small muted">${kinds}</span><span></span><span></span></div>` : ""}
          ${kpi(T("active_tasks"), c.tasks, null)}${kpi(T("jobs_done"), c.done, null)}${kpi(T("vendors"), c.vendors, null)}
          ${kpi(T("attachments_n", n(c.files)), c.files_size, null, false, bytes)}</div></section>
      <section class="panel"><header><h2>${esc(T("roles"))}</h2></header><div class="kpis one">${f.roles.map((r) =>
        `<div class="kpi"><span class="l">${esc(r.name)}</span><span class="v">${esc(r.permissions == null ? T("everything") : T("n_permissions", r.permissions))}</span><span></span></div>`).join("")}</div></section>
      <section class="panel"><header><h2>${esc(T("open_invites"))}</h2></header>${f.invites.length ? `<div class="kpis one">${f.invites.map((i) =>
        `<div class="kpi"><span class="l">${esc(i.email)} <span class="pill">${esc(i.role)}</span></span><span class="small muted">${esc(T("expires", day(i.expires_at)))}</span><span></span></div>`).join("")}</div>`
        : `<div class="empty">${esc(T("none"))}</div>`}</section>
    </div></div>`;
  $$("[data-find]", main).forEach((a) => a.onclick = () => { state.findUser = a.dataset.find; });
  $("#del").onclick = async () => {
    const ok = await confirmBox(T("delete_family_q", f.name), T("delete_family_text", n(c.things), n(c.files)), T("delete_forever"));
    if (!ok) return;
    try {
      const r = await api(`/families/${id}`, { method: "DELETE" });
      toast(r.accounts_deleted.length ? T("family_deleted_n", r.accounts_deleted.length) : T("family_deleted"));
      location.hash = "#/families";
    } catch (e) { fail(e); }
  };
}

// ---------------------------------------------------------------- users
async function pageUsers(main) {
  const list = await api("/users");
  main.innerHTML = `<div class="toolbar"><input type="search"><span class="muted small">${esc(T("n_users", n(list.length)))}</span></div>
    <section class="panel"><div class="tablewrap"><table class="t"><thead><tr><th>${esc(T("user"))}</th><th>${esc(T("families_roles"))}</th>
      <th>${esc(T("registered"))}</th><th>${esc(T("last_login"))}</th><th></th></tr></thead>
      <tbody>${list.map((u) => `<tr><td><b>${esc(u.name)}</b>${u.blocked ? ` <span class="pill blocked">${esc(T("blocked"))}</span>` : ""}${u.is_admin ? ` <span class="pill warn" title="${esc(T("old_admin"))}">admin</span>` : ""}
          <div class="small muted">${esc(u.email)}</div></td>
        <td>${u.families.map((f) => `<a class="pill ${f.role_key === "owner" ? "owner" : ""}" href="#/families/${f.id}">${esc(f.name)} · ${esc(f.role)}</a>`).join("") || `<span class="pill bad">${esc(T("no_family"))}</span>`}</td>
        <td>${day(u.created_at)}</td><td>${esc(ago(u.last_login))}</td>
        <td class="act"><button class="btn small" data-reset="${u.id}" title="${esc(T("reset_title"))}">${I.key}${esc(T("reset_btn"))}</button>
          <button class="btn small" data-block="${u.id}">${esc(u.blocked ? T("unblock") : T("block"))}</button>
          <button class="btn small danger" data-del="${u.id}">${esc(T("delete"))}</button></td></tr>`).join("")}</tbody></table></div></section>`;
  searchBox(main, T("search_users"), list.map((u) => `${u.name} ${u.email} ${u.families.map((f) => f.name).join(" ")}`));
  if (state.findUser) { const i = $(".toolbar input", main); i.value = state.findUser; i.oninput(); state.findUser = null; }
  const byId = (b, k) => list.find((u) => u.id === Number(b.dataset[k]));
  $$("[data-reset]", main).forEach((b) => b.onclick = async () => {
    const u = byId(b, "reset");
    try { const r = await api(`/users/${u.id}/reset-link`, { method: "POST" });
      linkModal(T("reset_for", u.name), T("reset_text", u.email, r.hours), r.link);
    } catch (e) { fail(e); }
  });
  $$("[data-block]", main).forEach((b) => b.onclick = async () => {
    const u = byId(b, "block");
    if (!u.blocked && !(await confirmBox(T("block_q", u.name), T("block_text"), T("block")))) return;
    try { await api(`/users/${u.id}/block`, { method: "POST", body: { blocked: !u.blocked } }); toast(u.blocked ? T("unblocked") : T("blocked_done")); render(); }
    catch (e) { fail(e); }
  });
  $$("[data-del]", main).forEach((b) => b.onclick = async () => {
    const u = byId(b, "del");
    const lonely = u.families.filter((f) => f.role_key === "owner");
    const ok = await confirmBox(T("delete_user_q", u.name),
      T("delete_user_text", esc(u.email), lonely.map((f) => esc(f.name)).join(", ")), T("delete_forever"));
    if (!ok) return;
    try { const r = await api(`/users/${u.id}`, { method: "DELETE" }); toast(r.families_deleted.length ? T("user_deleted_with", r.families_deleted.join(", ")) : T("user_deleted")); render(); }
    catch (e) { fail(e); }
  });
}

// ---------------------------------------------------------------- invitations
async function pageInvites(main) {
  const d = await api("/invitations");
  const lbl = { open: T("inv_open"), accepted: T("inv_accepted"), expired: T("inv_expired") };
  const open = d.invitations.filter((i) => i.status === "open");
  main.innerHTML = `<div class="grid2"><section class="panel"><header><h2>${esc(T("invitations"))}</h2><span class="sub">${esc(T("n_open", open.length))}</span></header>
      ${d.invitations.length ? `<div class="tablewrap"><table class="t"><thead><tr><th>${esc(T("email"))}</th><th>${esc(T("family"))}</th><th>${esc(T("status"))}</th><th>${esc(T("sent"))}</th><th></th></tr></thead><tbody>
      ${d.invitations.map((i) => `<tr><td><b>${esc(i.email)}</b><div class="small muted">${esc(i.role)}${i.invited_by ? ` · ${esc(T("by", i.invited_by))}` : ""}</div></td>
        <td><a href="#/families/${i.group_id}">${esc(i.family)}</a></td>
        <td><span class="pill ${i.status}">${lbl[i.status]}</span><div class="small muted">${i.status === "open" ? esc(T("expires", day(i.expires_at))) : i.accepted_at ? day(i.accepted_at) : ""}</div></td>
        <td>${day(i.created_at)}</td>
        <td class="act">${i.status === "open" ? `<button class="btn small danger" data-cancel="${i.id}">${esc(T("cancel"))}</button>` : ""}</td></tr>`).join("")}
      </tbody></table></div>` : `<div class="empty">${esc(T("no_invites"))}</div>`}</section>
    <section class="panel"><header><h2>${esc(T("signups"))}</h2><span class="sub">${esc(T("new_families_sub"))}</span></header>${feed(d.signups, T("no_signups"))}</section></div>`;
  $$("[data-cancel]", main).forEach((b) => b.onclick = async () => {
    if (!(await confirmBox(T("cancel_invite_q"), T("cancel_invite_text"), T("cancel_invite")))) return;
    try { await api(`/invitations/${b.dataset.cancel}`, { method: "DELETE" }); render(); } catch (e) { fail(e); }
  });
}

// ---------------------------------------------------------------- e-mail
async function pageMail(main) {
  const d = await api("/mail");
  main.innerHTML = `<div class="grid2"><div class="stack">
      <section class="panel"><header><h2>${esc(T("smtp_settings"))}</h2><span class="sub">${esc(T("from_env"))}</span></header>
        <dl class="facts"><dt>${esc(T("status"))}</dt><dd>${d.configured ? `<span class="pill ok">${esc(T("smtp_on"))}</span>` : `<span class="pill bad">${esc(T("smtp_off"))}</span>`}</dd>
          <dt>Server</dt><dd class="mono">${esc(d.host || "–")}${d.host ? `:${d.port}` : ""}</dd><dt>${esc(T("user_smtp"))}</dt><dd class="mono">${esc(d.user || "–")}</dd>
          <dt>${esc(T("sender"))}</dt><dd class="mono">${esc(d.sender || "–")}</dd></dl>
        ${d.configured ? "" : `<div class="body small muted">${T("smtp_help")}</div>`}
        <div class="actions"><button class="btn primary" id="test">${I.send}${esc(T("send_test"))}</button></div></section>
    </div>
    <section class="panel"><header><h2>${esc(T("mail_log"))}</h2><span class="sub">${esc(T("last_100"))}</span></header>${feed(d.log, T("no_mail"))}</section></div>`;
  $("#test").onclick = () => testMailDialog();
}

// ---------------------------------------------------------------- settings
async function pageSettings(main) {
  const s = await api("/settings");
  const opt = (v, title, text) => `<label class="radio"><input type="radio" name="mode" value="${v}" ${s.signup_mode === v ? "checked" : ""}><span><b>${esc(title)}</b><span class="small muted">${esc(text)}</span></span></label>`;
  main.innerHTML = `<div class="grid2"><section class="panel"><header><h2>${esc(T("signup_title"))}</h2>
      <span class="sub">${esc(s.signup_from === "admin" ? T("chosen_here") : T("from_env"))}</span></header><div class="body">
      ${opt("open", T("open_title"), T("open_text"))}
      ${opt("code", T("code_title"), T("code_text"))}
      ${opt("closed", T("closed_title"), T("closed_text"))}
      <label class="field" id="codeField" ${s.signup_mode === "code" ? "" : "hidden"}><span>${esc(T("code"))}</span>
        <span style="display:flex;gap:8px"><input id="code" value="${esc(s.signup_code)}" style="flex:1"><button class="btn" type="button" id="gen">${esc(T("generate"))}</button></span></label>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" id="save">${esc(T("save"))}</button>
        ${s.signup_from === "admin" ? `<button class="btn" id="env">${esc(T("back_to_env"))}</button>` : ""}</div></div></section>
    <section class="panel"><header><h2>${esc(T("other_values"))}</h2><span class="sub">${esc(T("other_values_sub"))}</span></header>
      <dl class="facts"><dt>${esc(T("app_address"))}</dt><dd class="mono">${esc(s.public_url)}</dd>
        <dt>${esc(T("invite_validity"))}</dt><dd>${esc(T("n_days", s.invite_days))} <span class="muted mono">INVITE_DAYS</span></dd>
        <dt>${esc(T("reset_validity"))}</dt><dd>${esc(T("n_hours", s.reset_hours))} <span class="muted mono">RESET_HOURS</span></dd>
        <dt>${esc(T("admin_session"))}</dt><dd>${esc(T("n_hours", s.session_hours))} <span class="muted mono">ADMIN_SESSION_HOURS</span></dd>
        <dt>${esc(T("allowed_nets"))}</dt><dd class="mono small">${esc(s.allow_nets)}</dd></dl></section></div>`;
  $$('input[name="mode"]', main).forEach((r) => r.onchange = () => { $("#codeField").hidden = r.value !== "code" || !r.checked; });
  $("#gen").onclick = async () => { try { $("#code").value = (await api("/settings/new-code")).code; } catch (e) { fail(e); } };
  $("#save").onclick = async () => {
    const mode = $('input[name="mode"]:checked', main)?.value;
    try { await api("/settings/signup", { method: "PUT", body: { mode, code: $("#code").value } }); toast(T("saved")); render(); } catch (e) { fail(e); }
  };
  $("#env")?.addEventListener("click", async () => {
    try { await api("/settings/signup", { method: "PUT", body: { mode: "env" } }); toast(T("env_now")); render(); } catch (e) { fail(e); }
  });
}

// ---------------------------------------------------------------- backups
async function pageBackups(main) {
  const d = await api("/backups");
  main.innerHTML = `<div class="grid2"><section class="panel"><header><h2>${esc(T("db_backups"))}</h2><span class="sub">${esc(T("n_files_keep", d.files.length))}</span>
      <span class="grow"></span><button class="btn primary small" id="now">${I.backup}${esc(T("backup_now"))}</button></header>
      ${d.files.length ? `<div class="tablewrap"><table class="t"><thead><tr><th>${esc(T("file"))}</th><th>${esc(T("date"))}</th><th class="num">${esc(T("size"))}</th><th></th></tr></thead><tbody>
      ${d.files.map((f) => `<tr><td class="mono">${esc(f.name)}</td><td>${dt(f.at)}</td><td class="num">${bytes(f.size)}</td>
        <td class="act"><a class="btn small" href="/api/backups/${encodeURIComponent(f.name)}">${esc(T("download"))}</a></td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty">${esc(T("no_backups"))}</div>`}</section>
    <section class="panel"><header><h2>${esc(T("where_how"))}</h2></header>
      <dl class="facts"><dt>${esc(T("folder"))}</dt><dd class="mono small">${esc(d.dir)}</dd><dt>${esc(T("database"))}</dt><dd>${esc(d.kind)}</dd>
        <dt>${esc(T("free_space"))}</dt><dd>${esc(T("of", bytes(d.disk_free), bytes(d.disk_total)))}</dd></dl>
      <div class="body small muted">${T("backup_help")}</div></section></div>`;
  $("#now").onclick = () => doBackup();
}

// ---------------------------------------------------------------- database & system
async function pageDatabase(main) {
  const s = await api("/system");
  const adminer = s.adminer_url || `${location.protocol}//${location.hostname}:8082/?pgsql=db&username=totalmaint&db=totalmaint`;
  main.innerHTML = `<div class="grid2"><section class="panel"><header><h2>${esc(T("tables"))}</h2><span class="sub">${esc(s.database)} · ${bytes(s.database_size)}</span></header>
      <div class="tablewrap"><table class="t"><thead><tr><th>${esc(T("table"))}</th><th class="num">${esc(T("rows"))}</th></tr></thead><tbody>
      ${s.tables.map((t) => `<tr><td class="mono">${esc(t.name)}</td><td class="num">${n(t.rows)}</td></tr>`).join("")}</tbody></table></div></section>
    <section class="panel"><header><h2>Adminer</h2><span class="sub">${esc(T("adminer_sub"))}</span></header>
      <div class="body"><p style="margin-top:0">${T("adminer_text")}</p>
        <p class="small muted">${esc(T("adminer_warn"))}</p>
        <a class="btn primary" href="${esc(adminer)}" target="_blank" rel="noopener">${I.ext}${esc(T("open_adminer"))}</a></div></section></div>`;
}

async function pageSystem(main) {
  const s = await api("/system");
  main.innerHTML = `<div class="grid2"><section class="panel"><header><h2>${esc(T("nav_system"))}</h2></header>
    <dl class="facts"><dt>TotalMaint</dt><dd><b>${esc(s.version)}</b></dd><dt>Python</dt><dd>${esc(s.python)}</dd><dt>${esc(T("system_sys"))}</dt><dd class="small">${esc(s.platform)}</dd>
      <dt>${esc(T("database"))}</dt><dd>${esc(s.database)} · <span class="mono small">${esc(s.database_where)}</span></dd><dt>${esc(T("db_size"))}</dt><dd>${bytes(s.database_size)}</dd>
      <dt>${esc(T("attachments"))}</dt><dd>${esc(T("n_files", n(s.uploads)))} · ${bytes(s.uploads_size)}</dd><dt>${esc(T("started"))}</dt><dd>${dt(s.started_at)}</dd><dt>${esc(T("timezone"))}</dt><dd>${esc(s.timezone)}</dd></dl></section>
    <section class="panel"><header><h2>${esc(T("server_log"))}</h2></header><div class="body small">${T("server_log_text")}</div></section></div>`;
}

async function pageLog(main, before = null, kind = state.logKind || "") {
  const d = await api(`/events?${kind ? `kind=${kind}&` : ""}${before ? `before=${before}` : ""}`);
  const opts = Object.keys(d.kinds).map((k) => `<option value="${k}" ${k === kind ? "selected" : ""}>${esc(kindLabel(k))}</option>`).join("");
  if (!before) {
    main.innerHTML = `<div class="toolbar"><select id="kind"><option value="">${esc(T("all_events"))}</option>${opts}</select></div>
      <section class="panel"><div id="list"></div></section><div style="margin-top:10px"><button class="btn" id="more" hidden>${esc(T("more"))}</button></div>`;
    $("#kind").onchange = (e) => { state.logKind = e.target.value; pageLog(main, null, e.target.value); };
  }
  const list = $("#list");
  list.insertAdjacentHTML("beforeend", feed(d.events, T("no_events")));
  const last = d.events[d.events.length - 1];
  $("#more").hidden = d.events.length < 100;
  $("#more").onclick = () => pageLog(main, last.id, kind);
}

setLang(LANG);
render();
