"""Hermes-specific configuration. Imported only when an enabled plugin is used."""
from pathlib import Path
import importlib.util

_spec = importlib.util.spec_from_file_location("graft_own_core", Path(__file__).with_name("core.py"))
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)


def context():
    from hermes_cli.config import load_config_readonly
    from plugins.plugin_storage import plugin_data_dir
    from agent.secret_scope import get_secret

    config = load_config_readonly()
    settings = config.get("plugins", {}).get("entries", {}).get("graft", {}).get("settings", {})
    adapter = core.Kanboard(settings.get("kanboard_url", "http://127.0.0.1:8460"),
                           settings.get("kanboard_user", "graft"), get_secret("GRAFT_KANBOARD_TOKEN") or "")
    return core.Store(plugin_data_dir("graft") / "graft.db"), adapter


def event(name, payload):
    from hermes_cli.plugin_events import broadcast_plugin_event
    broadcast_plugin_event("graft", name, payload)
