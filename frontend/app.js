/* TotalMaint frontend – plain JavaScript, no build step.
   Talks to the FastAPI backend under /api. Works as a PWA (installable on phone and desktop). */
"use strict";

// ---------------------------------------------------------------- state & helpers
// Languages: Norwegian, English, Italian. Unknown or missing → the browser's language, else English.
const LANG_OPTIONS = [["no", "Norsk"], ["en", "English"], ["it", "Italiano"]];
function pickLang() {
  let saved = null;
  try { saved = localStorage.getItem("tm_lang"); } catch { /* storage off */ }
  if (LANG_OPTIONS.some(([k]) => k === saved)) return saved;
  const nav = navigator.language || "";
  return /^(nb|nn|no)/i.test(nav) ? "no" : /^it/i.test(nav) ? "it" : "en";
}
const langSwitch = () => `<div class="lang-switch">${LANG_OPTIONS.map(([k, label]) =>
  `<button class="btn small ${state.lang === k ? "primary" : ""}" data-lang="${k}">${label}</button>`).join("\n      ")}</div>`;
const state = {
  token: localStorage.getItem("tm_token"),
  user: null,
  lang: pickLang(),
  users: [],
  vendors: [],
  mine: localStorage.getItem("tm_mine") === "1",
  assetFilter: Number(localStorage.getItem("tm_asset")) || null,
  assetTab: "tasks",
  calMonth: null,
};

const T = (key, ...args) => {
  const v = (I18N[state.lang] && I18N[state.lang][key]) ?? I18N.en[key] ?? key;
  return typeof v === "function" ? v(...args) : v;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const locale = () => ({ no: "nb-NO", it: "it-IT" }[state.lang] || "en-GB");
const todayIso = () => new Date().toLocaleDateString("sv-SE");
const daysFromToday = (iso) => Math.round((Date.parse(iso) - Date.parse(todayIso())) / 864e5);
const fmtDate = (iso) => (iso ? new Date(iso + "T12:00:00").toLocaleDateString(locale(), { day: "numeric", month: "short", year: "numeric" }) : "");
const money = (n) => (n == null ? "" : `${Math.round(n).toLocaleString(locale())} kr`);

// What the user's role allows in the active group. The server checks every call; this only
// hides what the user can't use: any element with data-perm="tasks.create" etc. is removed
// as soon as it appears on the page, when the role doesn't have that permission.
const can = (perm) => !!state.user?.permissions?.includes(perm);
function applyPerms(root) {
  if (root.matches?.("[data-perm]") && !can(root.dataset.perm)) { root.remove(); return; }
  root.querySelectorAll?.("[data-perm]").forEach((el) => { if (!can(el.dataset.perm)) el.remove(); });
}
new MutationObserver((muts) => muts.forEach((m) => m.addedNodes.forEach((n) => { if (n.nodeType === 1) applyPerms(n); })))
  .observe(document.documentElement, { childList: true, subtree: true });

function stamp(iso) {
  if (!iso) return { d: "–", m: "" };
  const dt = new Date(iso + "T12:00:00");
  const sameYear = dt.getFullYear() === new Date().getFullYear();
  const m = dt.toLocaleDateString(locale(), { month: "short" }).replace(".", "");
  return { d: dt.getDate(), m: sameYear ? m : `${m} ${String(dt.getFullYear()).slice(2)}` };
}

function whenText(t) {
  if (!t.active) return T("inactive");
  const byCounter = counterWhen(t);
  if (!t.next_due) return byCounter || T("no_date");
  const n = daysFromToday(t.next_due);
  // the counter is what makes it due (date still far away): say that
  if (byCounter && t.status !== "ok" && n > t.remind_days_before) return byCounter;
  if (n < 0) return T("days_overdue", -n);
  if (n === 0) return T("today");
  if (n === 1) return T("tomorrow");
  return T("in_days", n);
}

const unitShort = (u) => (u === "km" ? "km" : u === "hours" ? T("hours_short") : "");
const num = (n) => Math.round(n).toLocaleString(locale());
const counterVal = (n, u) => `${num(n)} ${unitShort(u)}`;

function intervalText(t) {
  const byTime = t.interval_unit !== "none" && t.interval_value ? T("every_text", t.interval_value, t.interval_unit) : "";
  const byCounter = t.counter_unit && t.counter_interval ? T("every_counter", counterVal(t.counter_interval, t.counter_unit)) : "";
  if (byTime && byCounter) return T("whichever_first", byTime, byCounter);
  return byTime || byCounter || T("unit_none");
}

// "50 h left" / "15 h over", or null when the task doesn't follow a counter
function counterWhen(t) {
  if (t.counter_left == null) return null;
  return t.counter_left < 0 ? T("counter_over", counterVal(-t.counter_left, t.counter_unit)) : T("counter_left", counterVal(t.counter_left, t.counter_unit));
}

async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  let res;
  try {
    res = await fetch(path, { method, headers, body: payload });
  } catch {
    throw new Error(T("error_generic"));
  }
  if (res.status === 401 && state.token) { logout(); throw new Error("401"); }
  if (!res.ok) {
    let msg = T("error_generic");
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = j.detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join(", ");
    } catch { /* not json */ }
    throw new Error(msg);
  }
  const type = res.headers.get("content-type") || "";
  return type.includes("application/json") ? res.json() : res;
}

let toastTimer;
function toast(msg, error = false) {
  let el = $(".toast");
  if (!el) { el = document.createElement("div"); el.className = "toast"; el.setAttribute("role", "status"); document.body.append(el); }
  el.textContent = msg;
  el.classList.toggle("error", error);
  el.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 3200);
}
const fail = (e) => { if (e.message !== "401") toast(e.message, true); };

