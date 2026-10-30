/* TotalMant Admin – console for whoever runs the server. Plain JavaScript, no build step.
   Talks to /api on the admin server (its own port), logged in with the ADMIN_PASSWORD cookie. */
"use strict";

// ---------------------------------------------------------------- helpers
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const LOCALE = "it-IT";
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
  if (!iso) return "mai";
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 60) return "adesso";
  if (s < 3600) return `${Math.floor(s / 60)} min fa`;
  if (s < 86400) return `${Math.floor(s / 3600)} h fa`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)} g fa`;
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
  try { res = await fetch(`/api${path}`, opt); } catch { throw new Error("Il server non risponde"); }
  if (res.status === 401 && path !== "/login") { state.authed = false; render(); throw new Error("Accedi di nuovo"); }
  const data = (res.headers.get("content-type") || "").includes("json") ? await res.json() : null;
  if (!res.ok) throw new Error(data?.detail && typeof data.detail === "string" ? data.detail : `Errore ${res.status}`);
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

function modal(title, html, buttons = `<button class="btn" data-close>Chiudi</button>`) {
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
      `<button class="btn" data-close>Annulla</button><button class="btn ${danger ? "danger" : "primary"}" data-ok>${esc(okLabel)}</button>`);
    $("[data-ok]", b).onclick = () => { closeModal(); resolve(true); };
    b.addEventListener("click", (e) => { if (e.target === b || e.target.closest("[data-close]")) resolve(false); });
  });
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast("Copiato"); }
  catch { prompt("Copia il link:", text); }
}

function linkModal(title, text, link) {
  const b = modal(title, `<p style="margin-top:0">${esc(text)}</p><input readonly value="${esc(link)}">`,
    `<button class="btn" data-close>Chiudi</button><button class="btn primary" data-copy>Copia link</button>`);
  $("[data-copy]", b).onclick = () => copy(link);
  $("input", b).onfocus = (e) => e.target.select();
}

// deltas: "↗ 6 %" like a report; bad=true when going up is bad (errors)
function delta(now, before, bad = false) {
  if (!before && !now) return `<span class="d same">–</span>`;
  if (!before) return `<span class="d up${bad ? " bad" : ""}">nuovo</span>`;
  const p = Math.round(((now - before) / before) * 100);
  if (p === 0) return `<span class="d same">stabile</span>`;
  return `<span class="d ${p > 0 ? "up" : "down"}${bad ? " bad" : ""}">${p > 0 ? "↗" : "↘"} ${Math.abs(p)} %</span>`;
}
const kpi = (label, now, before, bad, fmt = n) =>
  `<div class="kpi"><span class="l">${esc(label)}</span><span class="v">${fmt(now)}</span>${before === null ? "<span></span>" : delta(now, before, bad)}</div>`;

const KIND_IT = {
  setup: "Primo account", signup: "Nuova famiglia", family_created: "Famiglia in più", login: "Accesso",
  login_blocked: "Accesso bloccato", invite_sent: "Invito", invite_accepted: "Invito accettato",
  member_added: "Membro aggiunto", member_removed: "Membro rimosso", reset_requested: "Link password",
  reset_done: "Password cambiata", mail_sent: "E-mail", mail_failed: "E-mail fallita", reminders: "Promemoria",
  backup: "Backup", admin: "Admin", admin_login: "Accesso console",
};
const feed = (list, empty = "Ancora niente") => list.length
  ? `<ul class="feed">${list.map((e) => `<li><time title="${esc(dt(e.at))}">${esc(timeShort(e.at))}</time>
      <div><span class="k k-${esc(e.kind)}">${esc(KIND_IT[e.kind] || e.kind)}</span>${esc(e.text)}
      ${e.group_name && e.group_id ? ` · <a href="#/families/${e.group_id}">${esc(e.group_name)}</a>` : ""}</div></li>`).join("")}</ul>`
  : `<div class="empty">${esc(empty)}</div>`;

// ---------------------------------------------------------------- state & router
const state = { authed: null, dash: null, timer: null, countdown: 60 };
const NAV = [
  ["#/", "Dashboard", "dash"], ["#/families", "Famiglie", "family"], ["#/users", "Utenti", "users"],
  ["#/invitations", "Inviti e registrazioni", "invite"], ["#/mail", "E-mail", "mail"], ["#/settings", "Impostazioni", "settings"],
];
const NAV_SYS = [["#/backups", "Backup", "backup"], ["#/database", "Database", "db"], ["#/log", "Registro eventi", "log"], ["#/system", "Versione e sistema", "info"]];
const TITLES = { "": "Dashboard", families: "Famiglie", users: "Utenti", invitations: "Inviti e registrazioni", mail: "E-mail",
  settings: "Impostazioni", backups: "Backup", database: "Database", log: "Registro eventi", system: "Versione e sistema" };

async function render() {
  clearInterval(state.timer);
  if (state.authed === null) {
    try { await api("/dashboard"); state.authed = true; } catch { state.authed = false; }
  }
  if (!state.authed) return renderLogin();
  const [, route = "", id] = (location.hash || "#/").split("/");
  if (!$(".shell")) renderShell();
  $$(".nav a").forEach((a) => a.classList.toggle("on", a.getAttribute("href") === `#/${route}`));
  $(".top h1").textContent = TITLES[route] || "TotalMant Admin";
  $(".top .refresh").hidden = route !== "";
  $(".shell").classList.remove("open");
  const main = $("#page");
  main.innerHTML = `<div class="muted" style="padding:20px 0">Carico…</div>`;
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
  const link = ([h, l, i]) => `<a href="${h}">${I[i]}<span>${esc(l)}</span>${h === "#/invitations" ? `<span class="badge" id="badgeInv" hidden></span>` : ""}</a>`;
  $("#app").innerHTML = `<div class="shell">
    <aside class="side"><div class="brand"><img src="icon.svg" alt=""><div>TotalMant Admin<small>Console del server</small></div></div>
      <nav class="nav">${NAV.map(link).join("")}<h6>Sistema</h6>${NAV_SYS.map(link).join("")}</nav>
      <div class="foot"><div id="ver"></div><button id="logout">Esci</button></div></aside>
    <main class="main"><div class="top"><button class="iconbtn menu-btn" id="menu" aria-label="Menu">${I.menu}</button>
      <h1>Dashboard</h1><span class="date">${esc(new Date().toLocaleDateString(LOCALE, { weekday: "long", day: "numeric", month: "long" }))}</span>
      <span class="grow"></span>
      <span class="refresh"><span id="countdown"></span><button class="iconbtn" id="reload" title="Aggiorna" aria-label="Aggiorna">${I.refresh}</button></span></div>
      <div id="page"></div></main></div>`;
  $("#logout").onclick = async () => { try { await api("/logout", { method: "POST" }); } catch { /* gone anyway */ } state.authed = false; render(); };
  $("#menu").onclick = () => $(".shell").classList.toggle("open");
  $("#reload").onclick = () => render();
}

