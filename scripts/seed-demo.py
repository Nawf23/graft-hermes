#!/usr/bin/env python3
"""Add labelled example projects to the dedicated demo app. Never changes existing tasks."""
from datetime import datetime, timedelta
from getpass import getpass
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Kanboard, GraftError

app_url = input("Demo app address [http://127.0.0.1:8460]: ").strip() or "http://127.0.0.1:8460"
username = input("Demo app username [admin]: ").strip() or "admin"
token = getpass("Personal API token (hidden; paste here, not into chat): ")
api = Kanboard(app_url, username, token)
print("This adds three [Graft demo] projects, three demo users, and eighteen example tasks.")
print("It does not change or remove existing tasks. Demo-user passwords are random and are not printed.")
if input("Type GRAFT to add the demo data: ").strip() != "GRAFT":
    raise SystemExit("Cancelled. No demo data added.")

PROJECTS = {
    "Website launch": ["Finalize onboarding flow", "Review mobile checkout", "Approve launch artwork", "Check analytics events", "Confirm release checklist", "Publish launch announcement"],
    "Customer experience": ["Triage payment retries", "Update refund help page", "Review signup feedback", "Close accessibility issues", "Prepare support briefing", "Test account recovery"],
    "Developer platform": ["Review API migration guide", "Complete webhook integration tests", "Check SDK examples", "Document new rate limits", "Confirm release rollback steps", "Update developer changelog"],
}

try:
    owners = []
    for suffix, name in [("alex", "Alex · demo"), ("maya", "Maya · demo"), ("sam", "Sam · demo")]:
        existing = api.call("getUserByName", username="graft_demo_" + suffix)
        ident = int(existing["id"]) if existing else api.call("createUser", username="graft_demo_" + suffix,
                    password=secrets.token_urlsafe(32), name=name, role="app-user")
        if not ident: raise GraftError("Could not create a demo user. Use an administrator's personal token.")
        owners.append(int(ident))
    created = 0
    for project_index, (name, titles) in enumerate(PROJECTS.items()):
        full_name = "[Graft demo] " + name
        existing = api.call("getProjectByName", name=full_name)
        pid = int(existing["id"]) if existing else api.call("createProject", name=full_name)
        if not pid: raise GraftError("Could not create a demo project.")
        members = api.call("getProjectUsers", project_id=pid) or {}
        for owner in owners:
            if str(owner) not in {str(k) for k in members}:
                if not api.call("addProjectUser", project_id=pid, user_id=owner, role="project-member"):
                    raise GraftError("Could not add a demo teammate to the project.")
        known = {t["title"] for t in (api.call("getAllTasks", project_id=pid, status_id=1) or [])}
        columns = api.call("getColumns", project_id=pid) or []
        for index, title in enumerate(titles):
            if title in known: continue
            due = datetime.now() + timedelta(days=index - 3 + project_index)
            owner = 0 if index % 4 == 0 else owners[(index + project_index) % len(owners)]
            ident = api.call("createTask", title=title, project_id=pid, owner_id=owner,
                             column_id=int(columns[min(index % 3, len(columns) - 1)]["id"]) if columns else 0,
                             date_due=due.strftime("%Y-%m-%d 17:00"), priority=2 if index < 2 else 1,
                             time_estimated=[2, 4, 3, 6, 2, 5][index],
                             description="Example task created for the Graft demonstration. Safe to edit during the demo.")
            if not ident: raise GraftError("A demo task could not be added.")
            created += 1
        print("Ready:", full_name)
    print(f"Done. Added {created} tasks. Existing tasks were left as they were.")
except GraftError as exc:
    raise SystemExit(str(exc)) from None