// ---------------------------------------------------------------- icons (simple line icons)
const svg = (p) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
const ICON = {
  overview: svg('<path d="M4 5h16M4 12h16M4 19h10"/>'),
  things: svg('<path d="M3 10.5 12 4l9 6.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>'),
  calendar: svg('<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>'),
  cart: svg('<path d="M3 4h2.5l2.2 11h10.6L20.5 8H7"/><circle cx="9.5" cy="19.5" r="1.3"/><circle cx="17" cy="19.5" r="1.3"/>'),
  settings: svg('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>'),
  check: svg('<path d="m5 12.5 4.5 4.5L19 7.5"/>'),
  plus: svg('<path d="M12 5v14M5 12h14"/>'),
  home: svg('<path d="M3 10.5 12 4l9 6.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>'),
  car: svg('<path d="M5 16V11l2-5h10l2 5v5"/><path d="M3.5 16h17v3h-3v-1.5h-11V19h-3z"/><circle cx="7.5" cy="13" r=".8"/><circle cx="16.5" cy="13" r=".8"/>'),
  boat: svg('<path d="M3 15h18l-2.5 4.5h-13z"/><path d="M12 3v12M12 4l6 8h-6"/>'),
  cabin: svg('<path d="M2.5 12 12 4l9.5 8"/><path d="M5 10v10h14V10"/><path d="M10 20v-5h4v5"/><path d="M16 6V3.5h2v4"/>'),
  other: svg('<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 12h6M12 9v6"/>'),
  bicycle: svg('<circle cx="6" cy="16" r="3.5"/><circle cx="18" cy="16" r="3.5"/><path d="M6 16l4-7h6l2 7M10 9l3 7h-1M15 6h2l1 3M9 7h3"/>'),
  motorcycle: svg('<circle cx="5.5" cy="16.5" r="3"/><circle cx="18.5" cy="16.5" r="3"/><path d="M5.5 16.5 9 12h6l3.5 4.5M9 12l1.5-3h4.5l1 3M15.5 6.5h2l1 4"/>'),
  scooter: svg('<circle cx="5.5" cy="18" r="2"/><circle cx="18.5" cy="18" r="2"/><path d="M7.5 18h9M16.5 18 14.5 4.5M12.5 4.5h4"/>'),
  file: svg('<path d="M14 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8z"/><path d="M14 3v5h5"/>'),
  template: svg('<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9h8M8 13h8M8 17h5"/>'),
  x: svg('<path d="M6 6l12 12M18 6 6 18"/>'),
  eye: svg('<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
  eyeOff: svg('<path d="M3 3l18 18"/><path d="M10.6 5.1A10.7 10.7 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4.1M6.6 6.6C3.8 8.4 2 12 2 12s3.6 7 10 7c1.9 0 3.5-.6 4.9-1.4"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>'),
  print: svg('<path d="M7 9V3.5h10V9"/><rect x="3.5" y="9" width="17" height="8" rx="1.5"/><path d="M7 14.5h10V20.5H7z"/>'),
};
const kindIcon = (k) => ICON[k] || ICON.other;

// ---------------------------------------------------------------- modal & form builder
function closeModal() { $(".modal-back")?.remove(); }

function modal({ title, html, footer = "", onMount }) {
  closeModal();
  const back = document.createElement("div");
  back.className = "modal-back";
  back.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}">
    <header><h2>${esc(title)}</h2><button class="btn ghost small" data-close aria-label="${esc(T("close"))}">${ICON.x}</button></header>
    <div class="content">${html}</div>${footer ? `<footer>${footer}</footer>` : ""}</div>`;
  back.addEventListener("click", (e) => { if (e.target === back || e.target.closest("[data-close]")) closeModal(); });
  document.body.append(back);
  const first = $("input, select, textarea", back);
  if (first && window.matchMedia("(hover: hover)").matches) first.focus();
  onMount?.(back);
  return back;
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
// Show / hide password: the eye button next to every password field
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-pw]");
  if (!b) return;
  e.preventDefault();
  const input = b.parentElement.querySelector("input");
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  b.innerHTML = show ? ICON.eyeOff : ICON.eye;
  b.setAttribute("aria-pressed", String(show));
  const label = T(show ? "hide_password" : "show_password");
  b.setAttribute("aria-label", label); b.title = label;
  input.focus();
});

function fieldHtml(f, value) {
  const v = value ?? f.default ?? "";
  const id = `f_${f.name}`;
  if (f.type === "checkbox") {
    return `<label class="check"><input type="checkbox" id="${id}" name="${f.name}" ${v ? "checked" : ""}><span>${esc(f.label)}</span></label>`;
  }
  let input;
  if (f.type === "textarea") input = `<textarea id="${id}" name="${f.name}">${esc(v)}</textarea>`;
  else if (f.type === "select") {
    input = `<select id="${id}" name="${f.name}">${f.options.map(([ov, ol]) =>
      `<option value="${esc(ov)}" ${String(ov) === String(v ?? "") ? "selected" : ""}>${esc(ol)}</option>`).join("")}</select>`;
  } else if (f.type === "file") input = `<input type="file" id="${id}" name="${f.name}" multiple>`;
  else {
    const extra = f.type === "number" ? `step="${f.step || "any"}" inputmode="decimal"` : "";
    input = `<input type="${f.type || "text"}" id="${id}" name="${f.name}" value="${esc(v)}" ${f.required ? "required" : ""} ${extra} ${f.autocomplete ? `autocomplete="${f.autocomplete}"` : ""} ${f.placeholder ? `placeholder="${esc(f.placeholder)}"` : ""}>`;
    if (f.type === "password") {
      input = `<span class="pw-wrap">${input}<button type="button" class="pw-toggle" data-pw aria-pressed="false"
        aria-label="${esc(T("show_password"))}" title="${esc(T("show_password"))}">${ICON.eye}</button></span>`;
    }
  }
  return `<label class="field" for="${id}"><span>${esc(f.label)}</span>${input}</label>`;
}

function formHtml(fields, values = {}) {
  let out = "", i = 0;
  while (i < fields.length) {
    const f = fields[i];
    if (f.row && fields[i + 1]?.row === f.row) {
      out += `<div class="row2">${fieldHtml(f, values[f.name])}${fieldHtml(fields[i + 1], values[fields[i + 1].name])}</div>`;
      i += 2;
    } else { out += fieldHtml(f, values[f.name]); i += 1; }
  }
  return out;
}

function readForm(root, fields) {
  const out = {};
  for (const f of fields) {
    const el = root.querySelector(`[name="${f.name}"]`);
    if (!el) continue;
    if (f.type === "checkbox") out[f.name] = el.checked;
    else if (f.type === "file") out[f.name] = [...el.files];
    else if (f.type === "number") out[f.name] = el.value === "" ? (f.int ? 0 : null) : (f.int ? parseInt(el.value, 10) : parseFloat(el.value.replace(",", ".")));
    else if (f.type === "select" && f.numeric) out[f.name] = el.value === "" ? null : Number(el.value);
    else out[f.name] = el.value.trim() === "" ? null : el.value.trim();
  }
  return out;
}

// container: show the form right on the page (no pop-up window). Save/Cancel wake up once something changes.
// editPerm / deletePerm: without that permission the form only shows the values / has no Delete.
function openForm({ title, fields, values = {}, submitLabel = T("save"), onSubmit, onDelete, intro = "", outro = "", container = null,
  editPerm = null, deletePerm = null }) {
  const readOnly = !!editPerm && !can(editPerm);
  if (deletePerm && !can(deletePerm)) onDelete = null;
  const formTag = `<form id="mform" novalidate>${intro}${formHtml(fields, values)}${outro}<button type="submit" hidden></button></form>`;
  const footer = readOnly
    ? `${onDelete ? `<button class="btn danger left" data-del type="button">${esc(T("delete"))}</button>` : ""}
       ${container ? "" : `<button class="btn" data-close type="button">${esc(T("close"))}</button>`}`
    : `${onDelete ? `<button class="btn danger left" data-del type="button">${esc(T("delete"))}</button>` : ""}
             <button class="btn" ${container ? "data-reset disabled" : "data-close"} type="button">${esc(T("cancel"))}</button>
             <button class="btn primary" data-ok type="button" ${container ? "disabled" : ""}>${esc(submitLabel)}</button>`;
  let back;
  if (container) {
    container.innerHTML = `${formTag}<div class="form-actions">${footer}</div>`;
    back = container;
  } else back = modal({ title, html: formTag, footer });
  const form = $("#mform", back);
  if (readOnly) {
    form.insertAdjacentHTML("afterbegin", `<p class="small muted read-only-note">${esc(T("read_only"))}</p>`);
    $$("input, select, textarea", form).forEach((i) => { i.disabled = true; });
    $$(".dropzone, input[type=file]", form).forEach((i) => (i.closest(".field") || i).remove());
    $("[data-del]", back)?.addEventListener("click", async () => {
      if (!confirm(T("confirm_delete"))) return;
      try { await onDelete(); closeModal(); toast(T("deleted")); } catch (err) { fail(err); }
    });
    return back;
  }
  if (container) {
    const okBtn = $("[data-ok]", back), resetBtn = $("[data-reset]", back);
    const dirty = (on) => { okBtn.disabled = !on; resetBtn.disabled = !on; back.classList.toggle("dirty", on); };
    form.addEventListener("input", () => dirty(true));
    form.addEventListener("change", () => dirty(true));
    resetBtn.addEventListener("click", () => { form.reset(); form.dispatchEvent(new Event("reset-done")); dirty(false); });
  }
  const submit = async (e) => {
    e?.preventDefault();
    const missing = fields.find((f) => f.required && !form.querySelector(`[name="${f.name}"]`).value.trim());
    if (missing) { toast(`${missing.label}?`, true); form.querySelector(`[name="${missing.name}"]`).focus(); return; }
    const btn = $("[data-ok]", back);
    btn.disabled = true;
    try { await onSubmit(readForm(form, fields)); closeModal(); }
    catch (err) { fail(err); btn.disabled = false; }
  };
  form.addEventListener("submit", submit);
  $("[data-ok]", back).addEventListener("click", submit);
  $("[data-del]", back)?.addEventListener("click", async () => {
    if (!confirm(T("confirm_delete"))) return;
    try { await onDelete(); closeModal(); toast(T("deleted")); } catch (err) { fail(err); }
  });
  return back;
}

// ---------------------------------------------------------------- shared pieces
function vendorPill(t) {
  if (t.vendor_status === "confirmed") return ` <span class="pill green">${esc(T("vs_confirmed_on", fmtDate(t.vendor_booked_for)))}</span>`;
  if (t.vendor_status === "requested") return ` <span class="pill amber">${esc(T("vs_requested"))}</span>`;
  return "";
}

function entryHtml(t, { showAsset = true } = {}) {
  const s = stamp(t.next_due);
  const meta = [showAsset ? t.asset_name : null, t.component_name, intervalText(t)].filter(Boolean).join(", ");
  return `<a class="entry ${t.status}" href="#/task/${t.id}">
    <span class="bar"></span>
    <span class="stamp"><span class="d">${s.d}</span><span class="m">${esc(s.m)}</span></span>
    <span class="body"><div class="entry-title">${esc(t.title)}${vendorPill(t)}</div><div class="meta">${esc(meta)}</div></span>
    <span class="side"><span class="when ${t.status}">${esc(whenText(t))}</span>
      ${t.active ? `<button class="done-btn" data-perm="tasks.complete" data-done="${t.id}" title="${esc(T("mark_done"))}" aria-label="${esc(T("mark_done"))}: ${esc(t.title)}">${ICON.check}</button>` : ""}
    </span></a>`;
}

// One listener for every "done" button on every page
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-done]");
  if (!b) return;
  e.preventDefault();
  e.stopPropagation();
  completeDialog(Number(b.dataset.done));
});

async function completeDialog(taskId) {
  let task;
  try { task = await api(`/api/tasks/${taskId}`); } catch (e) { return fail(e); }
  let vendors = [];
  try { vendors = await api("/api/vendors"); } catch (e) { /* not essential */ }
  const fields = [
    { name: "done_on", label: T("done_on"), type: "date", default: todayIso(), row: "a" },
    { name: "cost", label: T("cost"), type: "number", default: task.estimated_cost ?? "", row: "a" },
  ];
  if (vendors.length || task.vendor_id) {
    fields.push({ name: "vendor_id", label: T("done_by_vendor"), type: "select", numeric: true, default: task.vendor_id ?? "",
      options: [["", T("done_ourselves")], ...vendors.filter((v) => v.active || v.id === task.vendor_id).map((v) => [v.id, v.company])] });
  }
  if (task.counter_unit) {
    fields.push({ name: "counter_value", label: T("counter_at_done", unitShort(task.counter_unit)), type: "number", default: task.counter_current ?? "" });
  }
  fields.push({ name: "notes", label: T("notes"), type: "textarea" });
  if (can("attachments.add")) fields.push({ name: "files", label: T("invoice_or_receipt"), type: "file" });
  openForm({
    title: `${T("mark_done")}: ${task.title}`,
    fields,
    submitLabel: T("done"),
    onSubmit: async (v) => {
      const res = await api(`/api/tasks/${taskId}/complete`, { method: "POST", body: { done_on: v.done_on || todayIso(), cost: v.cost, notes: v.notes, counter_value: v.counter_value ?? null, vendor_id: v.vendor_id ?? null } });
      if (v.files?.length) {
        const newest = res.completions.reduce((a, b) => (b.id > a.id ? b : a));
        for (const f of v.files) await uploadFile("completion", newest.id, f);
      }
      const nextBits = [res.next_due ? fmtDate(res.next_due) : "", res.counter_next_due != null && res.counter_unit ? counterVal(res.counter_next_due, res.counter_unit) : ""].filter(Boolean);
      toast(res.active ? (nextBits.length ? `${T("completed_ok")}. ${T("next_due_on", nextBits.join(T("or_word")))}` : T("completed_ok")) : T("closed_task"));
      render();
    },
  });
}

async function uploadFile(entityType, entityId, file) {
  const form = new FormData();
  form.append("entity_type", entityType);
  form.append("entity_id", entityId);
  form.append("file", file);
  return api("/api/attachments", { method: "POST", form });
}

async function openAttachment(id, filename) {
  try {
    const res = await api(`/api/attachments/${id}/file`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    if (!/^(image|application\/pdf|text)/.test(blob.type)) a.download = filename;
    else a.target = "_blank";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) { fail(e); }
}

async function filesWidget(container, entityType, entityId) {
  const draw = async () => {
    let files = [];
    try { files = await api(`/api/attachments?entity_type=${entityType}&entity_id=${entityId}`); } catch (e) { return fail(e); }
    container.innerHTML = `<div class="files">${files.length ? files.map((f) => `
      <div class="file">${ICON.file}<div class="grow"><button class="link" data-open="${f.id}" data-name="${esc(f.filename)}">${esc(f.filename)}</button>
        <div class="small muted">${fmtDate(f.uploaded_at.slice(0, 10))}, ${Math.max(1, Math.round(f.size / 1024))} kB</div></div>
        <button class="btn ghost small" data-perm="attachments.delete" data-rm="${f.id}" aria-label="${esc(T("delete"))}">${ICON.x}</button></div>`).join("")
      : `<p class="muted small">${esc(T("no_files"))}</p>`}</div>
      ${can("attachments.add") ? `<label class="dropzone">${esc(T("drop_files"))}<input type="file" multiple hidden></label>` : ""}`;
    $$("[data-open]", container).forEach((b) => b.onclick = () => openAttachment(b.dataset.open, b.dataset.name));
    $$("[data-rm]", container).forEach((b) => b.onclick = async () => {
      if (!confirm(T("confirm_delete"))) return;
      try { await api(`/api/attachments/${b.dataset.rm}`, { method: "DELETE" }); draw(); } catch (e) { fail(e); }
    });
    const zone = $(".dropzone", container);
    if (!zone) return;
    const input = $("input", zone);
    const send = async (list) => {
      for (const f of list) { try { await uploadFile(entityType, entityId, f); } catch (e) { fail(e); } }
      toast(T("uploaded")); draw();
    };
    input.onchange = () => send([...input.files]);
    zone.ondragover = (e) => { e.preventDefault(); zone.classList.add("over"); };
    zone.ondragleave = () => zone.classList.remove("over");
    zone.ondrop = (e) => { e.preventDefault(); zone.classList.remove("over"); send([...e.dataTransfer.files]); };
  };
  await draw();
}

// Compact file list for one history entry or purchase: open files, attach more afterwards
async function miniFiles(el, entityType, entityId) {
  let files = [];
  try { files = await api(`/api/attachments?entity_type=${entityType}&entity_id=${entityId}`); } catch { return; }
  el.innerHTML = `<div class="mini-files">${files.map((f) =>
    `<button class="btn ghost small" type="button" data-open="${f.id}" data-name="${esc(f.filename)}">${ICON.file}${esc(f.filename)}</button>`).join("")}
    ${can("attachments.add") ? `<label class="btn ghost small attach">${ICON.plus}${esc(T("attach_receipt"))}<input type="file" multiple hidden></label>` : ""}</div>`;
  $$("[data-open]", el).forEach((b) => b.onclick = () => openAttachment(b.dataset.open, b.dataset.name));
  const input = $("input", el);
  if (!input) return;
  input.onchange = async () => {
    for (const f of input.files) { try { await uploadFile(entityType, entityId, f); } catch (e) { fail(e); } }
    toast(T("uploaded"));
    miniFiles(el, entityType, entityId);
  };
}

// ---------------------------------------------------------------- auth screens
function logout() {
  state.token = null; state.user = null; state.users = []; state.vendors = [];
  localStorage.removeItem("tm_token");
  location.hash = "#/";
  render();
}

function loggedIn(res) {
  state.token = res.token;
  localStorage.setItem("tm_token", res.token);
  state.user = null;  // /api/me brings group, role and permissions
  setLang(res.user.lang);
  shellRendered = false;
  state.users = []; state.vendors = []; state.assetFilter = null; localStorage.removeItem("tm_asset");
}

// mode: "login" | "setup" (first user ever) | "signup" (new group, needs the sign-up code)
async function renderAuth(mode) {
  const app = $("#app");
  let status = { needs_setup: false, signup_enabled: false, signup_needs_code: false };
  try { status = await api("/api/auth/status"); } catch (e) { fail(e); }
  mode = status.needs_setup ? "setup" : mode === "signup" && status.signup_enabled ? "signup" : "login";
  const newAccount = [{ name: "name", label: T("your_name"), required: true, autocomplete: "name" },
    { name: "email", label: T("email"), type: "email", required: true, autocomplete: "email" },
    { name: "password", label: T("password"), type: "password", required: true, autocomplete: "new-password" }];
  const familyField = { name: "group_name", label: T("group_name"), required: true, placeholder: T("group_name_hint") };
  const fields = mode === "setup" ? [familyField, ...newAccount]
    : mode === "signup" ? [familyField, ...newAccount,
                           ...(status.signup_needs_code ? [{ name: "code", label: T("signup_code"), required: true }] : [])]
    : [{ name: "email", label: T("email"), type: "email", required: true, autocomplete: "username" },
       { name: "password", label: T("password"), type: "password", required: true, autocomplete: "current-password" }];
  const title = { setup: "setup_title", signup: "signup_title", login: "login_title" }[mode];
  const lead = { setup: "setup_lead", signup: "signup_lead", login: "login_lead" }[mode];
  app.innerHTML = `<div class="auth-wrap"><div class="auth">
    <div class="brand"><img src="icon.svg" alt=""><span>${T("app")}</span></div>
    <div class="panel"><h1>${esc(T(title))}</h1>
      <p class="lead">${esc(T(lead))}</p>
      <form id="authform">${formHtml(fields)}<button class="btn primary" style="width:100%">${esc(T(mode === "login" ? "log_in" : "create_account"))}</button></form>
      ${mode === "login" ? `<p class="small" style="text-align:center;margin:14px 0 0"><button class="link" type="button" id="toForgot">${esc(T("forgot_link"))}</button></p>` : ""}
      ${mode === "login" && status.signup_enabled ? `<p class="small" style="text-align:center;margin:8px 0 0"><button class="link" id="toSignup">${esc(T("signup_link"))}</button></p>` : ""}
      ${mode === "signup" ? `<p class="small" style="text-align:center;margin:14px 0 0"><button class="link" id="toLogin">${esc(T("have_account"))}</button></p>` : ""}
    </div>
    ${langSwitch()}
  </div></div>`;
  $$("[data-lang]", app).forEach((b) => b.onclick = () => { setLang(b.dataset.lang); renderAuth(mode); });
  $("#toSignup")?.addEventListener("click", () => renderAuth("signup"));
  $("#toForgot")?.addEventListener("click", () => renderForgot($('[name="email"]', app)?.value || ""));
  $("#toLogin")?.addEventListener("click", () => renderAuth("login"));
  $("#authform").onsubmit = async (e) => {
    e.preventDefault();
    const v = readForm(e.target, fields);
    try {
      const path = { setup: "/api/auth/setup", signup: "/api/auth/signup", login: "/api/auth/login" }[mode];
      const body = mode === "login" ? v : { ...v, lang: state.lang };
      loggedIn(await api(path, { method: "POST", body }));
      render();
    } catch (err) { fail(err); }
  };
}

// Same frame as the log-in screen, for the smaller pages around it
function authFrame(inner, onLang) {
  const app = $("#app");
  app.innerHTML = `<div class="auth-wrap"><div class="auth">
    <div class="brand"><img src="icon.svg" alt=""><span>${T("app")}</span></div>
    <div class="panel">${inner}</div>
    ${langSwitch()}
  </div></div>`;
  $$("[data-lang]", app).forEach((b) => b.onclick = () => { setLang(b.dataset.lang); onLang(); });
  return app;
}

// "Forgot password?": ask for the e-mail address, the server mails a one-time link
function renderForgot(email = "") {
  const fields = [{ name: "email", label: T("email"), type: "email", required: true, autocomplete: "username" }];
  const app = authFrame(`<h1>${esc(T("forgot_title"))}</h1><p class="lead">${esc(T("forgot_lead"))}</p>
      <form id="forgotform">${formHtml(fields, { email })}<button class="btn primary" style="width:100%">${esc(T("forgot_send"))}</button></form>
      <p class="small" style="text-align:center;margin:14px 0 0"><button class="link" type="button" id="toLogin">${esc(T("back_to_login"))}</button></p>`,
    () => renderForgot($('[name="email"]')?.value || ""));
  $("#toLogin").onclick = () => renderAuth("login");
  $("#forgotform").onsubmit = async (e) => {
    e.preventDefault();
    const v = readForm(e.target, fields);
    if (!v.email) return toast(`${T("email")}?`, true);
    try {
      const r = await api("/api/auth/forgot", { method: "POST", body: { email: v.email, lang: state.lang } });
      authFrame(`<h1>${esc(T("forgot_title"))}</h1>
        <p class="lead">${esc(r.mail_enabled ? T("forgot_sent", v.email) : T("forgot_no_mail"))}</p>
        <button class="btn" style="width:100%" id="toLogin">${esc(T("back_to_login"))}</button>`, () => renderForgot(v.email));
      $("#toLogin").onclick = () => renderAuth("login");
    } catch (err) { fail(err); }
  };
}

// The page behind the link in a reset e-mail: #/reset/<token>
async function renderReset(token) {
  let info;
  try { info = await api(`/api/auth/reset/${token}`); }
  catch (e) {
    const app = authFrame(`<h1>${esc(T("reset_title"))}</h1><p class="lead">${esc(e.message)}</p>
      <button class="btn primary" style="width:100%" id="again">${esc(T("forgot_again"))}</button>`, () => renderReset(token));
    $("#again", app).onclick = () => { history.replaceState(null, "", "#/"); renderForgot(); };
    return;
  }
  const fields = [
    { name: "password", label: T("choose_password"), type: "password", required: true, autocomplete: "new-password" },
    { name: "password2", label: T("repeat_password"), type: "password", required: true, autocomplete: "new-password" },
  ];
  authFrame(`<h1>${esc(T("reset_title"))}</h1><p class="lead">${esc(T("reset_lead", info.name))}</p>
      <p class="small muted">${esc(info.email)}</p>
      <form id="resetform">${formHtml(fields)}<button class="btn primary" style="width:100%">${esc(T("reset_save"))}</button></form>`,
    () => renderReset(token));
  $("#resetform").onsubmit = async (e) => {
    e.preventDefault();
    const v = readForm(e.target, fields);
    if (!v.password || v.password.length < 6) return toast(T("password_short"), true);
    if (v.password !== v.password2) return toast(T("password_mismatch"), true);
    try {
      loggedIn(await api(`/api/auth/reset/${token}`, { method: "POST", body: { password: v.password } }));
      toast(T("reset_done"));
      location.hash = "#/";
      render();
    } catch (err) { fail(err); }
  };
}

// The page behind the link in an invitation e-mail: #/invite/<token>
async function renderInvite(token) {
  const app = $("#app");
  let info;
  try { info = await api(`/api/invite/${token}`); }
  catch (e) {
    app.innerHTML = `<div class="auth-wrap"><div class="auth"><div class="brand"><img src="icon.svg" alt=""><span>${T("app")}</span></div>
      <div class="panel"><h1>${esc(T("invite_title"))}</h1><p class="lead">${esc(e.message)}</p>
      <a class="btn" href="#/" style="width:100%">${esc(T(state.token ? "nav_home" : "log_in"))}</a></div></div></div>`;
    return;
  }
  const fields = info.has_account
    ? [{ name: "password", label: T("password"), type: "password", required: true, autocomplete: "current-password" }]
    : [{ name: "name", label: T("name"), required: true, autocomplete: "name" },
       { name: "password", label: T("choose_password"), type: "password", required: true, autocomplete: "new-password" }];
  app.innerHTML = `<div class="auth-wrap"><div class="auth">
    <div class="brand"><img src="icon.svg" alt=""><span>${T("app")}</span></div>
    <div class="panel"><h1>${esc(T("invite_title"))}</h1>
      <p class="lead">${esc(T("invite_lead", info.invited_by || T("app"), info.group_name, info.role_name))}</p>
      <p class="small muted">${esc(info.email)}${info.has_account ? ` · ${esc(T("invite_has_account"))}` : ""}</p>
      <form id="invform">${formHtml(fields)}<button class="btn primary" style="width:100%">${esc(T("join_group"))}</button></form>
    </div>
    ${langSwitch()}
  </div></div>`;
  $$("[data-lang]", app).forEach((b) => b.onclick = () => { setLang(b.dataset.lang); renderInvite(token); });
  $("#invform").onsubmit = async (e) => {
    e.preventDefault();
    const v = readForm(e.target, fields);
    try {
      loggedIn(await api(`/api/invite/${token}/accept`, { method: "POST", body: { ...v, lang: state.lang } }));
      toast(T("joined_group", info.group_name));
      location.hash = "#/";
      render();
    } catch (err) { fail(err); }
  };
}

function setLang(lang) {
  state.lang = lang;
  localStorage.setItem("tm_lang", lang);
  document.documentElement.lang = lang === "no" ? "nb" : lang;
}

// ---------------------------------------------------------------- shell
let shellRendered = false;
const NAV = [
  ["#/", "nav_home", "overview"], ["#/assets", "nav_assets", "things"], ["#/calendar", "nav_calendar", "calendar"],
  ["#/shopping", "nav_shopping", "cart"], ["#/settings", "nav_settings", "settings"],
];

function renderShell() {
  const links = (cls) => NAV.map(([href, key, icon]) =>
    `<a href="${href}" data-nav="${href}">${ICON[icon]}<span>${esc(T(key))}</span><span class="badge hidden" data-badge="${key}"></span></a>`).join("");
  $("#app").innerHTML = `<div class="shell">
    <aside class="sidebar"><div class="brand"><img src="icon.svg" alt=""><span>${T("app")}</span></div>
      <nav class="nav">${links()}</nav><div class="who">${esc(state.user?.name || "")}${state.user?.group ? `<div class="small">${esc(state.user.group.name)} · ${esc(state.user.role.name)}</div>` : ""}</div></aside>
    <main class="main" id="main"></main>
    <nav class="tabbar">${links()}</nav></div>`;
  shellRendered = true;
}

function markNav() {
  const hash = location.hash || "#/";
  const top = hash.startsWith("#/asset") || hash.startsWith("#/task") ? "#/assets" : `#/${hash.split("/")[1] || ""}`;
  $$("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === top));
}

async function refreshBadges() {
  try {
    const d = await api(`/api/dashboard?mine=${state.mine}`);
    $$('[data-badge="nav_home"]').forEach((b) => {
      const n = d.overdue.length || d.due_soon.length;
      b.textContent = n; b.classList.toggle("hidden", !n); b.classList.toggle("soon", !d.overdue.length);
    });
    $$('[data-badge="nav_shopping"]').forEach((b) => {
      b.textContent = d.shopping_count; b.classList.toggle("hidden", !d.shopping_count); b.classList.add("soon");
    });
  } catch { /* badges are optional */ }
}

// ---------------------------------------------------------------- router
async function render() {
  const inviteToken = (location.hash.match(/^#\/invite\/([\w-]+)/) || [])[1];
  if (inviteToken) { shellRendered = false; return renderInvite(inviteToken); }
  const resetToken = (location.hash.match(/^#\/reset\/([\w-]+)/) || [])[1];
  if (resetToken) { shellRendered = false; return renderReset(resetToken); }
  if (!state.token) { shellRendered = false; return renderAuth(); }
  if (!state.user) {
    try { state.user = await api("/api/me"); setLang(state.user.lang); } catch (e) { return; }
  }
  if (!shellRendered) renderShell();
  markNav();
  const main = $("#main");
  const [, route, id] = (location.hash || "#/").split("?")[0].split("/");
  // a page that needs a number (#/task/12, #/asset/3) but got none: go to the overview instead of an error
  if ((route === "task" || route === "asset" || route === "vendor") && !/^\d+$/.test(id || "")) { location.replace("#/"); return; }
  main.innerHTML = `<div class="loading">…</div>`;
  try {
    if (!route) await pageDashboard(main);
    else if (route === "assets") await pageAssets(main);
    else if (route === "asset") await pageAsset(main, Number(id));
    else if (route === "task") await pageTask(main, Number(id));
    else if (route === "vendor") await pageVendor(main, Number(id));
    else if (route === "calendar") await pageCalendar(main);
    else if (route === "shopping") await pageShopping(main);
    else if (route === "print") await pagePrint(main);
    else if (route === "settings") await pageSettings(main);
    else location.hash = "#/";
  } catch (e) { fail(e); main.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
  refreshBadges();
}
window.addEventListener("hashchange", () => { closeModal(); render(); window.scrollTo(0, 0); });

// ---------------------------------------------------------------- filter by thing (overview + calendar)
async function loadAssetsForFilter() {
  const assets = await api("/api/assets");
  if (state.assetFilter && !assets.some((a) => a.id === state.assetFilter)) setAssetFilter(null);
  return assets;
}

function setAssetFilter(id) {
  state.assetFilter = id || null;
  try { id ? localStorage.setItem("tm_asset", id) : localStorage.removeItem("tm_asset"); } catch { /* ignore */ }
}

const filterQuery = () => `mine=${state.mine}${state.assetFilter ? `&asset_id=${state.assetFilter}` : ""}`;

function assetChips(assets) {
  if (assets.length < 2) return "";
  const chip = (id, label, icon, extra = "") =>
    `<button class="chip ${String(state.assetFilter || "") === String(id) ? "active" : ""}" data-asset="${id}" aria-pressed="${String(state.assetFilter || "") === String(id)}">${icon}<span>${esc(label)}</span>${extra}</button>`;
  return `<div class="chips" role="group" aria-label="${esc(T("filter_by_thing"))}">
    ${chip("", T("all_things"), "")}
    ${assets.map((a) => chip(a.id, a.name, kindIcon(a.kind),
      a.overdue_count ? `<span class="chip-n">${a.overdue_count}</span>` : "")).join("")}</div>`;
}

function bindAssetChips(root, rerender) {
  $$("[data-asset]", root).forEach((b) => b.onclick = () => { setAssetFilter(Number(b.dataset.asset) || null); rerender(); });
  // on the phone the row scrolls sideways: keep the selected thing visible
  const active = $(".chip.active", root);
  const row = active?.parentElement;
  if (active && row && row.scrollWidth > row.clientWidth) {
    row.scrollLeft = active.offsetLeft - (row.clientWidth - active.offsetWidth) / 2;
  }
}

// ---------------------------------------------------------------- dashboard
async function pageDashboard(main) {
  const [d, assets] = await Promise.all([api(`/api/dashboard?${filterQuery()}`), loadAssetsForFilter()]);
  const one = Boolean(state.assetFilter);
  if (!d.asset_count) {
    main.innerHTML = `<div class="page-head"><div class="grow"><h1>${esc(T("nav_home"))}</h1></div></div>
      <div class="empty"><p>${esc(T("no_things"))}</p><button class="btn primary" id="first">${ICON.plus}${esc(T("add_thing"))}</button></div>`;
    $("#first").onclick = () => assetForm();
    return;
  }
  const list = (items, empty = "") => items.length ? `<div class="entries">${items.map((t) => entryHtml(t, { showAsset: !one })).join("")}</div>` : empty;
  const maxCost = Math.max(1, ...d.cost_by_asset.map((x) => x.cost));
  const hello = new Date().toLocaleDateString(locale(), { weekday: "long", day: "numeric", month: "long" });
  main.innerHTML = `
    <div class="page-head"><div class="grow"><h1>${esc(T("nav_home"))}</h1><div class="sub">${esc(hello)}</div></div>
      <label class="check" style="margin:0"><input type="checkbox" id="mine" ${state.mine ? "checked" : ""}><span>${esc(T("only_mine"))}</span></label>
      <button class="btn" id="printBtn">${ICON.print}${esc(T("print"))}</button></div>
    ${assetChips(assets)}
    <div class="overview">
      <a href="#overdue"><span class="n ${d.overdue.length ? "overdue" : ""}">${d.overdue.length}</span><span class="l">${esc(T("overdue"))}</span></a>
      <a href="#soon"><span class="n ${d.due_soon.length ? "soon" : ""}">${d.due_soon.length}</span><span class="l">${esc(T("due_soon"))}</span></a>
      <a href="#/calendar"><span class="n">${d.done_this_year}</span><span class="l">${esc(T("done_this_year"))}</span></a>
      <a href="${one ? `#/asset/${state.assetFilter}` : "#/assets"}"><span class="n">${esc(money(d.cost_this_year))}</span><span class="l">${esc(T("spent_this_year"))}</span></a>
    </div>
    <div class="two-col"><div>
      ${!d.overdue.length && !d.due_soon.length ? `<div class="section"><div class="allclear">${esc(T("all_clear"))}</div></div>` : ""}
      ${d.overdue.length ? `<div class="section" id="overdue"><h2>${esc(T("overdue"))} <span class="count">${d.overdue.length}</span></h2>${list(d.overdue)}</div>` : ""}
      ${d.due_soon.length ? `<div class="section" id="soon"><h2>${esc(T("due_soon"))} <span class="count">${d.due_soon.length}</span></h2>${list(d.due_soon)}</div>` : ""}
      ${d.upcoming.length ? `<div class="section"><h2>${esc(T("upcoming"))} <span class="count">${d.upcoming.length}</span></h2>${list(d.upcoming)}</div>` : ""}
    </div><div>
      <div class="panel mini-cal" id="miniCal"></div>
      ${d.recent.length ? `<div class="panel"><h3>${esc(T("recent"))}</h3><ul class="list-plain">${d.recent.map((r) => `
        <li><span class="grow"><a href="${r.kind === "purchase" ? `#/asset/${r.asset_id}` : `#/task/${r.task_id}`}">${esc(r.task_title)}</a><div class="small muted">${one ? "" : `${esc(r.asset_name)}, `}${fmtDate(r.done_on)}${r.done_by_name ? `, ${esc(r.done_by_name)}` : ""}</div></span>
        <span class="money small">${esc(money(r.cost))}</span></li>`).join("")}</ul></div>` : ""}
      ${d.cost_by_asset.length > 1 ? `<div class="panel"><h3>${esc(T("cost_by_asset"))}</h3><ul class="list-plain">${d.cost_by_asset.map((c) => `
        <li><span class="grow">${esc(c.asset)}<div class="costbar"><i style="width:${(c.cost / maxCost) * 100}%"></i></div></span><span class="money">${esc(money(c.cost))}</span></li>`).join("")}</ul></div>` : ""}
      ${d.warranties_expiring.length ? `<div class="panel"><h3>${esc(T("warranties_ending"))}</h3><ul class="list-plain">${d.warranties_expiring.map((w) => `
        <li><span class="grow"><a href="#/asset/${w.asset_id}">${esc(w.title)}</a><div class="small muted">${esc(w.asset_name)}</div></span><span class="pill amber">${fmtDate(w.end_date)}</span></li>`).join("")}</ul></div>` : ""}
      ${d.shopping_count ? `<div class="panel"><h3>${esc(T("shopping_title"))}</h3><p class="muted">${d.shopping_count} ${esc(T("shopping_items").toLowerCase())}</p><a class="btn small" href="#/shopping">${esc(T("nav_shopping"))}</a></div>` : ""}
    </div></div>`;
  $("#mine").onchange = (e) => { state.mine = e.target.checked; localStorage.setItem("tm_mine", state.mine ? "1" : "0"); render(); };
  bindAssetChips(main, () => pageDashboard(main));
  miniCalendar($("#miniCal")).catch(fail);
  $("#printBtn").onclick = () => openPrint();
  $$('.overview a[href^="#o"], .overview a[href^="#s"]').forEach((a) => a.onclick = (e) => {
    e.preventDefault(); document.getElementById(a.getAttribute("href").slice(1))?.scrollIntoView({ behavior: "smooth" });
  });
}

// ---------------------------------------------------------------- small month calendar on the overview
// Dots show what happens on each day; click a day to see its tasks underneath.
async function miniCalendar(box) {
  if (!box) return;
  const base = state.miniMonth || new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  state.miniMonth = base;
  const iso = (d) => d.toLocaleDateString("sv-SE");
  const gridStart = new Date(base); gridStart.setDate(1 - ((base.getDay() + 6) % 7)); // Monday first
  const gridEnd = new Date(gridStart); gridEnd.setDate(gridStart.getDate() + 41);
  const events = await api(`/api/calendar?start=${iso(gridStart)}&end=${iso(gridEnd)}&${filterQuery()}`);
  if (!box.isConnected) return;
  const byDay = {};
  for (const e of events) (byDay[e.date] ||= []).push(e);
  const evClass = (e) => e.type === "warranty" ? "warranty" : e.type === "done" ? "done" : e.type === "booked" ? "booked" : e.projected ? "projected" : e.status;
  const evHref = (e) => e.type === "warranty" ? `#/asset/${e.asset_id}` : `#/task/${e.id}`;
  // keep the chosen day if it is in this month, otherwise today (or nothing)
  if (!state.miniDay || state.miniDay.slice(0, 7) !== iso(base).slice(0, 7)) {
    state.miniDay = todayIso().slice(0, 7) === iso(base).slice(0, 7) ? todayIso() : null;
  }
  const order = ["overdue", "due_soon", "booked", "ok", "projected", "warranty", "done"];
  const dows = [...Array(7)].map((_, i) => new Date(2024, 0, 1 + i).toLocaleDateString(locale(), { weekday: "narrow" }));
  let cells = "";
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart); d.setDate(gridStart.getDate() + i);
    const k = iso(d);
    const kinds = [...new Set((byDay[k] || []).map(evClass))].sort((a, b) => order.indexOf(a) - order.indexOf(b)).slice(0, 3);
    const n = (byDay[k] || []).length;
    const label = `${d.toLocaleDateString(locale(), { day: "numeric", month: "long" })}${n ? `, ${T("n_tasks", n)}` : ""}`;
    cells += `<button type="button" class="mc-day ${d.getMonth() !== base.getMonth() ? "other" : ""} ${k === todayIso() ? "today" : ""} ${k === state.miniDay ? "sel" : ""}"
      data-day="${k}" aria-label="${esc(label)}" aria-pressed="${k === state.miniDay}"><span class="mc-n">${d.getDate()}</span>
      <span class="mc-dots">${kinds.map((c) => `<i class="${c}"></i>`).join("")}</span></button>`;
  }
  const sel = state.miniDay ? byDay[state.miniDay] || [] : [];
  const dayTitle = state.miniDay ? new Date(state.miniDay + "T12:00:00").toLocaleDateString(locale(), { weekday: "long", day: "numeric", month: "long" }) : "";
  box.innerHTML = `<div class="mc-head"><h3>${esc(base.toLocaleDateString(locale(), { month: "long", year: "numeric" }))}</h3>
      <button class="btn ghost small" data-mc="-1" aria-label="${esc(T("prev"))}">‹</button>
      <button class="btn ghost small" data-mc="0">${esc(T("this_month"))}</button>
      <button class="btn ghost small" data-mc="1" aria-label="${esc(T("next"))}">›</button></div>
    <div class="mc-grid">${dows.map((d) => `<span class="mc-dow">${esc(d)}</span>`).join("")}${cells}</div>
    ${state.miniDay ? `<div class="mc-list"><div class="mc-list-title">${esc(dayTitle)}</div>
      ${sel.length ? sel.map((e) => `<a class="ev ${evClass(e)}" href="${evHref(e)}" title="${esc(e.title)}, ${esc(e.asset)}">${esc(e.title)}</a>`).join("")
        : `<p class="small muted" style="margin:0">${esc(T("nothing_this_day"))}</p>`}</div>` : ""}
    <a class="small mc-more" href="#/calendar">${esc(T("open_calendar"))} ›</a>`;
  $$("[data-mc]", box).forEach((b) => b.onclick = () => {
    const step = Number(b.dataset.mc);
    state.miniMonth = step ? new Date(base.getFullYear(), base.getMonth() + step, 1) : null;
    if (!step) state.miniDay = todayIso();
    miniCalendar(box).catch(fail);
  });
  $$("[data-day]", box).forEach((b) => b.onclick = () => {
    const k = b.dataset.day;
    state.miniDay = k;
    if (k.slice(0, 7) !== iso(base).slice(0, 7)) state.miniMonth = new Date(Number(k.slice(0, 4)), Number(k.slice(5, 7)) - 1, 1);
    miniCalendar(box).catch(fail);
  });
}

// ---------------------------------------------------------------- assets
const KINDS = ["home", "car", "boat", "cabin", "bicycle", "motorcycle", "scooter", "other"];

// "Documents and receipts" in a form: a file list when editing, a file picker when creating
const docsOutro = (obj) => obj ? `<div class="field"><span class="form-sub">${esc(T("docs_and_receipts"))}</span><div id="formfiles"></div></div>` : "";
function docsField(fields, obj) { if (!obj && can("attachments.add")) fields.push({ name: "files", label: T("docs_and_receipts"), type: "file" }); return fields; }
async function uploadAll(entityType, id, files) { for (const f of files || []) await uploadFile(entityType, id, f); }
function mountDocs(entityType, obj) { if (obj) filesWidget($("#formfiles"), entityType, obj.id); }

function assetForm(asset) {
  const fields = [
    { name: "name", label: T("name"), required: true },
    { name: "kind", label: T("kind"), type: "select", options: KINDS.map((k) => [k, T(`kind_${k}`)]) },
    { name: "location", label: T("location") },
    { name: "counter_unit", label: T("counter_unit"), type: "select", options: [["none", T("counter_none")], ["km", T("counter_km")], ["hours", T("counter_hours")]], row: "cu" },
    { name: "counter_value", label: T("counter_now"), type: "number", row: "cu" },
    { name: "description", label: T("description"), type: "textarea" },
  ];
  docsField(fields, asset);
  openForm({
    title: asset ? T("edit") : T("add_thing"),
    fields, values: asset || { kind: "home", counter_unit: "none" }, outro: docsOutro(asset),
    onSubmit: async (v) => {
      const files = v.files; delete v.files;
      if (asset) { await api(`/api/assets/${asset.id}`, { method: "PUT", body: v }); toast(T("saved")); render(); }
      else {
        const a = await api("/api/assets", { method: "POST", body: v });
        await uploadAll("asset", a.id, files);
        location.hash = `#/asset/${a.id}`;
        setTimeout(() => templateDialog(a), 250);
      }
    },
    onDelete: asset ? async () => { await api(`/api/assets/${asset.id}`, { method: "DELETE" }); location.hash = "#/assets"; } : null,
    editPerm: asset ? "assets.edit" : "assets.create", deletePerm: "assets.delete",
  });
  mountDocs("asset", asset);
}

function counterDialog(a) {
  const hist = (a.readings || []).length ? `<div class="field"><span class="form-sub">${esc(T("counter_history"))}</span><ul class="list-plain small">${a.readings.map((r) =>
    `<li><span class="grow">${fmtDate(r.reading_on)}</span><b>${esc(counterVal(r.value, a.counter_unit))}</b><button type="button" class="btn ghost small" data-perm="counters.record" data-rmr="${r.id}" aria-label="${esc(T("delete"))}">${ICON.x}</button></li>`).join("")}</ul></div>` : "";
  const back = openForm({
    title: `${T("counter_update")}: ${a.name}`,
    fields: [
      { name: "value", label: T("counter_now_unit", unitShort(a.counter_unit)), type: "number", required: true, row: "r" },
      { name: "reading_on", label: T("reading_date"), type: "date", default: todayIso(), row: "r" },
    ],
    values: { value: a.counter_value ?? "", reading_on: todayIso() },
    outro: hist,
    onSubmit: async (v) => { await api(`/api/assets/${a.id}/counter`, { method: "POST", body: { value: v.value, reading_on: v.reading_on || todayIso() } }); toast(T("saved")); render(); },
    editPerm: "counters.record",
  });
  $$("[data-rmr]", back).forEach((b) => b.onclick = async () => {
    if (!confirm(T("confirm_delete"))) return;
    try { await api(`/api/counter-readings/${b.dataset.rmr}`, { method: "DELETE" }); closeModal(); render(); } catch (e) { fail(e); }
  });
}

async function pageAssets(main) {
  const assets = await api("/api/assets");
  main.innerHTML = `<div class="page-head"><div class="grow"><h1>${esc(T("things_title"))}</h1><div class="sub">${esc(T("things_sub"))}</div></div>
      <button class="btn primary" id="add" data-perm="assets.create">${ICON.plus}${esc(T("add_thing"))}</button></div>
    ${assets.length ? `<div class="asset-grid">${assets.map((a) => `
      <a class="asset-card" href="#/asset/${a.id}"><span class="kind-icon">${kindIcon(a.kind)}</span>
        <span><h3>${esc(a.name)}</h3><span class="small muted">${esc(T(`kind_${a.kind}`))}${a.location ? `, ${esc(a.location)}` : ""}</span>
        <span class="stats"><span>${esc(T("active_tasks", a.task_count))}</span>
          ${a.overdue_count ? `<b class="overdue">${esc(T("n_overdue", a.overdue_count))}</b>` : ""}
          ${a.due_soon_count ? `<b class="soon">${esc(T("n_soon", a.due_soon_count))}</b>` : ""}
          ${a.total_cost ? `<span>${esc(money(a.total_cost))}</span>` : ""}</span></span></a>`).join("")}</div>`
      : `<div class="empty"><p>${esc(T("no_things"))}</p></div>`}`;
  $("#add").onclick = () => assetForm();
}

async function templateDialog(asset) {
  let templates = [];
  try { templates = await api(`/api/templates?kind=${asset.kind}`); } catch (e) { return fail(e); }
  if (!templates.length) return toast(T("template_none"));
  const back = modal({
    title: T("use_template"),
    html: `<div class="entries" style="gap:10px">${templates.map((t, i) => `
      <label class="panel" style="display:flex;gap:12px;cursor:pointer;margin:0;padding:14px">
        <input type="checkbox" name="tpl" value="${esc(t.key)}" ${i === 0 ? "checked" : ""} style="width:18px;height:18px;accent-color:var(--fjord);margin-top:3px">
        <span><b>${esc(t.name)}</b><div class="small muted">${t.task_titles.map(esc).join(", ")}</div></span></label>`).join("")}</div>
      <div style="margin-top:16px">${fieldHtml({ name: "start", label: T("template_start"), type: "date" }, todayIso())}</div>`,
    footer: `<button class="btn" data-close>${esc(T("cancel"))}</button><button class="btn primary" data-ok>${esc(T("use_template"))}</button>`,
  });
  $("[data-ok]", back).onclick = async () => {
    const keys = $$('input[name="tpl"]:checked', back).map((i) => i.value);
    const start = $('[name="start"]', back).value || todayIso();
    let n = 0;
    try {
      for (const k of keys) n += (await api(`/api/assets/${asset.id}/apply-template?key=${k}&start=${start}`, { method: "POST" })).tasks_created;
      closeModal(); toast(T("template_applied", n)); render();
    } catch (e) { fail(e); }
  };
}

function vendorOptions(selectedId) {
  // inactive vendors are hidden, unless the task already uses one
  const list = state.vendors.filter((v) => v.active || v.id === selectedId);
  return [["", T("no_vendor")], ...list.map((v) => [v.id, v.trade ? `${v.company} (${v.trade})` : v.company]),
    ...(can("vendors.manage") ? [["new", T("new_vendor_option")]] : [])];
}

function taskFields(asset, task) {
  return [
    { name: "title", label: T("title"), required: true },
    { name: "component_id", label: T("component"), type: "select", numeric: true, options: [["", T("none")], ...asset.components.map((c) => [c.id, c.name])] },
    { name: "interval_value", label: T("every"), type: "number", int: true, step: 1, row: "r" },
    { name: "interval_unit", label: T("repeat"), type: "select", row: "r",
      options: [["none", T("unit_none")], ["days", T("unit_days")], ["weeks", T("unit_weeks")], ["months", T("unit_months")], ["years", T("unit_years")]] },
    { name: "next_due", label: T("next_due"), type: "date", row: "d" },
    { name: "remind_days_before", label: T("remind_before"), type: "number", int: true, step: 1, row: "d" },
    ...(asset.counter_unit && asset.counter_unit !== "none" ? [
      { name: "counter_interval", label: T("every_counter_label", unitShort(asset.counter_unit)), type: "number", row: "k" },
      { name: "counter_next_due", label: T("next_at_label", unitShort(asset.counter_unit)), type: "number", row: "k" },
    ] : []),
    { name: "assigned_to_id", label: T("assigned_to"), type: "select", numeric: true, options: [["", T("anyone")], ...state.users.map((u) => [u.id, u.name])], row: "a" },
    { name: "vendor_id", label: T("vendor"), type: "select", numeric: true, options: vendorOptions(task?.vendor_id ?? null), row: "a" },
    { name: "estimated_cost", label: T("estimated_cost"), type: "number" },
    { name: "description", label: T("description"), type: "textarea" },
    { name: "active", label: T("active"), type: "checkbox" },
  ];
}

function createdByText(t) {
  const who = t.created_by_name || T("unknown");
  return t.created_at ? `${who} · ${fmtDate(String(t.created_at).slice(0, 10))}` : who;
}

// The vendor menu in a form (tasks and spare parts share one vendor list).
// "+ New vendor" opens a small form right inside the window. Returns a function that gives
// the chosen vendor id on Save, creating the new vendor first when needed.
function vendorPicker(back) {
  const nvFields = [
    { name: "nv_company", label: T("company"), row: "n1" }, { name: "nv_trade", label: T("trade"), row: "n1" },
    { name: "nv_contact_name", label: T("contact_name"), row: "n2" }, { name: "nv_phone", label: T("phone"), type: "tel", row: "n2" },
    { name: "nv_email", label: T("email"), type: "email", row: "n3" }, { name: "nv_hourly_rate", label: T("hourly_rate"), type: "number", row: "n3" },
  ];
  const sel = $('[name="vendor_id"]', back);
  (sel.closest(".row2") || sel.closest(".field")).insertAdjacentHTML("afterend",
    `<div class="subform" id="newVendor" hidden><div class="subform-title">${esc(T("add_vendor"))}</div>${formHtml(nvFields, {})}
      <p class="small muted" style="margin:0">${esc(T("new_vendor_hint"))}</p></div>`);
  const box = $("#newVendor", back);
  sel.addEventListener("change", () => {
    box.hidden = sel.value !== "new";
    if (!box.hidden) $('[name="nv_company"]', back).focus();
  });
  // Cancel on a page form puts the stored values back: hide the box again too
  $("#mform", back).addEventListener("reset-done", () => { box.hidden = true; });
  return async () => {
    if (sel.value !== "new") return sel.value === "" ? null : Number(sel.value);
    const nv = readForm(box, nvFields);
    if (!nv.nv_company) { $('[name="nv_company"]', back).focus(); throw new Error(`${T("company")}?`); }
    const body = { active: true };
    for (const [k, val] of Object.entries(nv)) body[k.slice(3)] = val;
    const v = await api("/api/vendors", { method: "POST", body });
    // keep the new vendor selected, so a second click on Save doesn't create it twice
    sel.insertAdjacentHTML("beforeend", `<option value="${v.id}">${esc(v.company)}</option>`);
    sel.value = String(v.id);
    box.hidden = true;
    state.vendors.push(v);
    return v.id;
  };
}

async function taskForm(asset, task, { container = null } = {}) {
  if (!state.users.length) state.users = await api("/api/users");
  state.vendors = await api("/api/vendors");
  const inline = Boolean(container && task);
  const values = task || { interval_value: 1, interval_unit: "years", next_due: todayIso(), remind_days_before: 7, active: true };
  const fields = taskFields(asset, task);
  // new task: pick files now, they are uploaded right after the task is created
  if (!task && can("attachments.add")) fields.push({ name: "files", label: T("docs_and_receipts"), type: "file" });
  let resolveVendor = async () => null;
  const back = openForm({
    title: task ? T("edit") : T("add_task"),
    fields, values,
    container: inline ? container : null,
    // on the task page, "created by" and the files are already shown next to the form
    intro: task && !inline ? `<p class="small muted form-meta">${esc(T("created_by"))}: ${esc(createdByText(task))}</p>` : "",
    outro: inline ? "" : docsOutro(task),
    onSubmit: async (v) => {
      const files = v.files || [];
      delete v.files;
      v.vendor_id = await resolveVendor();
      if (v.interval_unit === "none") v.interval_value = 0;
      if (v.interval_unit !== "none" && !v.interval_value) v.interval_value = 1;
      if ("counter_interval" in v && !v.counter_interval) { v.counter_interval = null; v.counter_next_due = null; }
      // fields the form doesn't show keep their stored value
      if (task) for (const k of ["counter_interval", "counter_next_due", "counter_remind_before"]) if (!(k in v)) v[k] = task[k] ?? null;
      if (task && task.counter_remind_before != null) v.counter_remind_before = task.counter_remind_before;
      if (task) await api(`/api/tasks/${task.id}`, { method: "PUT", body: v });
      else {
        const created = await api(`/api/assets/${asset.id}/tasks`, { method: "POST", body: v });
        for (const f of files) await uploadFile("task", created.id, f);
      }
      toast(T("saved")); render();
    },
    onDelete: task ? async () => { await api(`/api/tasks/${task.id}`, { method: "DELETE" }); location.hash = `#/asset/${asset.id}`; } : null,
    editPerm: task ? "tasks.edit" : "tasks.create", deletePerm: "tasks.delete",
  });
  resolveVendor = vendorPicker(back);
  if (!inline) mountDocs("task", task);
}

function componentForm(asset, c) {
  const fields = [
    { name: "name", label: T("name"), required: true },
    { name: "brand", label: T("brand"), row: "b" }, { name: "model", label: T("model"), row: "b" },
    { name: "serial_number", label: T("serial"), row: "s" }, { name: "installed_on", label: T("installed_on"), type: "date", row: "s" },
    { name: "notes", label: T("notes"), type: "textarea" },
  ];
  docsField(fields, c);
  openForm({
    title: c ? T("edit") : T("add_component"), fields, values: c || {}, outro: docsOutro(c),
    onSubmit: async (v) => {
      const files = v.files; delete v.files;
      if (c) await api(`/api/components/${c.id}`, { method: "PUT", body: v });
      else await uploadAll("component", (await api(`/api/assets/${asset.id}/components`, { method: "POST", body: v })).id, files);
      toast(T("saved")); render();
    },
    onDelete: c ? async () => { await api(`/api/components/${c.id}`, { method: "DELETE" }); render(); } : null,
    editPerm: c ? "components.edit" : "components.create", deletePerm: "components.delete",
  });
  mountDocs("component", c);
}

// A purchase adds to stock and is counted as money spent on the thing
function purchaseDialog(p) {
  const qty = p.on_shopping_list ? p.qty_to_buy : Math.max(p.min_qty - p.qty_in_stock, 1);
  const fields = [
    { name: "qty", label: T("quantity"), type: "number", int: true, step: 1, default: Math.max(qty, 1), row: "q" },
    { name: "unit_price", label: T("unit_price"), type: "number", default: p.unit_price ?? "", row: "q" },
    { name: "bought_on", label: T("bought_on"), type: "date", default: todayIso() },
    { name: "files", label: T("receipt_or_doc"), type: "file" },
  ];
  openForm({
    title: `${T("register_purchase")}: ${p.name}`, fields, submitLabel: T("bought"),
    onSubmit: async (v) => {
      const res = await api(`/api/parts/${p.id}/bought`, { method: "POST", body: { qty: Math.max(v.qty || 1, 1), unit_price: v.unit_price, bought_on: v.bought_on || todayIso() } });
      for (const f of v.files) await uploadFile("purchase", res.last_purchase_id, f);
      toast(v.unit_price != null ? `${T("bought_ok")}: ${money((v.qty || 1) * v.unit_price)}` : T("bought_ok"));
      render();
    },
  });
}

async function purchaseHistory(container, partId) {
  const rows = await api(`/api/purchases?part_id=${partId}`);
  if (!rows.length) { container.innerHTML = ""; return; }
  container.innerHTML = `<h3 style="margin:4px 0 6px">${esc(T("purchases"))}</h3><ul class="list-plain" style="margin-bottom:18px">${rows.map((r) => `
    <li style="flex-wrap:wrap"><span class="grow">${fmtDate(r.bought_on)}, ${r.qty} ${esc(T("pcs"))}</span><span class="money">${esc(money(r.total))}</span>
      <button class="btn ghost small" type="button" data-perm="history.delete" data-rmbuy="${r.id}" aria-label="${esc(T("delete"))}">${ICON.x}</button>
      <div data-pfiles="${r.id}" style="flex-basis:100%"></div></li>`).join("")}</ul>`;
  for (const el of $$("[data-pfiles]", container)) miniFiles(el, "purchase", Number(el.dataset.pfiles));
  $$("[data-rmbuy]", container).forEach((b) => b.onclick = async () => {
    if (!confirm(T("confirm_delete"))) return;
    try { await api(`/api/purchases/${b.dataset.rmbuy}`, { method: "DELETE" }); closeModal(); toast(T("deleted")); render(); } catch (e) { fail(e); }
  });
}

async function partForm(asset, p) {
  state.vendors = await api("/api/vendors");
  const fields = [
    { name: "name", label: T("name"), required: true },
    { name: "component_id", label: T("component"), type: "select", numeric: true, options: [["", T("none")], ...asset.components.map((c) => [c.id, c.name])] },
    { name: "part_number", label: T("part_number"), row: "p" },
    { name: "vendor_id", label: T("supplier"), type: "select", numeric: true, options: vendorOptions(p?.vendor_id ?? null), row: "p" },
    { name: "url", label: T("url"), type: "url" },
    { name: "unit_price", label: T("unit_price"), type: "number", row: "q" }, { name: "qty_in_stock", label: T("in_stock"), type: "number", int: true, step: 1, row: "q" },
    { name: "min_qty", label: T("min_qty"), type: "number", int: true, step: 1, row: "m" }, { name: "qty_to_buy", label: T("qty_to_buy"), type: "number", int: true, step: 1, row: "m" },
    { name: "on_shopping_list", label: T("on_list"), type: "checkbox" },
  ];
  docsField(fields, p);
  let resolveVendor = async () => null;
  const back = openForm({
    title: p ? T("edit") : T("add_part"), fields, values: p || { qty_in_stock: 0, min_qty: 0, qty_to_buy: 1 },
    intro: p ? `<div id="buyhist"></div>` : "", outro: docsOutro(p),
    onSubmit: async (v) => {
      const files = v.files; delete v.files;
      v.vendor_id = await resolveVendor();
      if (p) await api(`/api/parts/${p.id}`, { method: "PUT", body: v });
      else await uploadAll("part", (await api(`/api/assets/${asset.id}/parts`, { method: "POST", body: v })).id, files);
      toast(T("saved")); render();
    },
    onDelete: p ? async () => { await api(`/api/parts/${p.id}`, { method: "DELETE" }); render(); } : null,
    editPerm: "parts.manage", deletePerm: "parts.manage",
  });
  resolveVendor = vendorPicker(back);
  if (p) purchaseHistory($("#buyhist"), p.id).catch(fail);
  mountDocs("part", p);
}

function warrantyForm(asset, w) {
  const fields = [
    { name: "title", label: T("title"), required: true },
    { name: "component_id", label: T("component"), type: "select", numeric: true, options: [["", T("none")], ...asset.components.map((c) => [c.id, c.name])] },
    { name: "provider", label: T("provider"), row: "p" }, { name: "reference", label: T("reference"), row: "p" },
    { name: "start_date", label: T("start_date"), type: "date", row: "d" }, { name: "end_date", label: T("end_date"), type: "date", row: "d" },
    { name: "notes", label: T("notes"), type: "textarea" },
  ];
  openForm({
    title: w ? T("edit") : T("add_warranty"), fields, values: w || {},
    intro: w ? `<div id="wfiles" style="margin-bottom:16px"></div>` : "",
    onSubmit: async (v) => {
      if (w) await api(`/api/warranties/${w.id}`, { method: "PUT", body: v });
      else await api(`/api/assets/${asset.id}/warranties`, { method: "POST", body: v });
      toast(T("saved")); render();
    },
    onDelete: w ? async () => { await api(`/api/warranties/${w.id}`, { method: "DELETE" }); render(); } : null,
    editPerm: "warranties.manage", deletePerm: "warranties.manage",
  });
  if (w) filesWidget($("#wfiles"), "warranty", w.id);
}

async function pageAsset(main, id) {
  const a = await api(`/api/assets/${id}`);
  if (!state.users.length) state.users = await api("/api/users");
  const tabs = [["tasks", T("tasks"), a.tasks.filter((t) => t.active).length], ["components", T("components"), a.components.length],
    ["parts", T("parts"), a.parts.length], ["warranties", T("warranties"), a.warranties.length], ["files", T("files"), a.attachments.length]];
  if (!tabs.some(([k]) => k === state.assetTab)) state.assetTab = "tasks";
  main.innerHTML = `
    <a class="crumb" href="#/assets">${esc(T("things_title"))}</a>
    <div class="page-head"><span class="kind-icon">${kindIcon(a.kind)}</span>
      <div class="grow"><h1>${esc(a.name)}</h1><div class="sub">${esc(T(`kind_${a.kind}`))}${a.location ? `, ${esc(a.location)}` : ""}${a.total_cost ? `. ${esc(T("total_cost"))}: ${esc(money(a.total_cost))}` : ""}</div></div>
      <div class="actions"><button class="btn" id="tpl" data-perm="templates.apply">${ICON.template}${esc(T("use_template"))}</button><button class="btn" id="printBtn">${ICON.print}${esc(T("print"))}</button><button class="btn" id="edit" data-perm="assets.edit">${esc(T("edit"))}</button></div></div>
    ${a.description ? `<p class="muted">${esc(a.description)}</p>` : ""}
    ${a.counter_unit !== "none" ? `<div class="panel counter-box"><div class="grow"><div class="small muted">${esc(T(a.counter_unit === "km" ? "counter_km" : "counter_hours"))}</div>
        <div class="counter-big">${a.counter_value != null ? esc(counterVal(a.counter_value, a.counter_unit)) : "–"}</div>
        <div class="small muted">${a.counter_on ? esc(T("counter_updated", fmtDate(a.counter_on))) : esc(T("counter_never"))}</div></div>
      <button class="btn primary" id="counterBtn" data-perm="counters.record">${esc(T("counter_update"))}</button></div>` : ""}
    <div class="tabs" role="tablist">${tabs.map(([k, l, n]) => `<button role="tab" data-tab="${k}" class="${state.assetTab === k ? "active" : ""}">${esc(l)} <span class="count">${n}</span></button>`).join("")}</div>
    <div id="tab"></div>`;
  $("#edit").onclick = () => assetForm(a);
  $("#tpl").onclick = () => templateDialog(a);
  $("#printBtn").onclick = () => openPrint(a.id);
  $("#counterBtn")?.addEventListener("click", () => counterDialog(a));
  $$("[data-tab]", main).forEach((b) => b.onclick = () => { state.assetTab = b.dataset.tab; pageAsset(main, id); });
  const tab = $("#tab");
  const addBtn = (label, idAttr, perm) => can(perm) ? `<div class="actions" style="margin-bottom:14px"><button class="btn primary" id="${idAttr}">${ICON.plus}${esc(label)}</button></div>` : "";

  if (state.assetTab === "tasks") {
    tab.innerHTML = addBtn(T("add_task"), "addTask", "tasks.create") + (a.tasks.length
      ? `<div class="entries">${a.tasks.map((t) => entryHtml(t, { showAsset: false })).join("")}</div>`
      : `<div class="empty"><p>${esc(T("template_none"))}</p><button class="btn" id="tpl2" data-perm="templates.apply">${esc(T("use_template"))}</button></div>`);
    $("#addTask")?.addEventListener("click", () => taskForm(a));
    $("#tpl2")?.addEventListener("click", () => templateDialog(a));
  } else if (state.assetTab === "components") {
    tab.innerHTML = addBtn(T("add_component"), "addC", "components.create") + (a.components.length ? `<table class="table"><thead><tr>
        <th>${esc(T("name"))}</th><th>${esc(T("brand"))} / ${esc(T("model"))}</th><th>${esc(T("serial"))}</th><th>${esc(T("installed_on"))}</th></tr></thead><tbody>
        ${a.components.map((c) => `<tr class="clickable" data-id="${c.id}"><td><b>${esc(c.name)}</b></td>
          <td data-l="${esc(T("model"))}">${esc([c.brand, c.model].filter(Boolean).join(" "))}</td><td data-l="${esc(T("serial"))}">${esc(c.serial_number)}</td>
          <td data-l="${esc(T("installed_on"))}">${fmtDate(c.installed_on)}</td></tr>`).join("")}</tbody></table>`
      : `<div class="empty"><p>${esc(T("no_components"))}</p></div>`);
    $("#addC")?.addEventListener("click", () => componentForm(a));
    $$("tr[data-id]", tab).forEach((r) => r.onclick = () => componentForm(a, a.components.find((c) => c.id === Number(r.dataset.id))));
  } else if (state.assetTab === "parts") {
    tab.innerHTML = addBtn(T("add_part"), "addP", "parts.manage") + (a.parts.length ? `<table class="table"><thead><tr>
        <th>${esc(T("name"))}</th><th>${esc(T("part_number"))}</th><th>${esc(T("supplier"))}</th><th class="num">${esc(T("in_stock"))}</th><th class="num">${esc(T("unit_price"))}</th><th></th><th></th></tr></thead><tbody>
        ${a.parts.map((p) => `<tr class="clickable" data-id="${p.id}"><td><b>${esc(p.name)}</b>${p.component_name ? `<div class="small muted">${esc(p.component_name)}</div>` : ""}</td>
          <td data-l="${esc(T("part_number"))}">${esc(p.part_number)}</td><td data-l="${esc(T("supplier"))}">${p.vendor_id ? `<a href="#/vendor/${p.vendor_id}" data-stop>${esc(p.supplier)}</a>` : esc(p.supplier)}</td>
          <td class="num" data-l="${esc(T("in_stock"))}">${p.qty_in_stock}${p.min_qty ? ` / ${p.min_qty}` : ""}</td>
          <td class="num" data-l="${esc(T("unit_price"))}">${esc(money(p.unit_price))}</td>
          <td>${p.below_min ? `<span class="pill red">${esc(T("below_min"))}</span>` : ""}${p.on_shopping_list ? ` <span class="pill amber">${esc(T("shopping_items"))}</span>` : ""}</td>
          <td class="num"><button class="btn small" data-perm="parts.manage" data-buy="${p.id}">${ICON.check}${esc(T("bought"))}</button></td></tr>`).join("")}</tbody></table>`
      : `<div class="empty"><p>${esc(T("no_parts"))}</p></div>`);
    $("#addP")?.addEventListener("click", () => partForm(a).catch(fail));
    $$("tr[data-id]", tab).forEach((r) => r.onclick = () => partForm(a, a.parts.find((p) => p.id === Number(r.dataset.id))).catch(fail));
    $$("[data-stop]", tab).forEach((l) => l.onclick = (e) => e.stopPropagation());
    $$("[data-buy]", tab).forEach((b) => b.onclick = (e) => {
      e.stopPropagation();
      purchaseDialog(a.parts.find((p) => p.id === Number(b.dataset.buy)));
    });
  } else if (state.assetTab === "warranties") {
    tab.innerHTML = addBtn(T("add_warranty"), "addW", "warranties.manage") + (a.warranties.length ? `<table class="table"><thead><tr>
        <th>${esc(T("title"))}</th><th>${esc(T("provider"))}</th><th>${esc(T("reference"))}</th><th>${esc(T("end_date"))}</th></tr></thead><tbody>
        ${a.warranties.map((w) => {
          const left = w.end_date ? daysFromToday(w.end_date) : null;
          const pill = w.expired ? `<span class="pill">${esc(T("expired"))}</span>` : left != null && left <= 90 ? `<span class="pill amber">${fmtDate(w.end_date)}</span>` : left != null ? `<span class="pill green">${fmtDate(w.end_date)}</span>` : "";
          return `<tr class="clickable" data-id="${w.id}"><td><b>${esc(w.title)}</b>${w.component_name ? `<div class="small muted">${esc(w.component_name)}</div>` : ""}</td>
          <td data-l="${esc(T("provider"))}">${esc(w.provider)}</td><td data-l="${esc(T("reference"))}">${esc(w.reference)}</td><td data-l="${esc(T("end_date"))}">${pill}</td></tr>`;
        }).join("")}</tbody></table>`
      : `<div class="empty"><p>${esc(T("no_warranties"))}</p></div>`);
    $("#addW")?.addEventListener("click", () => warrantyForm(a));
    $$("tr[data-id]", tab).forEach((r) => r.onclick = () => warrantyForm(a, a.warranties.find((w) => w.id === Number(r.dataset.id))));
  } else {
    tab.innerHTML = `<div id="afiles" style="max-width:640px"></div>`;
    await filesWidget($("#afiles"), "asset", a.id);
  }
}

// ---------------------------------------------------------------- task detail
async function pageTask(main, id) {
  const t = await api(`/api/tasks/${id}`);
  const s = stamp(t.next_due);
  main.innerHTML = `
    <a class="crumb" href="#/asset/${t.asset_id}">${esc(t.asset_name)}</a>
    <div class="task-hero ${t.status}">
      <div class="big-date">${s.d}<small>${esc(s.m)}</small></div>
      <div><h1>${esc(t.title)}</h1>
        <div class="sub muted" style="margin-top:4px"><span class="when ${t.status}">${esc(whenText(t))}</span></div>
        <dl class="facts">
          <div><dt>${esc(T("repeat"))}</dt><dd>${esc(intervalText(t))}</dd></div>
          <div><dt>${esc(T("last_done"))}</dt><dd>${t.last_done ? fmtDate(t.last_done) : esc(T("never"))}</dd></div>
          <div><dt>${esc(T("total_cost"))}</dt><dd>${esc(money(t.total_cost))}</dd></div>
          <div><dt>${esc(T("assigned_to"))}</dt><dd>${esc(t.assigned_to_name || T("anyone"))}</dd></div>
          ${t.counter_unit ? `<div><dt>${esc(T("next_at"))}</dt><dd>${t.counter_next_due != null ? esc(counterVal(t.counter_next_due, t.counter_unit)) : "–"}${t.counter_current != null ? `<div class="small muted">${esc(T("counter_now_is", counterVal(t.counter_current, t.counter_unit)))}</div>` : ""}</dd></div>` : ""}
          ${t.vendor_name ? `<div><dt>${esc(T("vendor"))}</dt><dd><a href="#/vendor/${t.vendor_id}">${esc(t.vendor_name)}</a>${t.vendor_phone ? `<div class="small"><a href="tel:${esc(t.vendor_phone.replace(/\s+/g, ""))}">${esc(t.vendor_phone)}</a></div>` : ""}${t.vendor_email ? `<div class="small"><a href="mailto:${esc(t.vendor_email)}">${esc(t.vendor_email)}</a></div>` : ""}</dd></div>` : ""}
          <div><dt>${esc(T("created_by"))}</dt><dd>${esc(createdByText(t))}</dd></div>
          ${t.component_name ? `<div><dt>${esc(T("component"))}</dt><dd>${esc(t.component_name)}</dd></div>` : ""}
          ${t.estimated_cost != null ? `<div><dt>${esc(T("estimated_cost"))}</dt><dd>${esc(money(t.estimated_cost))}</dd></div>` : ""}
        </dl></div></div>
    ${t.active ? `<div class="actions" style="margin-bottom:24px"><button class="btn primary" data-perm="tasks.complete" data-done="${t.id}">${ICON.check}${esc(T("mark_done"))}</button></div>` : ""}
    ${t.vendor_id && t.active ? vendorBox(t) : ""}
    <div class="two-col"><div class="section"><h2>${esc(T("details"))}</h2><div class="panel task-edit" id="taskEdit"><div class="loading">…</div></div></div>
    <div><div class="section"><h2>${esc(T("history"))} <span class="count">${t.completions.length}</span></h2>
      ${t.completions.length ? `<ul class="history">${t.completions.map((c) => `<li>
        <div class="h-top"><b>${fmtDate(c.done_on)}</b>${c.cost != null ? `<span class="money">${esc(money(c.cost))}</span>` : ""}
          ${c.vendor_name ? `<a class="small" href="#/vendor/${c.vendor_id}">${esc(c.vendor_name)}</a>` : c.done_by_name ? `<span class="small muted">${esc(c.done_by_name)}</span>` : ""}
          ${c.counter_value != null && t.counter_unit ? `<span class="small muted">${esc(counterVal(c.counter_value, t.counter_unit))}</span>` : ""}
          <button class="btn ghost small" data-perm="history.delete" data-rmc="${c.id}" aria-label="${esc(T("delete"))}">${ICON.x}</button></div>
        ${c.notes ? `<div class="small" style="white-space:pre-wrap">${esc(c.notes)}</div>` : ""}
        <div data-cfiles="${c.id}"></div></li>`).join("")}</ul>`
        : `<p class="muted">${esc(T("no_history"))}</p>`}</div>
      <div class="section"><h2>${esc(T("files"))}</h2><div id="tfiles"></div></div></div></div>`;
  // the task opens ready to edit: change a field, then Save
  const editBox = $("#taskEdit");
  api(`/api/assets/${t.asset_id}`)
    .then((asset) => { if (editBox.isConnected) return taskForm(asset, t, { container: editBox }); })
    .catch(fail);
  $("#vsRequest")?.addEventListener("click", () => vendorRequestDialog(t));
  $("#vsConfirm")?.addEventListener("click", () => vendorConfirmDialog(t));
  $("#vsReset")?.addEventListener("click", async () => {
    try { await api(`/api/tasks/${t.id}/vendor-status`, { method: "PATCH", body: { status: "none" } }); render(); } catch (e) { fail(e); }
  });
  $$("[data-rmc]", main).forEach((b) => b.onclick = async () => {
    if (!confirm(T("confirm_delete"))) return;
    try { await api(`/api/completions/${b.dataset.rmc}`, { method: "DELETE" }); render(); } catch (e) { fail(e); }
  });
  // receipts on each history entry: open them, or attach one afterwards
  for (const el of $$("[data-cfiles]", main)) miniFiles(el, "completion", Number(el.dataset.cfiles));
  await filesWidget($("#tfiles"), "task", t.id);
}

// ---------------------------------------------------------------- vendor workflow on a task
function vendorBox(t) {
  const st = t.vendor_status;
  const text = st === "confirmed" ? T("vs_confirmed_text", t.vendor_name, fmtDate(t.vendor_booked_for))
    : st === "requested" ? T("vs_requested_text", t.vendor_name, fmtDate(t.vendor_requested_on))
    : T("vs_none_text", t.vendor_name);
  return `<div class="panel vendor-box ${st || "none"}" style="margin-bottom:24px">
    <div class="grow"><div class="small muted">${esc(T("vendor_job"))}</div><b>${esc(text)}</b></div>
    <div class="actions" data-perm="tasks.edit">
      <button class="btn${st ? "" : " primary"}" id="vsRequest">${esc(T(st ? "vs_send_again" : "vs_send"))}</button>
      <button class="btn${st === "requested" ? " primary" : ""}" id="vsConfirm">${esc(T(st === "confirmed" ? "vs_change_date" : "vs_confirm"))}</button>
      ${st ? `<button class="btn ghost" id="vsReset">${esc(T("vs_reset"))}</button>` : ""}
    </div></div>`;
}

async function vendorRequestDialog(t) {
  let v;
  try { v = await api(`/api/vendors/${t.vendor_id}`); } catch (e) { return fail(e); }
  const me = state.user?.name || "";
  const lines = [
    T("req_hello", v.contact_name || v.company), "",
    T("req_intro", t.title, t.asset_name),
    t.component_name ? `${T("component")}: ${t.component_name}` : "",
    t.description ? t.description : "",
    t.next_due ? T("req_by", fmtDate(t.next_due)) : "",
    "", T("req_ask"), "", T("req_regards"), me,
  ].filter((x, i, arr) => x !== "" || (arr[i - 1] !== "" && i > 0));
  const subject = T("req_subject", t.title, t.asset_name);
  const back = modal({
    title: T("vs_send"),
    html: `<p class="small muted" style="margin-top:0">${esc(T("req_help"))}</p>
      <label class="field"><span>${esc(T("req_subject_label"))}</span><input id="rqSubject" value="${esc(subject)}"></label>
      <label class="field"><span>${esc(T("req_text"))}</span><textarea id="rqBody" rows="11">${esc(lines.join("\n"))}</textarea></label>`,
    footer: `<button class="btn left" data-copy>${esc(T("copy"))}</button>
      ${v.phone ? `<button class="btn" data-sms>${esc(T("send_sms"))}</button>` : ""}
      ${v.email ? `<button class="btn primary" data-mail>${esc(T("send_email"))}</button>` : ""}`,
  });
  const body = () => $("#rqBody", back).value;
  const markRequested = async () => {
    try { await api(`/api/tasks/${t.id}/vendor-status`, { method: "PATCH", body: { status: "requested" } }); } catch (e) { fail(e); }
    closeModal(); toast(T("vs_marked_requested")); render();
  };
  $("[data-mail]", back)?.addEventListener("click", () => {
    location.href = `mailto:${encodeURIComponent(v.email)}?subject=${encodeURIComponent($("#rqSubject", back).value)}&body=${encodeURIComponent(body())}`;
    markRequested();
  });
  $("[data-sms]", back)?.addEventListener("click", () => {
    location.href = `sms:${v.phone.replace(/\s+/g, "")}?&body=${encodeURIComponent(body())}`;
    markRequested();
  });
  $("[data-copy]", back).addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(body()); } catch { $("#rqBody", back).select(); document.execCommand("copy"); }
    markRequested();
  });
  if (!v.email && !v.phone) toast(T("req_no_contact"), true);
}

function vendorConfirmDialog(t) {
  openForm({
    title: T("vs_confirm"),
    fields: [{ name: "on", label: T("vs_agreed_date"), type: "date", required: true }],
    values: { on: t.vendor_booked_for || t.next_due || todayIso() },
    onSubmit: async (v) => { await api(`/api/tasks/${t.id}/vendor-status`, { method: "PATCH", body: { status: "confirmed", on: v.on } }); toast(T("saved")); render(); },
  });
}

// ---------------------------------------------------------------- vendor page
async function pageVendor(main, id) {
  const h = await api(`/api/vendors/${id}/history`);
  const v = h.vendor;
  const contact = [
    v.contact_name ? esc(v.contact_name) : "",
    v.phone ? `<a href="tel:${esc(v.phone.replace(/\s+/g, ""))}">${esc(v.phone)}</a>` : "",
    v.email ? `<a href="mailto:${esc(v.email)}">${esc(v.email)}</a>` : "",
    v.website ? `<a href="${esc(/^https?:/i.test(v.website) ? v.website : `https://${v.website}`)}" target="_blank" rel="noopener">${esc(v.website)}</a>` : "",
  ].filter(Boolean).join(" · ");
  const facts = [
    v.address ? [T("address"), esc(v.address)] : null,
    v.org_number ? [T("org_number"), esc(v.org_number)] : null,
    v.hourly_rate != null ? [T("hourly_rate"), esc(money(v.hourly_rate))] : null,
    v.rate_notes ? [T("rate_notes"), esc(v.rate_notes)] : null,
  ].filter(Boolean);
  main.innerHTML = `
    <a class="crumb" href="#/settings">${esc(T("vendors"))}</a>
    <div class="page-head"><div class="grow"><h1>${esc(v.company)}</h1><div class="sub">${esc(v.trade || "")}${v.trade && contact ? " · " : ""}${contact}</div></div>
      <div class="actions"><button class="btn" id="editV" data-perm="vendors.manage">${esc(T("edit"))}</button></div></div>
    <div class="vstats">
      <div class="stat"><div class="small muted">${esc(T("spent_total"))}</div><b>${esc(money(h.total_spent))}</b></div>
      <div class="stat"><div class="small muted">${esc(T("spent_this_year"))}</div><b>${esc(money(h.spent_this_year))}</b></div>
      <div class="stat"><div class="small muted">${esc(T("jobs_done"))}</div><b>${h.jobs.length}</b></div>
    </div>
    ${facts.length ? `<dl class="facts" style="margin-bottom:20px">${facts.map(([k, val]) => `<div><dt>${esc(k)}</dt><dd>${val}</dd></div>`).join("")}</dl>` : ""}
    ${v.notes ? `<div class="panel" style="margin-bottom:20px;white-space:pre-wrap">${esc(v.notes)}</div>` : ""}
    <div class="two-col"><div class="section"><h2>${esc(T("open_jobs"))} <span class="count">${h.open_tasks.length}</span></h2>
      ${h.open_tasks.length ? `<div class="entries">${h.open_tasks.map((t) => entryHtml(t)).join("")}</div>` : `<p class="muted">${esc(T("no_open_jobs"))}</p>`}</div>
    <div class="section"><h2>${esc(T("job_history"))} <span class="count">${h.jobs.length}</span></h2>
      ${h.jobs.length ? `<ul class="history">${h.jobs.map((j) => `<li><div class="h-top"><b>${fmtDate(j.done_on)}</b>${j.cost != null ? `<span class="money">${esc(money(j.cost))}</span>` : ""}</div>
        <div><a href="#/task/${j.task_id}">${esc(j.task_title)}</a> <span class="small muted">${esc(j.asset_name)}</span></div>
        ${j.notes ? `<div class="small" style="white-space:pre-wrap">${esc(j.notes)}</div>` : ""}<div data-cfiles="${j.completion_id}"></div></li>`).join("")}</ul>`
        : `<p class="muted">${esc(T("no_jobs_yet"))}</p>`}</div></div>`;
  $("#editV")?.addEventListener("click", () => vendorForm(v));
  for (const el of $$("[data-cfiles]", main)) miniFiles(el, "completion", Number(el.dataset.cfiles));
}

// ---------------------------------------------------------------- calendar
async function pageCalendar(main) {
  const base = state.calMonth || new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  state.calMonth = base;
  const first = new Date(base);
  const startOffset = (first.getDay() + 6) % 7; // Monday first
  const gridStart = new Date(first); gridStart.setDate(1 - startOffset);
  const gridEnd = new Date(gridStart); gridEnd.setDate(gridStart.getDate() + 41);
  const iso = (d) => d.toLocaleDateString("sv-SE");
  const [events, me, assets] = await Promise.all([
    api(`/api/calendar?start=${iso(gridStart)}&end=${iso(gridEnd)}&${filterQuery()}`),
    api("/api/me"),
    loadAssetsForFilter(),
  ]);
  const byDay = {};
  for (const e of events) (byDay[e.date] ||= []).push(e);
  const evHtml = (e) => {
    const cls = e.type === "warranty" ? "warranty" : e.type === "done" ? "done" : e.projected ? "projected" : e.status;
    const href = e.type === "warranty" ? `#/asset/${e.asset_id}` : `#/task/${e.id}`;
    return `<a class="ev ${cls}" href="${href}" title="${esc(e.title)}, ${esc(e.asset)}">${esc(e.title)}</a>`;
  };
  const monthName = base.toLocaleDateString(locale(), { month: "long", year: "numeric" });
  const dows = [...Array(7)].map((_, i) => new Date(2024, 0, 1 + i).toLocaleDateString(locale(), { weekday: "short" }));
  let cells = "";
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart); d.setDate(gridStart.getDate() + i);
    const k = iso(d);
    cells += `<div class="day ${d.getMonth() !== base.getMonth() ? "other" : ""} ${k === todayIso() ? "today" : ""}">
      <span class="num">${d.getDate()}</span>${(byDay[k] || []).map(evHtml).join("")}</div>`;
  }
  const monthDays = Object.keys(byDay).filter((k) => k.slice(0, 7) === iso(base).slice(0, 7)).sort();
  main.innerHTML = `<div class="page-head"><div class="grow"><h1>${esc(T("calendar_title"))}</h1></div>
      <button class="btn" id="printBtn">${ICON.print}${esc(T("print"))}</button></div>
    ${assetChips(assets)}
    <div class="cal-head"><h2>${esc(monthName)}</h2>
      <button class="btn small" id="prev" aria-label="${esc(T("prev"))}">‹</button>
      <button class="btn small" id="today">${esc(T("this_month"))}</button>
      <button class="btn small" id="next" aria-label="${esc(T("next"))}">›</button></div>
    <div class="cal">${dows.map((d) => `<div class="dow">${esc(d)}</div>`).join("")}${cells}</div>
    <div class="cal-list">${monthDays.length ? monthDays.map((k) => `<div class="day-group"><h3>${esc(new Date(k + "T12:00:00").toLocaleDateString(locale(), { weekday: "long", day: "numeric", month: "long" }))}</h3>
      ${byDay[k].map(evHtml).join("")}</div>`).join("") : `<p class="muted">–</p>`}</div>
    <div class="legend"><span class="ev overdue">${esc(T("overdue"))}</span><span class="ev ok">${esc(T("legend_due"))}</span>
      <span class="ev projected">${esc(T("legend_projected"))}</span><span class="ev done">${esc(T("legend_done"))}</span><span class="ev warranty">${esc(T("legend_warranty"))}</span></div>
    <div class="panel ical-box"><h3>${esc(T("ical_title"))}</h3><p class="muted small">${esc(T("ical_help"))}</p>
      <div class="copyline"><input type="text" readonly value="${esc(me.ical_url)}" id="icalurl"><button class="btn" id="copy">${esc(T("copy"))}</button></div>
      <button class="btn ghost small" id="reset" style="margin-top:8px">${esc(T("reset_link"))}</button></div>`;
  const move = (n) => { state.calMonth = new Date(base.getFullYear(), base.getMonth() + n, 1); pageCalendar(main); };
  bindAssetChips(main, () => pageCalendar(main));
  $("#printBtn").onclick = () => {
    // print the month on screen
    const last = new Date(base.getFullYear(), base.getMonth() + 1, 0);
    state.print = { ...(state.print || {}), from: iso(base), to: iso(last) };
    openPrint();
  };
  $("#prev").onclick = () => move(-1);
  $("#next").onclick = () => move(1);
  $("#today").onclick = () => { state.calMonth = null; pageCalendar(main); };
  $("#copy").onclick = async () => {
    const input = $("#icalurl");
    try { await navigator.clipboard.writeText(input.value); } catch { input.select(); document.execCommand("copy"); }
    toast(T("copied"));
  };
  $("#reset").onclick = async () => {
    if (!confirm(T("ical_reset_done"))) return;
    try { const r = await api("/api/me/ical-reset", { method: "POST" }); $("#icalurl").value = r.ical_url; toast(T("ical_reset_done")); } catch (e) { fail(e); }
  };
}

