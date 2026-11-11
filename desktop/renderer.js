/* Fixed page renderer. The model supplies data, never code. No network or credentials. */
function graftMountV1(packet, options = {}) {
  if (location.origin !== packet.origin) return { ok: false, reason: "wrong_origin" };
  const base = new URL(packet.app_url).pathname.replace(/\/$/, "");
  if (base && !location.pathname.startsWith(base + "/") && location.pathname !== base) return { ok: false, reason: "wrong_app" };
  const old = window.__graftV1;
  if (old && old.clientId === options.clientId) { old.update(packet); return { ok: true }; }
  if (old) old.remove();
  const host = document.createElement("div");
  host.id = "graft-feature-root";
  const shadow = host.attachShadow({ mode: "open" });
  const css = document.createElement("style");
  css.textContent = `
    :host{all:initial;position:fixed;inset:20px 20px 20px auto;width:min(1040px,82vw);z-index:2147483000;color:#ecf0ec;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color-scheme:dark}
    *{box-sizing:border-box}button,input,select{font:inherit}button{cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid #c1f588;outline-offset:3px}
    .shell{height:100%;display:flex;flex-direction:column;background:#151c19;border:1px solid #3b4a3f;border-radius:18px;box-shadow:0 24px 100px #0007;overflow:hidden}
    .bar{display:flex;align-items:center;justify-content:space-between;padding:15px 24px;border-bottom:1px solid #344137;background:#19231d;gap:12px}.brand{display:flex;gap:10px;align-items:center;font-size:18px;font-weight:700;letter-spacing:-.6px}.mark{color:#b8ee82;font-size:24px}.sub{color:#a2b0a5;font-size:11px;letter-spacing:1.6px;text-transform:uppercase}.live{display:flex;align-items:center;gap:7px;color:#c2d4c4;font-size:11px;letter-spacing:.8px}.dot{height:6px;width:6px;background:#b8ee82;border-radius:50%}
    .plain{background:transparent;border:1px solid #425346;color:#d1dbd2;padding:5px 11px;border-radius:7px}.plain:hover{background:#2d3c31}.top-actions{display:flex;align-items:center;gap:9px}.scroll{overflow:auto;padding:28px;flex:1}.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:1.7px;color:#b8ee82;margin:0 0 7px}h1{font-size:32px;line-height:1.12;font-weight:550;letter-spacing:-1.2px;margin:0 0 10px}p{margin:0;color:#b4c1b7}.intro{margin-bottom:25px}.tools{display:flex;align-items:center;justify-content:space-between;margin:18px 0;gap:10px}.search{width:min(100%,320px);background:#1b2720;border:1px solid #405145;border-radius:8px;padding:9px 12px;color:#e8eee9}.count{color:#91a394;font-size:12px}.widget{margin:0 0 20px;background:#1c2820;border:1px solid #34473a;border-radius:12px;overflow:hidden}.widget h2{font-size:13px;letter-spacing:.2px;font-weight:600;margin:0;padding:15px 18px;border-bottom:1px solid #34473a}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:1px;background:#34473a}.card{background:#1c2820;padding:20px}.number{font-size:35px;line-height:1.2;letter-spacing:-1px;color:#d5f5b8;font-weight:500}.label{color:#a7b7ab;font-size:12px;margin-top:7px}.chart{padding:18px;display:grid;gap:12px}.bar-row{display:grid;grid-template-columns:130px 1fr 48px;align-items:center;gap:10px;font-size:12px}.track{background:#2d3d31;height:10px;border-radius:3px;overflow:hidden}.fill{background:#b3e584;height:100%;border-radius:3px}.value{text-align:right;color:#d9e8d9;font-variant-numeric:tabular-nums}
    .table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;text-align:left}th{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#9caf9f;padding:12px 15px;font-weight:500;background:#202e25}td{border-top:1px solid #314235;padding:12px 15px;font-size:12px;vertical-align:middle}td:first-child{color:#f0f4f0;min-width:190px}tr:hover td{background:#233429}.group td{padding:9px 15px;background:#25382b;color:#b8dcad;font-size:10px;text-transform:uppercase;letter-spacing:1px}.late{color:#ffb59b}.pill{display:inline-block;border:1px solid #4a6150;border-radius:4px;padding:1px 6px;font-size:10px;color:#bdd3c0;white-space:nowrap}.empty{padding:30px;text-align:center;color:#a3b6a6}.edit td{background:#26382c;padding:16px}.edit-controls{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.edit-controls select,.edit-controls input{background:#16241b;border:1px solid #58715d;border-radius:6px;color:#edf3ed;padding:7px 9px}.go{background:#c1f588;color:#172718;border:0;border-radius:6px;padding:8px 12px;font-size:12px;font-weight:600}.note{font-size:11px;color:#abbfaf;margin-top:9px}.footer{padding:11px 24px;border-top:1px solid #344137;display:flex;justify-content:space-between;color:#91a194;font-size:10px;gap:10px}.toast{position:absolute;bottom:48px;left:28px;right:28px;background:#d5f3ba;color:#21351d;border-radius:9px;padding:12px 15px;font-size:12px;box-shadow:0 8px 25px #0004}.mini{width:128px!important;inset:auto 20px 20px auto!important;height:48px}.mini .shell{border-radius:12px}.mini .bar{padding:10px 15px}.mini .scroll,.mini .footer,.mini .live,.mini .sub,.mini .minimize{display:none}.mini .brand{font-size:16px}.mini .top-actions{display:none}
    @media(max-width:700px){:host{width:calc(100vw - 20px);inset:10px}.scroll{padding:18px}.bar{padding:12px 18px}h1{font-size:27px}.sub{display:none}.bar-row{grid-template-columns:95px 1fr 35px}th,td{padding:10px}}
  `;
  shadow.append(css);
  const el = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = String(value);
    return node;
  };
  const button = (label, fn, className = "plain") => { const b = el("button", className, label); b.type = "button"; b.addEventListener("click", fn); return b; };
  const shell = el("section", "shell");
  shell.setAttribute("aria-label", "Graft personal feature");
  const bar = el("header", "bar");
  const brand = el("div", "brand"); brand.append(el("span", "mark", "↗"), el("span", "", "graft"), el("span", "sub", "your app, extended"));
  const actions = el("div", "top-actions");
  const live = el("span", "live"); live.append(el("i", "dot"), el("span", "", options.preview ? "SAMPLE DATA" : "CONNECTED"));
  actions.append(live, button("−", () => host.classList.add("mini"), "plain minimize"), button("×", () => api.remove()));
  bar.append(brand, actions); bar.addEventListener("click", () => { if (host.classList.contains("mini")) host.classList.remove("mini"); });
  const content = el("main", "scroll");
  const footer = el("footer", "footer");
  shell.append(bar, content, footer); shadow.append(shell); document.documentElement.append(host);
  let current = packet, signature = "", searchValue = "", lease = Date.now() + 16000, toastTimer;
  const queue = [];
  function propose(row, action, value) {
    if (queue.length >= 20) return;
    queue.push({ clientId: options.clientId, feature_id: current.id, task_id: row.id, action, value });
    notify("Review this change in the Graft pane in Hermes. Nothing has been changed yet.");
  }
  function notify(message) {
    shadow.querySelector(".toast")?.remove();
    const toast = el("div", "toast", message); toast.setAttribute("role", "status"); shell.append(toast);
    clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.remove(), 6500);
  }
  function showEditor(tr, row, widget) {
    const next = tr.nextElementSibling;
    if (next?.classList.contains("edit")) { next.remove(); return; }
    const edit = el("tr", "edit"), cell = el("td"); cell.colSpan = widget.columns.length + 1;
    const controls = el("div", "edit-controls");
    if (widget.actions.includes("reassign")) {
      const select = el("select"); select.setAttribute("aria-label", "New owner for " + row.title);
      const owners = { "0": "Unassigned", ...(current.assignable[String(row.project_id)] || {}) };
      for (const [id, name] of Object.entries(owners)) { const opt = el("option", "", name); opt.value = id; select.append(opt); }
      select.value = String(row.owner_id);
      controls.append(select, button("Review owner change", () => propose(row, "reassign", Number(select.value)), "go"));
    }
    if (widget.actions.includes("set_due")) {
      const input = el("input"); input.type = "date"; input.value = row.due || ""; input.setAttribute("aria-label", "New due date for " + row.title);
      controls.append(input, button("Review date change", () => { if (input.value) propose(row, "set_due", input.value); }, "go"));
    }
    cell.append(controls, el("div", "note", "Changes wait for your confirmation in Hermes.")); edit.append(cell); tr.after(edit);
  }
  const titles = { id: "ID", title: "Task", project: "Project", owner: "Owner", due: "Due", effort: "Hours", priority: "Priority", status: "Status", column: "Stage", due_in_days: "Days to due", owner_id: "Owner ID", project_id: "Project ID", column_id: "Stage ID", is_overdue: "Overdue" };
  function table(widget, target) {
    const rows = widget.rows.filter(row => !searchValue || [row.title, row.project, row.owner].some(v => String(v).toLowerCase().includes(searchValue.toLowerCase())));
    if (!rows.length) { target.append(el("div", "empty", "No tasks match this view.")); return; }
    const wrap = el("div", "table-wrap"), tbl = el("table"), head = el("thead"), header = el("tr");
    widget.columns.forEach(c => header.append(el("th", "", titles[c] || c)));
    if (widget.actions.length) header.append(el("th", "", ""));
    head.append(header); tbl.append(head); const body = el("tbody");
    const groups = new Map();
    rows.forEach(row => { const k = widget.group_by ? String(row[widget.group_by] ?? "Unassigned") : ""; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(row); });
    for (const [name, items] of groups) {
      if (widget.group_by) { const group = el("tr", "group"), td = el("td", "", name + " · " + items.length); td.colSpan = widget.columns.length + (widget.actions.length ? 1 : 0); group.append(td); body.append(group); }
      for (const row of items) {
        const tr = el("tr"); tr.dataset.taskId = row.id;
        widget.columns.forEach(c => {
          const v = row[c]; const td = el("td", c === "due" && row.is_overdue ? "late" : "", v == null ? "—" : typeof v === "boolean" ? (v ? "Yes" : "No") : v);
          if (c === "title") td.title = row.title;
          tr.append(td);
        });
        if (widget.actions.length) { const td = el("td"); td.append(button("Edit", () => showEditor(tr, row, widget))); tr.append(td); }
        body.append(tr);
      }
    }
    tbl.append(body); wrap.append(tbl); target.append(wrap);
    if (widget.total > widget.rows.length) target.append(el("div", "note", "Showing " + widget.rows.length + " of " + widget.total + " tasks. Ask Hermes to narrow the view."));
  }
  function draw() {
    content.replaceChildren();
    const intro = el("div", "intro"); intro.append(el("div", "eyebrow", "A feature you asked for"), el("h1", "", current.view.title), el("p", "", current.view.description)); content.append(intro);
    if (current.view.widgets.some(w => w.type === "table")) {
      const tools = el("div", "tools"), search = el("input", "search"); search.type = "search"; search.placeholder = "Search task titles, projects, owners"; search.setAttribute("aria-label", "Search displayed tasks"); search.value = searchValue;
      search.addEventListener("input", () => { searchValue = search.value; for (const w of current.view.widgets.filter(w => w.type === "table")) { const target = shadow.querySelector('[data-widget="' + w.id + '"] .table-target'); target.replaceChildren(); table(w, target); } });
      tools.append(search, el("span", "count", current.view.matched + " open tasks in scope")); content.append(tools);
    }
    for (const w of current.view.widgets) {
      const box = el("section", "widget"); box.dataset.widget = w.id; box.append(el("h2", "", w.title));
      if (w.type === "metrics") {
        const cards = el("div", "cards"); w.cards.forEach(c => { const card = el("div", "card"); card.append(el("div", "number", c.value == null ? "—" : c.value), el("div", "label", c.label)); cards.append(card); }); box.append(cards);
      } else if (w.type === "bar_chart") {
        const chart = el("div", "chart"), max = Math.max(1, ...w.series.map(s => s.value));
        w.series.forEach(s => { const row = el("div", "bar-row"), track = el("div", "track"), fill = el("div", "fill"); fill.style.width = Math.max(0, s.value / max * 100) + "%"; track.append(fill); row.append(el("span", "", s.label), track, el("span", "value", s.value + (w.measure === "effort" ? "h" : ""))); chart.append(row); });
        if (!w.series.length) chart.append(el("div", "empty", "No matching work.")); box.append(chart);
      } else { const target = el("div", "table-target"); box.append(target); table(w, target); }
      content.append(box);
    }
    footer.replaceChildren(el("span", "", "PERSONAL EXTENSION · " + (options.preview ? "RENDERER PREVIEW" : "KANBOARD")), el("span", "", "Saved feature · revision " + current.revision));
  }
  const api = {
    clientId: options.clientId,
    update(next) {
      lease = Date.now() + 16000;
      if (next) {
        const sig = JSON.stringify([next.id, next.revision, next.view.widgets, next.assignable]);
        current = next;
        if (sig !== signature) { signature = sig; draw(); }
      }
    },
    drain() { lease = Date.now() + 16000; return queue.splice(0, 20); },
    remove() { clearInterval(watch); clearTimeout(toastTimer); host.remove(); if (window.__graftV1 === api) delete window.__graftV1; },
    notify,
  };
  const watch = setInterval(() => { if (Date.now() > lease || !host.isConnected) api.remove(); }, 1000);
  window.__graftV1 = api;
  api.update(packet);
  return { ok: true };
}