function renderLogin() {
  $("#app").innerHTML = `<div class="login"><form class="box" id="lf">
    <div class="brand"><img src="icon.svg" alt=""><div>TotalMant Admin<small>Console del server</small></div></div>
    <p>Accesso riservato all'amministratore del server.</p>
    <label class="field"><span>Password admin</span><input type="password" name="pw" autocomplete="current-password" required autofocus></label>
    <button class="btn primary">Entra</button>
    <div class="note" id="note">La password è <code>ADMIN_PASSWORD</code> nel file <code>.env</code> sul NAS.</div></form></div>`;
  api("/status").then((s) => {
    if (!s.configured) $("#note").innerHTML = `<b style="color:var(--down)">ADMIN_PASSWORD non è impostata</b> (almeno 10 caratteri) nel <code>.env</code>: impostala e riavvia il container <code>admin</code>.`;
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
  $("#ver").textContent = `Versione ${sv.version}`;
  const inv = $("#badgeInv"); if (inv) { inv.textContent = tot.open_invites; inv.hidden = !tot.open_invites; }
  const monthName = new Date().toLocaleDateString(LOCALE, { month: "long" });
  const signup = { open: "aperta", code: "con codice", closed: "chiusa" }[sv.signup] || sv.signup;
  main.innerHTML = `<div class="grid2">
    <div class="stack">
      <section class="panel"><header><h2>Oggi</h2><span class="sub">rispetto a ieri</span></header>
        <div class="kpis">
          ${kpi("Nuove famiglie", t.families.now, t.families.before)}
          ${kpi("Accessi", t.logins.now, t.logins.before)}
          ${kpi("Nuovi utenti", t.users.now, t.users.before)}
          ${kpi("Attività completate", t.tasks_done.now, t.tasks_done.before)}
          ${kpi("E-mail inviate", t.mails.now, t.mails.before)}
          ${kpi("E-mail fallite", t.mail_errors.now, t.mail_errors.before, true)}
        </div></section>
      <section class="panel"><header><h2>Vai a</h2></header>
        <div class="tiles">
          <a class="tile" href="#/families">${I.family}Famiglie</a><a class="tile" href="#/users">${I.users}Utenti</a>
          <a class="tile" href="#/invitations">${I.invite}Inviti</a><a class="tile" href="#/mail">${I.mail}E-mail</a>
          <a class="tile" href="#/backups">${I.backup}Backup</a><a class="tile" href="#/database">${I.db}Database</a>
          <a class="tile" href="#/settings">${I.settings}Impostazioni</a><a class="tile" href="#/log">${I.log}Registro</a>
        </div></section>
      <section class="panel"><header><h2>Ultime attività</h2><span class="grow"></span><a class="small" href="#/log">Tutto il registro →</a></header>
        ${feed(d.recent, "Ancora nessun evento: compariranno qui registrazioni, inviti, e-mail e backup.")}</section>
    </div>
    <div class="stack">
      <section class="panel"><header><h2>Finora a ${esc(monthName)}</h2><span class="sub">rispetto allo stesso periodo del mese scorso</span></header>
        <div class="kpis one">
          ${kpi("Famiglie attive", mo.active_families.now, mo.active_families.before)}
          ${kpi("Nuove famiglie", mo.new_families.now, mo.new_families.before)}
          ${kpi("Nuovi utenti", mo.new_users.now, mo.new_users.before)}
          ${kpi("Attività completate", mo.tasks_done.now, mo.tasks_done.before)}
        </div></section>
      <section class="panel"><header><h2>Totale</h2></header>
        <div class="kpis one">
          ${kpi("Famiglie", tot.families, null)}${kpi("Utenti", tot.users, null)}
          ${tot.blocked ? kpi("Utenti bloccati", tot.blocked, null) : ""}
          ${kpi("Oggetti (case, auto, barche …)", tot.things, null)}${kpi("Attività attive", tot.tasks, null)}
          ${kpi("Inviti aperti", tot.open_invites, null)}
          ${kpi(`Allegati (${n(tot.files)} file)`, tot.files_size, null, false, bytes)}
        </div></section>
      <section class="panel"><header><h2>Server</h2></header>
        <div class="links">
          <a href="#/settings">${I.settings}Registrazione nuove famiglie: <b>&nbsp;${esc(signup)}</b></a>
          <a href="#/mail">${I.mail}E-mail (SMTP): <b>&nbsp;${sv.mail ? "attiva" : "non configurata"}</b></a>
          <a href="#/backups">${I.backup}Ultimo backup: <b>&nbsp;${esc(ago(sv.last_backup))}</b></a>
          <a href="#/log">${I.log}Ultimi promemoria: <b>&nbsp;${esc(ago(sv.last_reminders))}</b></a>
        </div></section>
      <section class="panel"><header><h2>Azioni rapide</h2></header>
        <div class="actions">
          <button class="btn primary" id="qBackup">${I.backup}Backup ora</button>
          <button class="btn" id="qMail">${I.send}E-mail di prova</button>
          <button class="btn" id="qCode">${I.key}Nuovo codice di registrazione</button>
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
    if (cd) cd.textContent = `Aggiorno tra ${state.countdown} s`;
    if (state.countdown <= 0 && !$(".back")) render();
  }, 1000);
}

async function doBackup() {
  toast("Backup in corso…");
  try { const r = await api("/backups", { method: "POST" }); toast(`Backup fatto: ${r.name} (${bytes(r.size)})`); render(); }
  catch (e) { fail(e); }
}

function testMailDialog() {
  const b = modal("E-mail di prova", `<label class="field"><span>Manda a</span><input type="email" id="to" placeholder="nome@esempio.no"></label>`,
    `<button class="btn" data-close>Annulla</button><button class="btn primary" data-ok>Invia</button>`);
  $("#to", b).focus();
  $("[data-ok]", b).onclick = async () => {
    const to = $("#to", b).value.trim(); if (!to) return;
    try { const r = await api("/mail/test", { method: "POST", body: { to } }); closeModal(); r.ok ? toast(`Inviata a ${to}`) : fail(new Error(r.error)); }
    catch (e) { fail(e); }
  };
}

async function newCodeDialog() {
  try {
    const { code } = await api("/settings/new-code");
    const ok = await confirmBox("Nuovo codice di registrazione",
      `Chi registra una nuova famiglia dovrà scrivere questo codice:<br><br><code style="font-size:18px">${esc(code)}</code><br><br>Il codice vecchio smette di funzionare.`, "Attiva codice", false);
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
  main.innerHTML = `<div class="toolbar"><input type="search"><span class="muted small">${n(list.length)} famiglie</span></div>
    <section class="panel"><div class="tablewrap"><table class="t"><thead><tr><th>Famiglia</th><th>Proprietario</th>
      <th class="num">Membri</th><th class="num">Oggetti</th><th class="num">Attività</th><th>Creata</th><th>Ultima attività</th></tr></thead>
      <tbody>${list.map((f) => `<tr class="click" data-id="${f.id}"><td><b>${esc(f.name)}</b></td>
        <td>${f.owner ? `${esc(f.owner.name)}<div class="small muted">${esc(f.owner.email)}</div>` : `<span class="pill bad">senza proprietario</span>`}</td>
        <td class="num">${f.members}</td><td class="num">${f.things}</td><td class="num">${f.tasks}</td>
        <td>${day(f.created_at)}</td><td>${esc(ago(f.last_activity))}</td></tr>`).join("")}</tbody></table></div>
      ${list.length ? "" : `<div class="empty">Nessuna famiglia</div>`}</section>`;
  searchBox(main, "Cerca famiglia, proprietario o e-mail", list.map((f) => `${f.name} ${f.owner?.name || ""} ${f.owner?.email || ""}`));
  $$("tr[data-id]", main).forEach((tr) => tr.onclick = () => { location.hash = `#/families/${tr.dataset.id}`; });
}

async function pageFamily(main, id) {
  const f = await api(`/families/${id}`);
  const c = f.counts;
  const kinds = Object.entries(c.things_by_kind).map(([k, v]) => `${v} ${esc(k)}`).join(", ");
  $(".top h1").textContent = f.name;
  main.innerHTML = `<a class="crumb" href="#/families">← Famiglie</a>
    <div class="headline"><h2>${esc(f.name)}</h2><span class="muted">creata ${day(f.created_at)}</span><span class="grow" style="flex:1"></span>
      <button class="btn danger" id="del">Elimina famiglia</button></div>
    <div class="grid2"><div class="stack">
      <section class="panel"><header><h2>Membri</h2><span class="sub">${f.members.length}</span></header>
        <div class="tablewrap"><table class="t"><thead><tr><th>Nome</th><th>Ruolo</th><th>Ultimo accesso</th><th></th></tr></thead><tbody>
        ${f.members.map((u) => `<tr><td><b>${esc(u.name)}</b>${u.blocked ? ` <span class="pill blocked">bloccato</span>` : ""}
            <div class="small muted">${esc(u.email)}${u.other_families ? ` · anche in ${u.other_families} altra/e` : ""}</div></td>
          <td><span class="pill ${u.role_key === "owner" ? "owner" : ""}">${esc(u.role)}</span></td>
          <td>${esc(ago(u.last_login))}</td><td class="act"><a href="#/users" data-find="${esc(u.email)}">Utente →</a></td></tr>`).join("")}
        </tbody></table></div></section>
      <section class="panel"><header><h2>Eventi della famiglia</h2></header>${feed(f.events)}</section>
    </div><div class="stack">
      <section class="panel"><header><h2>Contenuto</h2><span class="sub">solo i numeri, non i dati</span></header>
        <div class="kpis one">${kpi("Oggetti", c.things, null)}${kinds ? `<div class="kpi"><span class="l small muted">${kinds}</span><span></span><span></span></div>` : ""}
          ${kpi("Attività attive", c.tasks, null)}${kpi("Lavori registrati", c.done, null)}${kpi("Fornitori", c.vendors, null)}
          ${kpi(`Allegati (${n(c.files)} file)`, c.files_size, null, false, bytes)}</div></section>
      <section class="panel"><header><h2>Ruoli</h2></header><div class="kpis one">${f.roles.map((r) =>
        `<div class="kpi"><span class="l">${esc(r.name)}</span><span class="v">${r.permissions == null ? "tutto" : `${r.permissions} permessi`}</span><span></span></div>`).join("")}</div></section>
      <section class="panel"><header><h2>Inviti aperti</h2></header>${f.invites.length ? `<div class="kpis one">${f.invites.map((i) =>
        `<div class="kpi"><span class="l">${esc(i.email)} <span class="pill">${esc(i.role)}</span></span><span class="small muted">scade ${day(i.expires_at)}</span><span></span></div>`).join("")}</div>`
        : `<div class="empty">Nessuno</div>`}</section>
    </div></div>`;
  $$("[data-find]", main).forEach((a) => a.onclick = () => { state.findUser = a.dataset.find; });
  $("#del").onclick = async () => {
    const ok = await confirmBox(`Eliminare ${f.name}?`,
      `Vengono cancellati <b>tutti</b> i suoi oggetti, attività, storico e allegati (${n(c.things)} oggetti, ${n(c.files)} file).
       I membri che non sono in altre famiglie perdono anche l'account. <b>Non si può annullare</b>: fai prima un backup se hai dubbi.`, "Elimina per sempre");
    if (!ok) return;
    try {
      const r = await api(`/families/${id}`, { method: "DELETE" });
      toast(r.accounts_deleted.length ? `Eliminata, con ${r.accounts_deleted.length} account` : "Famiglia eliminata");
      location.hash = "#/families";
    } catch (e) { fail(e); }
  };
}

// ---------------------------------------------------------------- users
async function pageUsers(main) {
  const list = await api("/users");
  main.innerHTML = `<div class="toolbar"><input type="search"><span class="muted small">${n(list.length)} utenti</span></div>
    <section class="panel"><div class="tablewrap"><table class="t"><thead><tr><th>Utente</th><th>Famiglie e ruoli</th>
      <th>Registrato</th><th>Ultimo accesso</th><th></th></tr></thead>
      <tbody>${list.map((u) => `<tr><td><b>${esc(u.name)}</b>${u.blocked ? ` <span class="pill blocked">bloccato</span>` : ""}${u.is_admin ? ` <span class="pill warn" title="Amministratore storico del server">admin</span>` : ""}
          <div class="small muted">${esc(u.email)}</div></td>
        <td>${u.families.map((f) => `<a class="pill ${f.role_key === "owner" ? "owner" : ""}" href="#/families/${f.id}">${esc(f.name)} · ${esc(f.role)}</a>`).join("") || `<span class="pill bad">nessuna famiglia</span>`}</td>
        <td>${day(u.created_at)}</td><td>${esc(ago(u.last_login))}</td>
        <td class="act"><button class="btn small" data-reset="${u.id}" title="Link per scegliere una nuova password">${I.key}Link password</button>
          <button class="btn small" data-block="${u.id}">${u.blocked ? "Sblocca" : "Blocca"}</button>
          <button class="btn small danger" data-del="${u.id}">Elimina</button></td></tr>`).join("")}</tbody></table></div></section>`;
  searchBox(main, "Cerca nome, e-mail o famiglia", list.map((u) => `${u.name} ${u.email} ${u.families.map((f) => f.name).join(" ")}`));
  if (state.findUser) { const i = $(".toolbar input", main); i.value = state.findUser; i.oninput(); state.findUser = null; }
  const byId = (b, k) => list.find((u) => u.id === Number(b.dataset[k]));
  $$("[data-reset]", main).forEach((b) => b.onclick = async () => {
    const u = byId(b, "reset");
    try { const r = await api(`/users/${u.id}/reset-link`, { method: "POST" });
      linkModal(`Link password per ${u.name}`, `Manda questo link a ${u.email} (SMS, WhatsApp …). Funziona una volta, per ${r.hours} ore; i link vecchi smettono di funzionare.`, r.link);
    } catch (e) { fail(e); }
  });
  $$("[data-block]", main).forEach((b) => b.onclick = async () => {
    const u = byId(b, "block");
    if (!u.blocked && !(await confirmBox(`Bloccare ${u.name}?`, "Non potrà più accedere, viene disconnesso subito da tutti i dispositivi e non riceve promemoria. I suoi dati restano. Puoi sbloccarlo quando vuoi.", "Blocca"))) return;
    try { await api(`/users/${u.id}/block`, { method: "POST", body: { blocked: !u.blocked } }); toast(u.blocked ? "Sbloccato" : "Bloccato"); render(); }
    catch (e) { fail(e); }
  });
  $$("[data-del]", main).forEach((b) => b.onclick = async () => {
    const u = byId(b, "del");
    const lonely = u.families.filter((f) => f.role_key === "owner");
    const ok = await confirmBox(`Eliminare ${u.name}?`,
      `L'account ${esc(u.email)} viene cancellato. ${lonely.length ? `Le famiglie dove è l'<b>unico membro</b> (${lonely.map((f) => esc(f.name)).join(", ")}) vengono cancellate con tutti i dati. ` : ""}<b>Non si può annullare.</b>`, "Elimina per sempre");
    if (!ok) return;
    try { const r = await api(`/users/${u.id}`, { method: "DELETE" }); toast(r.families_deleted.length ? `Eliminato, con ${r.families_deleted.join(", ")}` : "Account eliminato"); render(); }
    catch (e) { fail(e); }
  });
}

// ---------------------------------------------------------------- invitations
async function pageInvites(main) {
  const d = await api("/invitations");
  const lbl = { open: "aperto", accepted: "accettato", expired: "scaduto" };
  const open = d.invitations.filter((i) => i.status === "open");
  main.innerHTML = `<div class="grid2"><section class="panel"><header><h2>Inviti</h2><span class="sub">${open.length} aperti</span></header>
      ${d.invitations.length ? `<div class="tablewrap"><table class="t"><thead><tr><th>E-mail</th><th>Famiglia</th><th>Stato</th><th>Inviato</th><th></th></tr></thead><tbody>
      ${d.invitations.map((i) => `<tr><td><b>${esc(i.email)}</b><div class="small muted">${esc(i.role)}${i.invited_by ? ` · da ${esc(i.invited_by)}` : ""}</div></td>
        <td><a href="#/families/${i.group_id}">${esc(i.family)}</a></td>
        <td><span class="pill ${i.status}">${lbl[i.status]}</span><div class="small muted">${i.status === "open" ? `scade ${day(i.expires_at)}` : i.accepted_at ? day(i.accepted_at) : ""}</div></td>
        <td>${day(i.created_at)}</td>
        <td class="act">${i.status === "open" ? `<button class="btn small danger" data-cancel="${i.id}">Annulla</button>` : ""}</td></tr>`).join("")}
      </tbody></table></div>` : `<div class="empty">Nessun invito ancora</div>`}</section>
    <section class="panel"><header><h2>Registrazioni</h2><span class="sub">famiglie nuove</span></header>${feed(d.signups, "Nessuna registrazione ancora")}</section></div>`;
  $$("[data-cancel]", main).forEach((b) => b.onclick = async () => {
    if (!(await confirmBox("Annullare l'invito?", "Il link nell'e-mail smette di funzionare.", "Annulla invito"))) return;
    try { await api(`/invitations/${b.dataset.cancel}`, { method: "DELETE" }); render(); } catch (e) { fail(e); }
  });
}

// ---------------------------------------------------------------- e-mail
async function pageMail(main) {
  const d = await api("/mail");
  main.innerHTML = `<div class="grid2"><div class="stack">
      <section class="panel"><header><h2>Impostazioni SMTP</h2><span class="sub">dal file .env</span></header>
        <dl class="facts"><dt>Stato</dt><dd>${d.configured ? `<span class="pill ok">attiva</span>` : `<span class="pill bad">non configurata</span>`}</dd>
          <dt>Server</dt><dd class="mono">${esc(d.host || "–")}${d.host ? `:${d.port}` : ""}</dd><dt>Utente</dt><dd class="mono">${esc(d.user || "–")}</dd>
          <dt>Mittente</dt><dd class="mono">${esc(d.sender || "–")}</dd></dl>
        ${d.configured ? "" : `<div class="body small muted">Senza SMTP gli inviti si mandano copiando il link, il "Glemt passord" non può inviare niente e i promemoria finiscono solo nel log. Imposta <code>SMTP_HOST</code>, <code>SMTP_PORT</code>, <code>SMTP_USER</code>, <code>SMTP_PASSWORD</code> e <code>SMTP_FROM</code> nel <code>.env</code> e riavvia.</div>`}
        <div class="actions"><button class="btn primary" id="test">${I.send}Invia e-mail di prova</button></div></section>
    </div>
    <section class="panel"><header><h2>Registro e-mail</h2><span class="sub">ultime 100</span></header>${feed(d.log, "Nessuna e-mail ancora")}</section></div>`;
  $("#test").onclick = () => testMailDialog();
}

// ---------------------------------------------------------------- settings
async function pageSettings(main) {
  const s = await api("/settings");
  const opt = (v, title, text) => `<label class="radio"><input type="radio" name="mode" value="${v}" ${s.signup_mode === v ? "checked" : ""}><span><b>${title}</b><span class="small muted">${text}</span></span></label>`;
  main.innerHTML = `<div class="grid2"><section class="panel"><header><h2>Registrazione di nuove famiglie</h2>
      <span class="sub">${s.signup_from === "admin" ? "scelta da qui" : "dal file .env"}</span></header><div class="body">
      ${opt("open", "Aperta", "Chiunque raggiunga l'app può registrare una famiglia e diventarne proprietario.")}
      ${opt("code", "Con codice", "Serve un codice che dai tu alle famiglie che vuoi.")}
      ${opt("closed", "Chiusa", "Nessuna registrazione: si entra solo con un invito.")}
      <label class="field" id="codeField" ${s.signup_mode === "code" ? "" : "hidden"}><span>Codice</span>
        <span style="display:flex;gap:8px"><input id="code" value="${esc(s.signup_code)}" style="flex:1"><button class="btn" type="button" id="gen">Genera</button></span></label>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" id="save">Salva</button>
        ${s.signup_from === "admin" ? `<button class="btn" id="env">Torna al valore del .env</button>` : ""}</div></div></section>
    <section class="panel"><header><h2>Altri valori</h2><span class="sub">si cambiano nel .env e con un riavvio</span></header>
      <dl class="facts"><dt>Indirizzo dell'app</dt><dd class="mono">${esc(s.public_url)}</dd>
        <dt>Validità inviti</dt><dd>${s.invite_days} giorni <span class="muted mono">INVITE_DAYS</span></dd>
        <dt>Validità link password</dt><dd>${s.reset_hours} ore <span class="muted mono">RESET_HOURS</span></dd>
        <dt>Sessione admin</dt><dd>${s.session_hours} ore <span class="muted mono">ADMIN_SESSION_HOURS</span></dd>
        <dt>Reti ammesse alla console</dt><dd class="mono small">${esc(s.allow_nets)}</dd></dl></section></div>`;
  $$('input[name="mode"]', main).forEach((r) => r.onchange = () => { $("#codeField").hidden = r.value !== "code" || !r.checked; });
  $("#gen").onclick = async () => { try { $("#code").value = (await api("/settings/new-code")).code; } catch (e) { fail(e); } };
  $("#save").onclick = async () => {
    const mode = $('input[name="mode"]:checked', main)?.value;
    try { await api("/settings/signup", { method: "PUT", body: { mode, code: $("#code").value } }); toast("Salvato"); render(); } catch (e) { fail(e); }
  };
  $("#env")?.addEventListener("click", async () => {
    try { await api("/settings/signup", { method: "PUT", body: { mode: "env" } }); toast("Ora vale il .env"); render(); } catch (e) { fail(e); }
  });
}

// ---------------------------------------------------------------- backups
async function pageBackups(main) {
  const d = await api("/backups");
  main.innerHTML = `<div class="grid2"><section class="panel"><header><h2>Backup del database</h2><span class="sub">${d.files.length} file · ne restano gli ultimi 30</span>
      <span class="grow"></span><button class="btn primary small" id="now">${I.backup}Backup ora</button></header>
      ${d.files.length ? `<div class="tablewrap"><table class="t"><thead><tr><th>File</th><th>Data</th><th class="num">Dimensione</th><th></th></tr></thead><tbody>
      ${d.files.map((f) => `<tr><td class="mono">${esc(f.name)}</td><td>${dt(f.at)}</td><td class="num">${bytes(f.size)}</td>
        <td class="act"><a class="btn small" href="/api/backups/${encodeURIComponent(f.name)}">Scarica</a></td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty">Nessun backup ancora</div>`}</section>
    <section class="panel"><header><h2>Dove e come</h2></header>
      <dl class="facts"><dt>Cartella</dt><dd class="mono small">${esc(d.dir)}</dd><dt>Database</dt><dd>${esc(d.kind)}</dd>
        <dt>Spazio libero</dt><dd>${bytes(d.disk_free)} di ${bytes(d.disk_total)}</dd></dl>
      <div class="body small muted">Sul NAS questa è la cartella <code>backup/</code> del progetto: qui finiscono anche i backup di <code>nas/backup.sh</code> (notturno) e di <code>nas/update.sh</code>.
        Il ripristino non si fa da qui, apposta: vedi la guida in <code>GUIDA_AGGIORNAMENTI.md</code>.</div></section></div>`;
  $("#now").onclick = () => doBackup();
}

// ---------------------------------------------------------------- database & system
async function pageDatabase(main) {
  const s = await api("/system");
  const adminer = s.adminer_url || `${location.protocol}//${location.hostname}:8082/?pgsql=db&username=totalmaint&db=totalmaint`;
  main.innerHTML = `<div class="grid2"><section class="panel"><header><h2>Tabelle</h2><span class="sub">${esc(s.database)} · ${bytes(s.database_size)}</span></header>
      <div class="tablewrap"><table class="t"><thead><tr><th>Tabella</th><th class="num">Righe</th></tr></thead><tbody>
      ${s.tables.map((t) => `<tr><td class="mono">${esc(t.name)}</td><td class="num">${n(t.rows)}</td></tr>`).join("")}</tbody></table></div></section>
    <section class="panel"><header><h2>Adminer</h2><span class="sub">accesso diretto alle tabelle</span></header>
      <div class="body"><p style="margin-top:0">Per vedere o correggere i dati riga per riga si usa <b>Adminer</b>, sul NAS alla porta <code>8082</code>.
        Accesso: sistema <i>PostgreSQL</i>, server <code>db</code>, utente <code>totalmaint</code>, password = <code>POSTGRES_PASSWORD</code> del <code>.env</code>.</p>
        <p class="small muted">Attenzione: lì le modifiche sono immediate e senza controlli. Fai prima un backup.</p>
        <a class="btn primary" href="${esc(adminer)}" target="_blank" rel="noopener">${I.ext}Apri Adminer</a></div></section></div>`;
}

async function pageSystem(main) {
  const s = await api("/system");
  main.innerHTML = `<div class="grid2"><section class="panel"><header><h2>Versione e sistema</h2></header>
    <dl class="facts"><dt>TotalMaint</dt><dd><b>${esc(s.version)}</b></dd><dt>Python</dt><dd>${esc(s.python)}</dd><dt>Sistema</dt><dd class="small">${esc(s.platform)}</dd>
      <dt>Database</dt><dd>${esc(s.database)} · <span class="mono small">${esc(s.database_where)}</span></dd><dt>Dimensione database</dt><dd>${bytes(s.database_size)}</dd>
      <dt>Allegati</dt><dd>${n(s.uploads)} file · ${bytes(s.uploads_size)}</dd><dt>Console avviata</dt><dd>${dt(s.started_at)}</dd><dt>Fuso orario</dt><dd>${esc(s.timezone)}</dd></dl></section>
    <section class="panel"><header><h2>Log del server</h2></header><div class="body small">
      I log tecnici dei container li vedi in DSM → Container Manager → Container → <code>app</code> o <code>admin</code> → Registro,
      oppure via SSH con <code>sudo docker compose logs --tail 100 app</code>. Gli eventi utili (registrazioni, e-mail, backup) sono nel <a href="#/log">Registro eventi</a>.</div></section></div>`;
}

async function pageLog(main, before = null, kind = state.logKind || "") {
  const d = await api(`/events?${kind ? `kind=${kind}&` : ""}${before ? `before=${before}` : ""}`);
  const opts = Object.keys(d.kinds).map((k) => `<option value="${k}" ${k === kind ? "selected" : ""}>${esc(KIND_IT[k] || k)}</option>`).join("");
  if (!before) {
    main.innerHTML = `<div class="toolbar"><select id="kind"><option value="">Tutti gli eventi</option>${opts}</select></div>
      <section class="panel"><div id="list"></div></section><div style="margin-top:10px"><button class="btn" id="more" hidden>Mostra altri</button></div>`;
    $("#kind").onchange = (e) => { state.logKind = e.target.value; pageLog(main, null, e.target.value); };
  }
  const list = $("#list");
  list.insertAdjacentHTML("beforeend", feed(d.events, "Nessun evento"));
  const last = d.events[d.events.length - 1];
  $("#more").hidden = d.events.length < 100;
  $("#more").onclick = () => pageLog(main, last.id, kind);
}

render();