// ---------------------------------------------------------------- print: tasks per thing in a chosen period
function openPrint(assetId) {
  state.print = { ...(state.print || {}), asset: assetId ?? state.assetFilter ?? null };
  location.hash = "#/print";
}

async function pagePrint(main) {
  const addMonths = (iso, n) => { const d = new Date(iso + "T12:00:00"); d.setMonth(d.getMonth() + n); return d.toLocaleDateString("sv-SE"); };
  const p = state.print = {
    asset: state.assetFilter ?? null, from: todayIso(), to: addMonths(todayIso(), 3),
    overdue: true, repeats: true, done: false, mine: state.mine, ...(state.print || {}),
  };
  const assets = await api("/api/assets");
  if (p.asset && !assets.some((a) => a.id === p.asset)) p.asset = null;
  main.innerHTML = `<div class="page-head no-print"><div class="grow"><h1>${esc(T("print_title"))}</h1><div class="sub">${esc(T("print_sub"))}</div></div>
      <button class="btn primary" id="doPrint">${ICON.print}${esc(T("print_btn"))}</button></div>
    <div class="panel print-filters no-print">
      <label class="field"><span>${esc(T("nav_assets"))}</span><select id="pAsset"><option value="">${esc(T("all_things"))}</option>
        ${assets.map((a) => `<option value="${a.id}" ${a.id === p.asset ? "selected" : ""}>${esc(a.name)}</option>`).join("")}</select></label>
      <label class="field"><span>${esc(T("from_date"))}</span><input type="date" id="pFrom" value="${p.from}"></label>
      <label class="field"><span>${esc(T("to_date"))}</span><input type="date" id="pTo" value="${p.to}"></label>
      <div class="pf-checks">
        <label class="check"><input type="checkbox" id="pOverdue" ${p.overdue ? "checked" : ""}><span>${esc(T("include_overdue"))}</span></label>
        <label class="check"><input type="checkbox" id="pRepeats" ${p.repeats ? "checked" : ""}><span>${esc(T("include_repeats"))}</span></label>
        <label class="check"><input type="checkbox" id="pDone" ${p.done ? "checked" : ""}><span>${esc(T("include_done"))}</span></label>
        <label class="check"><input type="checkbox" id="pMine" ${p.mine ? "checked" : ""}><span>${esc(T("only_mine"))}</span></label>
      </div>
      <div class="pf-quick">${[["p_1m", 1], ["p_3m", 3], ["p_6m", 6], ["p_12m", 12]].map(([k, n]) =>
        `<button class="btn small" type="button" data-months="${n}">${esc(T(k))}</button>`).join("")}</div>
    </div>
    <div id="sheet" class="print-sheet"><div class="loading">…</div></div>`;
  const read = () => {
    p.asset = Number($("#pAsset").value) || null;
    p.from = $("#pFrom").value || todayIso();
    p.to = $("#pTo").value || p.from;
    p.overdue = $("#pOverdue").checked; p.repeats = $("#pRepeats").checked;
    p.done = $("#pDone").checked; p.mine = $("#pMine").checked;
  };
  const redraw = () => { read(); printSheet($("#sheet"), assets).catch(fail); };
  $$(".print-filters select, .print-filters input", main).forEach((el) => el.onchange = redraw);
  $$("[data-months]", main).forEach((b) => b.onclick = () => {
    $("#pFrom").value = todayIso(); $("#pTo").value = addMonths(todayIso(), Number(b.dataset.months)); redraw();
  });
  $("#doPrint").onclick = () => window.print();
  await printSheet($("#sheet"), assets);
}

