"""Graft's declarative feature engine and Kanboard connector. Standard library only."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

FIELDS = {
    "id": "number", "title": "text", "project": "text", "project_id": "number",
    "owner": "text", "owner_id": "number", "status": "text", "column": "text",
    "column_id": "number", "priority": "number", "effort": "number",
    "due": "date", "due_in_days": "number", "is_overdue": "boolean",
}
OPS = {"eq", "ne", "contains", "gt", "gte", "lt", "lte", "in", "empty", "not_empty"}
GROUPS = {"owner", "project", "column", "priority", "status"}
ACTIONS = {"reassign", "set_due"}
LIMIT = 5000


class GraftError(ValueError):
    pass


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def text(value, label, maximum=160):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise GraftError(f"{label} must be text between 1 and {maximum} characters.")
    return value.strip()


def keys(obj, allowed, label):
    if not isinstance(obj, dict):
        raise GraftError(f"{label} must be an object.")
    extra = set(obj) - set(allowed)
    if extra:
        raise GraftError(f"Unsupported {label} fields: {', '.join(sorted(extra))}.")


def field(name):
    if not isinstance(name, str) or name not in FIELDS:
        raise GraftError(f"Unknown field: {name!r}. Ask graft_capabilities for supported fields.")
    return name


def filters(value):
    if not isinstance(value, list) or len(value) > 12:
        raise GraftError("Use at most 12 filters.")
    result = []
    for item in value:
        keys(item, {"field", "op", "value"}, "filter")
        name, op = field(item.get("field")), item.get("op")
        if not isinstance(op, str) or op not in OPS:
            raise GraftError(f"Unknown filter operation: {op!r}.")
        val = item.get("value")
        if op == "in":
            if not isinstance(val, list) or len(val) > 50 or any(isinstance(v, (dict, list)) for v in val):
                raise GraftError("An 'in' filter needs at most 50 simple values.")
        elif isinstance(val, (dict, list)):
            raise GraftError("A filter needs a simple value.")
        if op in {"gt", "gte", "lt", "lte"} and FIELDS[name] == "number":
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise GraftError("Numerical comparisons need a finite number.")
        if op == "contains" and not isinstance(val, str):
            raise GraftError("A contains filter needs text.")
        result.append({"field": name, "op": op, "value": val})
    return result


def validate_spec(spec):
    try:
        encoded = json.dumps(spec, allow_nan=False)
    except (TypeError, ValueError):
        raise GraftError("Feature must contain ordinary, finite JSON values.") from None
    if len(encoded) > 30000:
        raise GraftError("Feature is too large.")
    keys(spec, {"version", "title", "description", "query", "widgets"}, "feature")
    if type(spec.get("version")) is not int or spec["version"] != 1:
        raise GraftError("Feature version must be 1.")
    result = {"version": 1, "title": text(spec.get("title"), "Title", 80),
              "description": text(spec.get("description", "A feature created with Graft."), "Description", 300)}
    query = spec.get("query", {})
    keys(query, {"filters", "sort", "limit"}, "query")
    order = query.get("sort", [{"field": "due", "direction": "asc"}])
    if not isinstance(order, list) or len(order) > 3:
        raise GraftError("Use at most three sort fields.")
    sorting = []
    for item in order:
        keys(item, {"field", "direction"}, "sort")
        direction = item.get("direction", "asc")
        if not isinstance(direction, str) or direction not in {"asc", "desc"}:
            raise GraftError("Sort direction must be asc or desc.")
        sorting.append({"field": field(item.get("field")), "direction": direction})
    limit = query.get("limit", 200)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise GraftError("Query limit must be between 1 and 1000.")
    result["query"] = {"filters": filters(query.get("filters", [])), "sort": sorting, "limit": limit}
    widgets = spec.get("widgets")
    if not isinstance(widgets, list) or not 1 <= len(widgets) <= 8:
        raise GraftError("A feature needs between one and eight widgets.")
    clean, ids = [], set()
    for widget in widgets:
        keys(widget, {"id", "type", "title", "columns", "group_by", "measure", "metrics", "actions", "filters"}, "widget")
        ident = text(widget.get("id"), "Widget ID", 40)
        if not all(c.isalnum() or c in "_-" for c in ident) or ident in ids:
            raise GraftError("Widget IDs must be unique letters, numbers, underscores or hyphens.")
        ids.add(ident)
        kind = widget.get("type")
        if not isinstance(kind, str) or kind not in {"table", "bar_chart", "metrics"}:
            raise GraftError("Supported widgets are table, bar_chart and metrics.")
        allowed_for_kind = {"id", "type", "title", "filters"} | {
            "table": {"columns", "group_by", "actions"},
            "bar_chart": {"group_by", "measure"}, "metrics": {"metrics"},
        }[kind]
        if set(widget) - allowed_for_kind:
            raise GraftError(f"Unsupported options for {kind}: {', '.join(sorted(set(widget) - allowed_for_kind))}.")
        out = {"id": ident, "type": kind, "title": text(widget.get("title", result["title"]), "Widget title", 80),
               "filters": filters(widget.get("filters", []))}
        if kind == "table":
            columns = widget.get("columns", ["title", "project", "owner", "due"])
            if not isinstance(columns, list) or not 1 <= len(columns) <= 8 or not all(isinstance(c, str) for c in columns) or len(set(columns)) != len(columns):
                raise GraftError("Tables need one to eight different columns.")
            out["columns"] = [field(c) for c in columns]
            group = widget.get("group_by")
            if group is not None and (not isinstance(group, str) or group not in GROUPS):
                raise GraftError("Unsupported table grouping.")
            out["group_by"] = group
            actions = widget.get("actions", [])
            if not isinstance(actions, list) or any(not isinstance(a, str) or a not in ACTIONS for a in actions):
                raise GraftError("Supported actions are reassign and set_due.")
            out["actions"] = list(dict.fromkeys(actions))
        elif kind == "bar_chart":
            group = widget.get("group_by")
            if not isinstance(group, str) or group not in GROUPS:
                raise GraftError("Bar charts need a supported grouping field.")
            measure = widget.get("measure", "count")
            if not isinstance(measure, str) or measure not in {"count", "effort"}:
                raise GraftError("Chart measure must be count or effort.")
            out.update(group_by=group, measure=measure)
        else:
            metrics = widget.get("metrics")
            if not isinstance(metrics, list) or not 1 <= len(metrics) <= 4:
                raise GraftError("Use one to four metric cards.")
            out["metrics"] = []
            for metric in metrics:
                keys(metric, {"label", "op", "field", "filters"}, "metric")
                op = metric.get("op", "count")
                if not isinstance(op, str) or op not in {"count", "sum", "avg"}:
                    raise GraftError("Metric operation must be count, sum or avg.")
                name = metric.get("field", "effort")
                if not isinstance(name, str) or name not in FIELDS or (op != "count" and FIELDS[name] != "number"):
                    raise GraftError("Sum and average need a numerical field.")
                out["metrics"].append({"label": text(metric.get("label"), "Metric label", 40), "op": op,
                                       "field": name, "filters": filters(metric.get("filters", []))})
        clean.append(out)
    result["widgets"] = clean
    if len(json.dumps(result)) > 30000:
        raise GraftError("Feature is too large.")
    return result


def matches(row, conditions):
    for condition in conditions:
        a, b, op = row.get(condition["field"]), condition.get("value"), condition["op"]
        try:
            ok = {
                "eq": lambda: a == b, "ne": lambda: a != b,
                "contains": lambda: isinstance(a, str) and b.casefold() in a.casefold(),
                "gt": lambda: a is not None and a > b, "gte": lambda: a is not None and a >= b,
                "lt": lambda: a is not None and a < b, "lte": lambda: a is not None and a <= b,
                "in": lambda: a in b, "empty": lambda: a is None or a == "",
                "not_empty": lambda: a is not None and a != "",
            }[op]()
        except (TypeError, ValueError):
            ok = False
        if not ok:
            return False
    return True


def evaluate(spec, rows):
    spec = validate_spec(spec)
    selected = [r for r in rows if matches(r, spec["query"]["filters"])]
    total = len(selected)
    for order in reversed(spec["query"]["sort"]):
        name = order["field"]
        present = [r for r in selected if r.get(name) is not None]
        missing = [r for r in selected if r.get(name) is None]
        selected = sorted(present, key=lambda r: r[name], reverse=order["direction"] == "desc") + missing
    # Metrics and charts use every matched record, not just the displayed table page.
    widgets = []
    for widget in spec["widgets"]:
        data = [r for r in selected if matches(r, widget["filters"])]
        out = dict(widget)
        if widget["type"] == "table":
            out.update(rows=data[:spec["query"]["limit"]], total=len(data))
        elif widget["type"] == "bar_chart":
            groups = {}
            for row in data:
                label = str(row.get(widget["group_by"]) or "Unassigned")
                groups[label] = groups.get(label, 0) + (1 if widget["measure"] == "count" else row["effort"])
            out["series"] = [{"label": k, "value": round(v, 2)} for k, v in sorted(groups.items(), key=lambda i: (-i[1], i[0]))]
        else:
            cards = []
            for metric in widget["metrics"]:
                subset = [r for r in data if matches(r, metric["filters"])]
                values = [r[metric["field"]] for r in subset if isinstance(r.get(metric["field"]), (int, float))]
                val = len(subset) if metric["op"] == "count" else sum(values)
                if metric["op"] == "avg":
                    val = val / len(values) if values else None
                cards.append({"label": metric["label"], "value": round(val, 2) if val is not None else None})
            out["cards"] = cards
        widgets.append(out)
    return {"title": spec["title"], "description": spec["description"], "matched": total,
            "source_count": len(rows), "widgets": widgets, "generated_at": time.time()}


def normalize_task(task, project, users, columns, now=None, tz="UTC"):
    zone = ZoneInfo(tz)
    now = (now or datetime.now(timezone.utc)).astimezone(zone)
    due_stamp = int(task.get("date_due") or 0)
    due = datetime.fromtimestamp(due_stamp, zone) if due_stamp else None
    owner_id = int(task.get("owner_id") or 0)
    due_days = (due.date() - now.date()).days if due else None
    return {"id": int(task["id"]), "title": str(task["title"]), "project_id": int(task["project_id"]),
            "project": project, "owner_id": owner_id, "owner": users.get(str(owner_id), "Unassigned" if not owner_id else f"User {owner_id}"),
            "status": "open" if str(task.get("is_active", "1")) == "1" else "closed",
            "column_id": int(task.get("column_id") or 0), "column": columns.get(str(task.get("column_id")), "Unknown"),
            "priority": int(task.get("priority") or 0), "effort": float(task.get("time_estimated") or 0),
            "due": due.strftime("%Y-%m-%d") if due else None, "due_in_days": due_days,
            "is_overdue": due_days is not None and due_days < 0 and str(task.get("is_active", "1")) == "1"}


class Kanboard:
    def __init__(self, url, username, token, timeout=12):
        parsed = urllib.parse.urlsplit(url.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise GraftError("Kanboard address must be an http(s) address without credentials or query parameters.")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise GraftError("Use HTTPS for a remote app, or connect through a localhost SSH tunnel.")
        self.url = url.rstrip("/")
        self.origin = f"{parsed.scheme}://{parsed.netloc}"
        self.username, self.token, self.timeout = username, token, timeout

    def call(self, method, **params):
        if not self.token:
            raise GraftError("Add your Kanboard personal API token in Hermes → Settings → Plugins → Graft.")
        body = json.dumps({"jsonrpc": "2.0", "id": secrets.randbelow(100000000), "method": method, "params": params}).encode()
        auth = base64.b64encode(f"{self.username}:{self.token}".encode()).decode()
        req = urllib.request.Request(self.url + "/jsonrpc.php", data=body,
                                     headers={"Content-Type": "application/json", "Authorization": "Basic " + auth})
        # Redirects must never carry a personal API token to another endpoint.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(req, timeout=self.timeout) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise GraftError("Kanboard returned too much data. Narrow the connector scope.")
            result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise GraftError("Kanboard refused access. Check the username, personal token and project permissions.") from None
            raise GraftError(f"Kanboard HTTP error {exc.code}.") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            raise GraftError("Cannot reach Kanboard. Check that the app and SSH tunnel are running.") from None
        if result.get("error"):
            raise GraftError(f"Kanboard could not perform {method}. Check that your account has permission.")
        return result.get("result")

    def dataset(self):
        tz = self.call("getTimezone") or "UTC"
        projects = self.call("getAllProjects") or []
        rows, assignable = [], {}
        for project in projects[:30]:
            pid = int(project["id"])
            users = self.call("getAssignableUsers", project_id=pid) or {}
            if isinstance(users, list):
                users = {str(u["id"]): u.get("name") or u.get("username") for u in users}
            users = {str(k): str(v) for k, v in users.items()}
            assignable[str(pid)] = users
            columns = {str(c["id"]): c["title"] for c in (self.call("getColumns", project_id=pid) or [])}
            tasks = self.call("getAllTasks", project_id=pid, status_id=1) or []
            rows.extend(normalize_task(t, project["name"], users, columns, tz=tz) for t in tasks)
            if len(rows) > LIMIT:
                raise GraftError("More than 5,000 tasks found. This prototype supports smaller workspaces.")
        if len(projects) > 30:
            raise GraftError("More than 30 projects found. This prototype needs a smaller account scope.")
        return {"rows": rows, "assignable": assignable, "origin": self.origin, "url": self.url,
                "projects": [{"id": int(p["id"]), "name": p["name"]} for p in projects]}

    def task(self, task_id):
        result = self.call("getTask", task_id=int(task_id))
        if not result:
            raise GraftError("This task was removed or is no longer accessible.")
        return result

    def update(self, task_id, changes):
        if self.call("updateTask", id=int(task_id), **changes) is not True:
            raise GraftError("Kanboard did not accept this change.")


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS features(id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                origin TEXT NOT NULL, spec TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, feature_id TEXT NOT NULL,
                revision INTEGER NOT NULL, payload TEXT NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at REAL NOT NULL,
                feature_id TEXT, event TEXT NOT NULL, detail TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, spec, origin, feature_id=None):
        spec = validate_spec(spec)
        ident = feature_id or secrets.token_hex(8)
        now = time.time()
        with self.connect() as db:
            old = db.execute("SELECT * FROM features WHERE id=?", (ident,)).fetchone()
            if feature_id and not old:
                raise GraftError("Feature not found. Create a new feature instead.")
            if old and old["origin"] != origin:
                raise GraftError("A saved feature cannot be moved to a different website.")
            rev = (old["revision"] + 1) if old else 1
            db.execute("INSERT INTO features VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,spec=excluded.spec,updated=excluded.updated",
                       (ident, rev, origin, json.dumps(spec), old["created"] if old else now, now))
            db.execute("INSERT INTO audit(at,feature_id,event,detail) VALUES(?,?,?,?)", (now, ident, "published", json.dumps({"revision": rev})))
        return self.get(ident)

    def get(self, ident):
        with self.connect() as db:
            row = db.execute("SELECT * FROM features WHERE id=?", (ident,)).fetchone()
        if not row:
            raise GraftError("Feature not found.")
        out = dict(row)
        out["spec"] = json.loads(out["spec"])
        return out

    def list(self):
        with self.connect() as db:
            return [{"id": row["id"], "revision": row["revision"], "origin": row["origin"],
                     "title": json.loads(row["spec"])["title"], "updated": row["updated"]}
                    for row in db.execute("SELECT * FROM features ORDER BY updated DESC")]

    def prepare(self, adapter, feature_id, task_id, action, value):
        saved = self.get(feature_id)
        if adapter.origin != saved["origin"]:
            raise GraftError("Connector address changed. Recreate the feature for this app.")
        if not any(action in w.get("actions", []) for w in saved["spec"]["widgets"]):
            raise GraftError("This feature does not allow that action.")
        current = adapter.task(task_id)
        if action == "reassign":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise GraftError("Choose an available owner.")
            people = adapter.call("getAssignableUsers", project_id=int(current["project_id"])) or {}
            if value and str(value) not in {str(k) for k in people}:
                raise GraftError("That person cannot be assigned to this project.")
            changes, label = {"owner_id": value}, "Change owner"
            old_id = int(current.get("owner_id") or 0)
            before = "Unassigned" if not old_id else people.get(str(old_id), people.get(old_id, f"User {old_id}"))
            after = "Unassigned" if not value else people.get(str(value), people.get(value))
            expected_value = value
        elif action == "set_due":
            try:
                parsed = datetime.strptime(value, "%Y-%m-%d")
            except (ValueError, TypeError):
                raise GraftError("Choose a date in YYYY-MM-DD format.") from None
            if parsed.strftime("%Y-%m-%d") != value:
                raise GraftError("Choose a valid date.")
            zone_name = adapter.call("getTimezone") or "UTC"
            zone = ZoneInfo(zone_name)
            changes, label = {"date_due": value + " 17:00"}, "Change due date"
            before = datetime.fromtimestamp(int(current["date_due"]), zone).strftime("%Y-%m-%d %H:%M") if int(current.get("date_due") or 0) else "No due date"
            after = value + " at 17:00 " + zone_name
            expected_value = int(parsed.replace(hour=17, tzinfo=zone).timestamp())
        else:
            raise GraftError("Unsupported action.")
        token = secrets.token_urlsafe(24)
        payload = {"task_id": int(task_id), "title": current["title"], "action": action, "label": label,
                   "before": before, "after": after, "changes": changes, "expected_value": expected_value,
                   "expected": fingerprint(current), "origin": adapter.origin, "username": adapter.username}
        with self.connect() as db:
            db.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?)", (token, feature_id, saved["revision"], json.dumps(payload), time.time() + 300, "pending"))
        return {"id": token, **payload, "expires_in": 300}

    def apply(self, adapter, review_id):
        # Consume before the network request. An ambiguous timeout is never automatically retried.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
            if not row or row["state"] != "pending" or row["expires"] < time.time():
                raise GraftError("This review expired or was already used. Prepare a fresh change.")
            saved = db.execute("SELECT * FROM features WHERE id=?", (row["feature_id"],)).fetchone()
            if not saved or saved["revision"] != row["revision"]:
                raise GraftError("This feature changed since review. Prepare a fresh change.")
            payload = json.loads(row["payload"])
            if adapter.origin != payload["origin"] or adapter.username != payload["username"]:
                raise GraftError("The connector changed. Prepare a fresh change.")
            current = adapter.task(payload["task_id"])
            if fingerprint(current) != payload["expected"]:
                raise GraftError("This task changed since review. Refresh and review the current version.")
            db.execute("UPDATE reviews SET state='applying' WHERE id=?", (review_id,))
        try:
            adapter.update(payload["task_id"], payload["changes"])
            confirmed = adapter.task(payload["task_id"])
            for name, value in payload["changes"].items():
                expected = payload["expected_value"]
                if str(confirmed.get(name)) != str(expected):
                    raise GraftError("The app did not confirm the expected value. Refresh before doing anything else.")
            status = "applied"
        except Exception:
            with self.connect() as db:
                db.execute("UPDATE reviews SET state='needs_check' WHERE id=?", (review_id,))
            raise GraftError("The change could not be confirmed. Check the task in Kanboard before trying again.") from None
        with self.connect() as db:
            db.execute("UPDATE reviews SET state=? WHERE id=?", (status, review_id))
            db.execute("INSERT INTO audit(at,feature_id,event,detail) VALUES(?,?,?,?)", (time.time(), row["feature_id"], "applied", json.dumps(payload)))
        return {"ok": True, "task_id": payload["task_id"], "message": "Change confirmed in Kanboard."}


def capabilities():
    return {"app": "kanboard", "version": 1, "fields": FIELDS,
            "filter_operations": sorted(OPS), "group_fields": sorted(GROUPS),
            "widgets": {"table": {"columns": "1–8 supported fields", "group_by": sorted(GROUPS), "actions": sorted(ACTIONS)},
                        "bar_chart": {"group_by": sorted(GROUPS), "measure": ["count", "effort"]},
                        "metrics": {"metrics": "1–4 {label, op: count|sum|avg, field?, filters?}"}},
            "spec_format": {"version": 1, "title": "Feature name", "description": "Purpose", "query": {"filters": [], "sort": [], "limit": 200}, "widgets": []},
            "rules": ["Never invent fields, widgets, operations or actions.", "Generate a feature blueprint, never executable code.",
                      "Use graft_publish to create or revise features. It does not modify app records.",
                      "Only the user can apply record changes through the Graft review panel.",
                      "The dataset contains open tasks only. Never claim to include closed tasks."]}
