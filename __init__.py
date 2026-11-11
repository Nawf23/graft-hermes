"""Graft: generate persistent in-app features from a validated blueprint."""
import json
from pathlib import Path
from . import runtime
core = runtime.core


def register(ctx):
    def guarded(fn):
        def handler(args, **kwargs):
            try:
                return json.dumps(fn(args), ensure_ascii=False)
            except core.GraftError as exc:
                return json.dumps({"error": str(exc)})
            except Exception:
                return json.dumps({"error": "Graft could not finish this request. Check the connector in Graft settings."})
        return handler

    def describe(args):
        return core.capabilities()

    def dataset(args):
        _, adapter = runtime.context()
        data = adapter.dataset()
        limit = min(50, max(1, int(args.get("sample_size", 12))))
        return {"projects": data["projects"], "total_open_tasks": len(data["rows"]), "sample": data["rows"][:limit],
                "available_owners": data["assignable"], "scope": "Open tasks accessible to the configured Kanboard account."}

    def publish(args):
        store, adapter = runtime.context()
        saved = store.save(args["spec"], adapter.origin, args.get("feature_id"))
        runtime.event("feature.updated", {"id": saved["id"], "revision": saved["revision"]})
        return {"ok": True, "feature_id": saved["id"], "revision": saved["revision"], "title": saved["spec"]["title"],
                "next": "The user can select this feature and click Attach to app in the Graft pane. No app records were changed."}

    def listing(args):
        store, _ = runtime.context()
        return {"features": store.list(), "selected": store.get(args["feature_id"]) if args.get("feature_id") else None}

    tools = [
        ("graft_capabilities", "Read Graft's supported fields, widgets, filter operations and blueprint format before creating an in-app feature.", {}, [], describe),
        ("graft_data", "Read a bounded sample of real open Kanboard tasks and project/owner identifiers to ground a Graft feature. This sends selected task text to the conversation's model.",
         {"sample_size": {"type": "integer", "minimum": 1, "maximum": 50}}, [], dataset),
        ("graft_publish", "Create or revise a persistent Graft feature from a declarative blueprint. Never send executable code. This changes Graft's interface only, not application records. Use graft_capabilities and the graft-builder skill first.",
         {"spec": {"type": "object", "description": "Version-1 Graft blueprint: version, title, description, query, widgets. Ask graft_capabilities for fields."},
          "feature_id": {"type": "string", "description": "Existing feature ID when revising; omit to create."}}, ["spec"], publish),
        ("graft_list", "List saved Graft features; optionally retrieve one blueprint so you can revise it without rebuilding unrelated parts.",
         {"feature_id": {"type": "string"}}, [], listing),
    ]
    for name, description, properties, required, handler in tools:
        schema = {"name": name, "description": description,
                  "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}
        ctx.register_tool(name=name, toolset="graft", schema=schema, handler=guarded(handler))
    ctx.register_skill("graft-builder", Path(__file__).parent / "skills" / "graft-builder" / "SKILL.md")