async function printSheet(sheet, assets) {
  const p = state.print;
  if (p.to < p.from) [p.from, p.to] = [p.to, p.from];
  if (daysFromToday(p.to) - daysFromToday(p.from) > 400) { sheet.innerHTML = `<div class="empty">${esc(T("range_too_long"))}</div>`; return; }
  const q = `mine=${p.mine}${p.asset ? `&asset_id=${p.asset}` : ""}`;
  const [events, tasks] = await Promise.all([api(`/api/calendar?start=${p.from}&end=${p.to}&${q}`), api(`/api/tasks?${q}`)]);
  if (!sheet.isConnected) return;
  const byId = Object.fromEntries(tasks.map((t) => [t.id, t]));
  const rows = [];
  // overdue from before the period: they still need doing
  if (p.overdue) for (const t of tasks) if (t.active && t.status === "overdue" && t.next_due && t.next_due < p.from) rows.push({ date: t.next_due, kind: "late", t });
  for (const e of events) {
    const t = byId[e.id];
    if (!t || (e.type !== "task" && e.type !== "done")) continue;
    if (e.type === "done" && !p.done) continue;
    if (e.type === "task" && e.projected && !p.repeats) continue;
    rows.push({ date: e.date, kind: e.type === "done" ? "done" : e.projected ? "repeat" : t.status === "overdue" ? "late" : "due", t });
  }
  rows.sort((a, b) => a.date.localeCompare(b.date) || a.t.title.localeCompare(b.t.title));
  const groups = new Map();
  for (const r of rows) {
    if (!groups.has(r.t.asset_id)) groups.set(r.t.asset_id, []);
    groups.get(r.t.asset_id).push(r);
  }
  const order = assets.filter((a) => groups.has(a.id));
  const thing = p.asset ? assets.find((a) => a.id === p.asset)?.name : T("all_things");
  const status = (r) => r.kind === "late" ? `<span class="pill red">${esc(T("overdue"))}</span>`
    : r.kind === "done" ? `<span class="pill green">${esc(T("legend_done"))}</span>`
    : r.kind === "repeat" ? `<span class="small muted">${esc(T("legend_projected"))}</span>` : "";
  const fullDate = (iso) => new Date(iso + "T12:00:00").toLocaleDateString(locale(), { day: "numeric", month: "short", year: "numeric" });
  sheet.innerHTML = `<div class="ps-head"><div class="grow"><div class="ps-brand">${esc(T("app"))}</div>
      <h2>${esc(T("print_heading"))}</h2>
      <div class="muted">${esc(thing || "")} · ${esc(fullDate(p.from))} – ${esc(fullDate(p.to))}${p.mine ? ` · ${esc(T("only_mine"))}` : ""}</div></div>
      <div class="small muted ps-printed">${esc(T("printed_on", fullDate(todayIso())))}<br>${esc(T("n_items", rows.length))}</div></div>
    ${order.length ? order.map((a) => {
      const list = groups.get(a.id);
      const est = list.filter((r) => r.kind !== "done").reduce((s, r) => s + (r.t.estimated_cost || 0), 0);
      return `<section class="ps-group"><h3>${esc(a.name)}${a.location ? ` <span class="muted small">${esc(a.location)}</span>` : ""}<span class="count">${list.length}</span></h3>
        <table class="ps-table"><colgroup><col style="width:26px"><col style="width:96px"><col><col style="width:13%"><col style="width:12%"><col style="width:10%"><col style="width:11%"><col style="width:9%"><col style="width:14%"></colgroup><thead><tr><th class="c-box"></th><th>${esc(T("col_date"))}</th><th>${esc(T("title"))}</th><th>${esc(T("component"))}</th>
          <th>${esc(T("repeat"))}</th><th>${esc(T("assigned_to"))}</th><th>${esc(T("vendor"))}</th><th class="num">${esc(T("col_cost"))}</th><th class="c-notes">${esc(T("notes"))}</th></tr></thead>
        <tbody>${list.map((r) => `<tr class="${r.kind}"><td class="c-box"><span class="box">${r.kind === "done" ? "✓" : ""}</span></td>
          <td class="nowrap">${esc(fullDate(r.date))}</td>
          <td><b>${esc(r.t.title)}</b> ${status(r)}${r.t.description ? `<div class="small muted ps-desc">${esc(r.t.description)}</div>` : ""}</td>
          <td>${esc(r.t.component_name || "")}</td><td>${esc(intervalText(r.t))}</td>
          <td>${esc(r.t.assigned_to_name || T("anyone"))}</td>
          <td>${esc(r.t.vendor_name || "")}${r.t.vendor_phone ? `<div class="small">${esc(r.t.vendor_phone)}</div>` : ""}</td>
          <td class="num">${r.kind !== "done" && r.t.estimated_cost != null ? esc(money(r.t.estimated_cost)) : ""}</td><td class="c-notes"></td></tr>`).join("")}</tbody>
        ${est ? `<tfoot><tr><td colspan="7">${esc(T("est_total"))}</td><td class="num">${esc(money(est))}</td><td></td></tr></tfoot>` : ""}</table></section>`;
    }).join("") : `<div class="empty">${esc(T("nothing_in_period"))}</div>`}`;
}

