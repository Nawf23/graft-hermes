"""Authenticated, profile-scoped routes mounted by Hermes under /api/plugins/graft."""
import importlib.util
from pathlib import Path
from fastapi import APIRouter, HTTPException

_root = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("graft_own_runtime", _root / "runtime.py")
runtime = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runtime)
core = runtime.core
router = APIRouter()


def checked(fn):
    try:
        return fn()
    except core.GraftError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/status")
def status():
    def run():
        store, adapter = runtime.context()
        return {"ok": True, "app_url": adapter.url, "origin": adapter.origin,
                "configured": bool(adapter.token), "features": store.list()}
    return checked(run)


@router.get("/features/{ident}/packet")
def packet(ident: str):
    def run():
        store, adapter = runtime.context()
        saved = store.get(ident)
        if saved["origin"] != adapter.origin:
            raise core.GraftError("The app address changed. Create a feature for the new app address.")
        data = adapter.dataset()
        return {"id": ident, "revision": saved["revision"], "origin": adapter.origin,
                "app_url": adapter.url, "view": core.evaluate(saved["spec"], data["rows"]), "assignable": data["assignable"]}
    return checked(run)


@router.post("/review")
def review(body: dict):
    def run():
        core.keys(body, {"feature_id", "task_id", "action", "value"}, "change request")
        if isinstance(body.get("task_id"), bool) or not isinstance(body.get("task_id"), int):
            raise core.GraftError("Choose a valid task.")
        store, adapter = runtime.context()
        return store.prepare(adapter, body["feature_id"], body["task_id"], body["action"], body.get("value"))
    return checked(run)


@router.post("/review/{ident}/apply")
def apply_review(ident: str, body: dict):
    if set(body) != {"confirmed"} or body.get("confirmed") is not True:
        raise HTTPException(status_code=400, detail="Confirm the exact change in the Graft pane.")
    def run():
        store, adapter = runtime.context()
        result = store.apply(adapter, ident)
        runtime.event("data.updated", {"task_id": result["task_id"]})
        return result
    return checked(run)


@router.get("/renderer")
def renderer():
    return {"source": (_root / "desktop" / "renderer.js").read_text(encoding="utf-8")}