// ---------------------------------------------------------------- shopping
async function pageShopping(main) {
  const parts = await api("/api/shopping-list");
  const groups = {};
  for (const p of parts) (groups[p.supplier || ""] ||= []).push(p);
  main.innerHTML = `<div class="page-head"><div class="grow"><h1>${esc(T("shopping_title"))}</h1></div></div>
    ${parts.length ? Object.entries(groups).map(([sup, items]) => `<div class="shop-group"><h3>${esc(sup || T("no_supplier"))}</h3>
      ${items.map((p) => {
        const qty = p.on_shopping_list ? p.qty_to_buy : Math.max(p.min_qty - p.qty_in_stock, 1);
        return `<div class="shop-item"><span class="qty">${qty}</span>
          <span class="grow"><b>${esc(p.name)}</b>${p.part_number ? ` <span class="small muted">${esc(p.part_number)}</span>` : ""}
            <div class="small muted">${esc(p.asset_name)}${p.component_name ? `, ${esc(p.component_name)}` : ""}${p.unit_price ? `, ${esc(money(p.unit_price * qty))}` : ""}
            ${p.url ? `, <a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(T("url"))}</a>` : ""}</div></span>
          <button class="btn small" data-perm="parts.manage" data-bought="${p.id}">${ICON.check}${esc(T("bought"))}</button></div>`;
      }).join("")}</div>`).join("")
      : `<div class="empty"><p>${esc(T("shopping_empty"))}</p></div>`}`;
  $$("[data-bought]", main).forEach((b) => b.onclick = () => purchaseDialog(parts.find((p) => p.id === Number(b.dataset.bought))));
}

// ---------------------------------------------------------------- vendors
function vendorForm(v) {
  const fields = [
    { name: "company", label: T("company"), required: true, row: "c" },
    { name: "trade", label: T("trade"), row: "c" },
    { name: "contact_name", label: T("contact_name"), row: "p" },
    { name: "phone", label: T("phone"), type: "tel", row: "p" },
    { name: "email", label: T("email"), type: "email", row: "e" },
    { name: "website", label: T("website"), row: "e" },
    { name: "address", label: T("address") },
    { name: "org_number", label: T("org_number"), row: "o" },
    { name: "hourly_rate", label: T("hourly_rate"), type: "number", row: "o" },
    { name: "rate_notes", label: T("rate_notes") },
    { name: "notes", label: T("notes"), type: "textarea" },
    { name: "active", label: T("active"), type: "checkbox" },
  ];
  openForm({
    title: v ? v.company : T("add_vendor"), fields, values: v || { active: true },
    onSubmit: async (val) => {
      if (v) await api(`/api/vendors/${v.id}`, { method: "PUT", body: val });
      else await api("/api/vendors", { method: "POST", body: val });
      state.vendors = []; toast(T("saved")); render();
    },
    onDelete: v ? async () => { await api(`/api/vendors/${v.id}`, { method: "DELETE" }); state.vendors = []; render(); } : null,
    editPerm: "vendors.manage", deletePerm: "vendors.manage",
  });
}

// ---------------------------------------------------------------- settings
async function pageSettings(main) {
  state.user = await api("/api/me");
  const u = state.user;
  const manage = can("members.manage"), editRoles = can("roles.manage");
  const [users, vendors, roles, invites, signup] = await Promise.all([
    api("/api/users"), api("/api/vendors"), api("/api/roles"), manage ? api("/api/invitations") : Promise.resolve([]),
    api("/api/auth/status").catch(() => ({})),
  ]);
  state.vendors = vendors;
  state.users = users;
  const profileFields = [
    { name: "name", label: T("name"), required: true },
    { name: "lang", label: T("language"), type: "select", options: LANG_OPTIONS },
    { name: "password", label: T("new_password"), type: "password", autocomplete: "new-password" },
    { name: "email_reminders", label: T("email_reminders"), type: "checkbox" },
  ];
  const head = (title, btns = "") => `<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap"><h3 style="flex:1;margin:0">${esc(title)}</h3>${btns}</div>`;
  main.innerHTML = `<div class="page-head"><div class="grow"><h1>${esc(T("settings_title"))}</h1><div class="sub">${esc(u.email)}</div></div>
      <button class="btn" id="logout">${esc(T("log_out"))}</button></div>
    <div class="two-col"><div>
      <div class="panel"><h3>${esc(T("profile"))}</h3><form id="pform">${formHtml(profileFields, u)}<button class="btn primary">${esc(T("save"))}</button></form></div>
      <div class="panel">${head(u.group.name, (manage ? `<button class="btn ghost small" id="renameGroup">${esc(T("rename"))}</button>` : "")
          + (signup.signup_enabled ? `<button class="btn ghost small" id="newGroup">${ICON.plus}${esc(T("new_family"))}</button>` : ""))}
        <p class="small muted" style="margin-top:-4px">${esc(T("your_role"))}: <b>${esc(u.role.name)}</b></p>
        ${u.groups.length > 1 ? `<label class="field"><span>${esc(T("active_group"))}</span><select id="groupSel">${u.groups.map((g) =>
          `<option value="${g.id}" ${g.id === u.group.id ? "selected" : ""}>${esc(g.name)} (${esc(g.role)})</option>`).join("")}</select></label>` : ""}
        ${head(T("members"), manage ? `<button class="btn small" id="invite">${ICON.plus}${esc(T("invite"))}</button><button class="btn ghost small" id="addUser">${esc(T("add_user"))}</button>` : "")}
        <ul class="list-plain">${users.map((x) => `<li><span class="grow"><b>${esc(x.name)}</b>${x.id === u.id ? ` <span class="small muted">(${esc(T("you"))})</span>` : ""}
          <div class="small muted">${esc(x.email)}</div></span><span class="pill${x.role_key === "owner" ? " green" : ""}">${esc(x.role_name)}</span>
          ${manage && (x.role_key !== "owner" || u.is_owner) ? `<button class="btn ghost small" data-user="${x.id}">${esc(T("edit"))}</button>` : ""}</li>`).join("")}</ul>
        ${invites.length ? `<div class="form-sub" style="margin-top:14px">${esc(T("pending_invites"))}</div><ul class="list-plain">${invites.map((i) => `<li><span class="grow"><b>${esc(i.email)}</b>
          <div class="small muted">${esc(i.role_name)} · ${esc(T("expires", fmtDate(i.expires_at.slice(0, 10))))}</div></span>
          <button class="btn ghost small" data-copy="${esc(i.link)}">${esc(T("copy_link"))}</button>
          <button class="btn ghost small" data-uninvite="${i.id}" aria-label="${esc(T("cancel_invite"))}" title="${esc(T("cancel_invite"))}">${ICON.x}</button></li>`).join("")}</ul>` : ""}
      </div>
      <div class="panel">${head(T("roles"), editRoles ? `<button class="btn small" id="addRole">${ICON.plus}${esc(T("new_role"))}</button>` : "")}
        <p class="small muted" style="margin-top:-4px">${esc(T("roles_help"))}</p>
        <ul class="list-plain">${roles.map((r) => `<li><span class="grow"><b>${esc(r.name)}</b>${r.locked ? ` <span class="small muted">(${esc(T("locked"))})</span>` : ""}
          <div class="small muted">${esc(r.locked ? T("all_permissions") : T("n_permissions", r.permissions.length))} · ${esc(T("n_members", r.members))}</div></span>
          <button class="btn ghost small" data-role="${r.id}">${esc(editRoles && !r.locked ? T("edit") : T("show"))}</button></li>`).join("")}</ul>
      </div>
    </div><div>
      <div class="panel">${head(T("vendors"), `<button class="btn small" id="addVendor" data-perm="vendors.manage">${ICON.plus}${esc(T("add_vendor"))}</button>`)}
        ${vendors.length ? `<ul class="list-plain">${vendors.map((v) => `<li><span class="grow"><a href="#/vendor/${v.id}"><b>${esc(v.company)}</b></a>${v.trade ? ` <span class="small muted">${esc(v.trade)}</span>` : ""}
          <div class="small muted">${esc([v.contact_name, v.phone, v.email].filter(Boolean).join(" · "))}</div>
          ${v.hourly_rate != null || v.rate_notes ? `<div class="small muted">${esc([v.hourly_rate != null ? `${money(v.hourly_rate)}${T("per_hour")}` : "", v.rate_notes].filter(Boolean).join(" · "))}</div>` : ""}</span>
          ${v.open_tasks ? `<span class="pill">${esc(T("n_tasks", v.open_tasks))}</span>` : ""}${!v.active ? `<span class="pill">${esc(T("inactive_vendor"))}</span>` : ""}
          <button class="btn ghost small" data-perm="vendors.manage" data-vendor="${v.id}">${esc(T("edit"))}</button></li>`).join("")}</ul>`
          : `<p class="small muted">${esc(T("vendors_empty"))}</p>`}</div>
      <div class="panel"><h3>${esc(T("install_title"))}</h3><p class="small muted">${esc(T("install_help"))}</p></div>
      ${manage || u.is_admin ? `<div class="panel"><h3>${esc(T("reminders"))}</h3><p class="small muted">${esc(T("reminders_help"))}</p>
        <div class="actions">${u.is_admin ? `<button class="btn small" id="testmail">${esc(T("test_mail"))}</button>` : ""}${manage ? `<button class="btn small" id="prev">${esc(T("preview"))}</button>` : ""}${u.is_admin ? `<button class="btn small" id="send">${esc(T("send_now"))}</button>` : ""}</div>
        <pre id="remout" class="small" style="white-space:pre-wrap;margin:12px 0 0"></pre></div>` : ""}
    </div></div>`;
  $("#logout").onclick = logout;
  $("#pform").onsubmit = async (e) => {
    e.preventDefault();
    const v = readForm(e.target, profileFields);
    if (!v.password) delete v.password;
    try {
      state.user = { ...state.user, ...(await api("/api/me", { method: "PATCH", body: v })) };
      setLang(state.user.lang); shellRendered = false; toast(T("saved")); render();
    } catch (err) { fail(err); }
  };
  $("#groupSel")?.addEventListener("change", async (e) => {
    try {
      await api("/api/me/group", { method: "POST", body: { group_id: Number(e.target.value) } });
      state.user = null; state.users = []; state.vendors = []; state.assetFilter = null; localStorage.removeItem("tm_asset");
      shellRendered = false; render();
    } catch (err) { fail(err); }
  });
  $("#newGroup")?.addEventListener("click", () => openForm({
    title: T("new_family"),
    fields: [{ name: "name", label: T("group_name"), required: true, placeholder: T("group_name_hint") },
      ...(signup.signup_needs_code ? [{ name: "code", label: T("signup_code"), required: true }] : [])],
    intro: `<p class="small muted">${esc(T("new_family_help"))}</p>`,
    submitLabel: T("create_family"),
    onSubmit: async (v) => {
      await api("/api/groups", { method: "POST", body: v });
      state.user = null; state.users = []; state.vendors = []; state.assetFilter = null; localStorage.removeItem("tm_asset");
      shellRendered = false; toast(T("family_created", v.name)); location.hash = "#/assets"; render();
    },
  }));
  $("#renameGroup")?.addEventListener("click", () => openForm({
    title: T("rename"), fields: [{ name: "name", label: T("group_name"), required: true }], values: { name: u.group.name },
    onSubmit: async (v) => { await api("/api/group", { method: "PATCH", body: v }); state.user = null; shellRendered = false; toast(T("saved")); render(); },
  }));

  // ---- members
  // the Owner role can only be given by the owner (that is "hand over the group", below)
  const roleOptions = (current) => roles.filter((r) => !r.locked || r.id === current).map((r) => [r.id, r.name]);
  const defaultRole = roles.find((r) => r.key === "creator")?.id;
  const userFields = (isNew, x) => [
    { name: "name", label: T("name"), required: true },
    ...(isNew ? [{ name: "email", label: T("email"), type: "email", required: true }] : []),
    { name: "role_id", label: T("role"), type: "select", numeric: true, options: roleOptions(x?.role_id) },
    { name: "password", label: isNew ? T("password") : T("new_password"), type: "password", required: isNew, autocomplete: "new-password" },
    { name: "lang", label: T("language"), type: "select", options: LANG_OPTIONS },
  ];
  $("#addUser")?.addEventListener("click", () => openForm({
    title: T("add_user"), fields: userFields(true), values: { lang: state.lang, role_id: defaultRole },
    intro: `<p class="small muted">${esc(T("add_user_help"))}</p>`,
    onSubmit: async (v) => { await api("/api/users", { method: "POST", body: v }); state.users = []; toast(T("saved")); render(); },
  }));
  $("#invite")?.addEventListener("click", () => inviteDialog(roles, defaultRole));
  $$("[data-user]", main).forEach((b) => b.onclick = () => {
    const x = users.find((y) => y.id === Number(b.dataset.user));
    const isOwnerRow = x.role_key === "owner";
    const fields = userFields(false, x).filter((f) => !(isOwnerRow && f.name === "role_id"));
    const back = openForm({
      title: x.name, fields, values: x,
      outro: (x.id !== u.id ? `<div class="field"><button type="button" class="btn small" id="resetLink">${esc(T("reset_link_btn"))}</button>
        <p class="small muted" style="margin:6px 0 0">${esc(T("reset_link_help"))}</p></div>` : "")
        + (u.is_owner && x.id !== u.id ? `<div class="field"><button type="button" class="btn small" id="makeOwner">${esc(T("make_owner"))}</button>
        <p class="small muted" style="margin:6px 0 0">${esc(T("make_owner_help", x.name))}</p></div>` : ""),
      onSubmit: async (v) => { if (!v.password) delete v.password; await api(`/api/users/${x.id}`, { method: "PATCH", body: v }); state.users = []; toast(T("saved")); render(); },
      onDelete: x.id === u.id || isOwnerRow ? null : async () => { await api(`/api/users/${x.id}`, { method: "DELETE" }); state.users = []; render(); },
    });
    $("#resetLink", back)?.addEventListener("click", async () => {
      try {
        const r = await api(`/api/users/${x.id}/reset-link`, { method: "POST" });
        const m = modal({
          title: T("reset_link_btn"),
          html: `<p>${esc(T("reset_link_ready", x.name, r.hours))}</p>
            <label class="field"><span>${esc(T("reset_link_label"))}</span><input readonly value="${esc(r.link)}" id="rLink"></label>`,
          footer: `<button class="btn" data-close>${esc(T("close"))}</button><button class="btn primary" id="copyR">${esc(T("copy_link"))}</button>`,
        });
        $("#copyR", m).onclick = () => copyText(r.link);
        $("#rLink", m).onfocus = (e) => e.target.select();
      } catch (e) { fail(e); }
    });
    $("#makeOwner", back)?.addEventListener("click", async () => {
      if (!confirm(T("make_owner_help", x.name))) return;
      try { await api("/api/group/transfer-owner", { method: "POST", body: { user_id: x.id } }); closeModal(); state.user = null; shellRendered = false; toast(T("saved")); render(); }
      catch (e) { fail(e); }
    });
  });
  $$("[data-copy]", main).forEach((b) => b.onclick = () => copyText(b.dataset.copy));
  $$("[data-uninvite]", main).forEach((b) => b.onclick = async () => {
    if (!confirm(T("cancel_invite"))) return;
    try { await api(`/api/invitations/${b.dataset.uninvite}`, { method: "DELETE" }); render(); } catch (e) { fail(e); }
  });

  // ---- roles
  $("#addRole")?.addEventListener("click", () => roleDialog(null));
  $$("[data-role]", main).forEach((b) => b.onclick = () => roleDialog(roles.find((r) => r.id === Number(b.dataset.role))));

  $("#addVendor")?.addEventListener("click", () => vendorForm(null));
  $$("[data-vendor]", main).forEach((b) => b.onclick = () => vendorForm(vendors.find((v) => v.id === Number(b.dataset.vendor))));
  const out = $("#remout");
  $("#prev")?.addEventListener("click", async () => {
    try { const r = await api("/api/reminders/preview"); out.textContent = r.map((x) => `${x.user}\n  ${x.tasks.join("\n  ")}`).join("\n\n") || "–"; } catch (e) { fail(e); }
  });
  $("#send")?.addEventListener("click", async () => {
    try {
      const r = await api("/api/reminders/run", { method: "POST" });
      const sent = r.result.filter((x) => x.sent).length;
      out.textContent = r.result.length
        ? r.result.map((x) => `${x.sent ? "✓" : "✗"} ${x.user}${x.error ? `\n  ${x.error}` : ""}`).join("\n")
        : T("nothing_to_remind");
      toast(T("reminders_sent", sent, r.result.length), sent < r.result.length);
    } catch (e) { fail(e); }
  });
  $("#testmail")?.addEventListener("click", async () => {
    try {
      const r = await api("/api/reminders/test", { method: "POST" });
      out.textContent = r.ok ? `✓ ${T("test_ok")} ${r.to}` : `✗ ${r.error}`;
      toast(r.ok ? T("test_ok") : r.error, !r.ok);
    } catch (e) { fail(e); }
  });
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast(T("link_copied")); }
  catch { prompt(T("copy_link"), text); }  // http on a phone: no clipboard API, let them copy by hand
}

function inviteDialog(roles, defaultRole) {
  const fields = [
    { name: "email", label: T("email"), type: "email", required: true },
    { name: "role_id", label: T("role"), type: "select", numeric: true, options: roles.filter((r) => !r.locked).map((r) => [r.id, r.name]) },
    { name: "lang", label: T("invite_language"), type: "select", options: LANG_OPTIONS },
  ];
  openForm({
    title: T("invite"), fields, values: { role_id: defaultRole, lang: state.lang }, submitLabel: T("send_invite"),
    intro: `<p class="small muted">${esc(T("invite_help"))}</p>`,
    onSubmit: async (v) => {
      const inv = await api("/api/invitations", { method: "POST", body: v });
      setTimeout(() => {
        const back = modal({
          title: T("invite"),
          html: `<p>${esc(inv.mailed ? T("invite_mailed", inv.email) : T("invite_not_mailed"))}</p>
            ${inv.mail_error && !inv.mailed ? `<p class="small muted">${esc(inv.mail_error)}</p>` : ""}
            <label class="field"><span>${esc(T("invite_link"))}</span><input readonly value="${esc(inv.link)}" id="invLink"></label>`,
          footer: `<button class="btn" data-close>${esc(T("close"))}</button><button class="btn primary" id="copyInv">${esc(T("copy_link"))}</button>`,
        });
        $("#copyInv", back).onclick = () => copyText(inv.link);
        $("#invLink", back).onfocus = (e) => e.target.select();
        back.addEventListener("click", (e) => { if (e.target.closest("[data-close]") || e.target === back) render(); });
      }, 50);
    },
  });
}

// Role editor: a name and one tick per permission. Owner is shown but locked.
async function roleDialog(role) {
  let catalog;
  try { catalog = await api("/api/permissions"); } catch (e) { return fail(e); }
  const editable = can("roles.manage") && !role?.locked;
  const have = new Set(role?.locked ? catalog.map((p) => p.key) : role?.permissions || []);
  // group the ticks by what they are about: assets.*, tasks.* ...
  const AREAS = [["assets", "components"], ["tasks", "history", "counters"], ["parts", "warranties", "vendors", "attachments", "templates"], ["members", "roles"]];
  const area = (k) => AREAS.findIndex((a) => a.includes(k.split(".")[0]));
  const ticks = AREAS.map((_, i) => `<div class="perm-group">${catalog.filter((p) => area(p.key) === i).map((p) =>
    `<label class="check"><input type="checkbox" name="perm" value="${esc(p.key)}" ${have.has(p.key) ? "checked" : ""} ${editable ? "" : "disabled"}><span>${esc(p.label)}</span></label>`).join("")}</div>`).join("");
  const back = modal({
    title: role ? role.name : T("new_role"),
    html: `<form id="roleForm" novalidate>
      ${fieldHtml({ name: "name", label: T("role_name"), required: true }, role?.name || "")}
      ${role?.locked ? `<p class="small muted">${esc(T("owner_locked"))}</p>` : ""}
      ${!role || role.key ? "" : `<p class="small muted">${esc(T("n_members", role.members))}</p>`}
      <div class="field"><span class="form-sub">${esc(T("permissions"))}</span>
        <p class="small muted" style="margin:0 0 8px">${esc(T("permissions_help"))}</p>${ticks}</div></form>`,
    footer: editable
      ? `${role && !role.builtin ? `<button class="btn danger left" data-del type="button">${esc(T("delete"))}</button>` : ""}
         <button class="btn" data-close type="button">${esc(T("cancel"))}</button><button class="btn primary" data-ok type="button">${esc(T("save"))}</button>`
      : `<button class="btn" data-close type="button">${esc(T("close"))}</button>`,
  });
  const nameInput = $('[name="name"]', back);
  if (!editable) nameInput.disabled = true;
  $("[data-ok]", back)?.addEventListener("click", async () => {
    const body = { name: nameInput.value.trim(), permissions: $$('input[name="perm"]:checked', back).map((i) => i.value) };
    if (!body.name) { toast(`${T("role_name")}?`, true); nameInput.focus(); return; }
    try {
      await api(role ? `/api/roles/${role.id}` : "/api/roles", { method: role ? "PUT" : "POST", body });
      closeModal(); state.user = null; toast(T("saved")); render();
    } catch (e) { fail(e); }
  });
  $("[data-del]", back)?.addEventListener("click", async () => {
    if (!confirm(T("delete_role_confirm"))) return;
    try { await api(`/api/roles/${role.id}`, { method: "DELETE" }); closeModal(); toast(T("deleted")); render(); } catch (e) { fail(e); }
  });
}

// ---------------------------------------------------------------- start
setLang(state.lang);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
render();
