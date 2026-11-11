# Graft

Ask your app for a missing feature. Graft turns a request in Hermes into a saved,
interactive feature inside a supported web app, with real data and reviewed actions.

**Status: working prototype.** Live Kanboard data, saved-feature rendering, a reviewed owner change and page-reload recovery have been verified. Initial model generation needed a temporary helper because the running agent had stale tool registration. The gateway has since reloaded all four tools; direct generation in a fresh chat and live due-date changes still need verification.

Start with [START-HERE.md](START-HERE.md) if you are setting it up for the first time.

## What it does

“Build a release room across my projects. Show overdue work by owner and let me
reassign tasks.” Hermes inspects the connector's capabilities and generates a
validated JSON blueprint. A fixed renderer turns the blueprint into metric cards,
charts and editable tables inside Kanboard. Follow-up requests revise the same
saved feature.

The model never supplies executable JavaScript, SQL or HTML. Filtering, grouping,
sorting and aggregation execute in the deterministic engine. The interface works
between model turns. Only explicit user confirmation in Graft's Hermes pane applies
a record change.

## Scope

- Hermes Desktop 0.23+ and its built-in Browser, with per-origin script consent.
- One configured Kanboard account and app address; open tasks in up to 30 projects,
  at most 5,000 records. No universal automatic app reverse engineering.
- Three widget types: tables, metric cards and bar charts; per-widget filtering.
- Supported writes: task reassignment and due dates (17:00 in the app user's timezone).
- Features live in profile-scoped plugin data, survive app-page reloads, and can be
  revised without changing the underlying application's source.

## Setup

The Mac runs Hermes and Graft. A VPS can run Kanboard on a loopback-only port,
reached with an SSH tunnel. An existing Kanboard instance also works.

Set **Settings → Plugins → Graft**:

- Kanboard address: `http://127.0.0.1:8460` when using the documented SSH tunnel.
- Kanboard username: your app user.
- Kanboard personal API token: enter privately in the masked settings field.

Enable both the agent half and the Desktop half in Hermes. Open Kanboard in the
chat's built-in Browser, use Graft's request box, and allow Graft on that origin
when Hermes asks. The Browser must remain embedded; the SDK does not bridge a
popped-out browser window.

## Architecture

`request → capability catalog → validated blueprint → data engine → page renderer`

The Python half registers `graft_capabilities`, `graft_data`, `graft_publish` and
`graft_list`. A profile-scoped API supplies rendered data to the Desktop half.
`ctx.preview.executeJavaScript` injects the fixed page renderer. Its bounded event
queue carries untrusted action proposals; the trusted Hermes pane reviews them.

Before a write, Graft checks the feature revision, configured account, expiry and
current task fingerprint. Each review is single use. A lost response is marked
`needs_check`, never automatically retried. Kanboard's API does not provide a
compare-and-swap write here: another app user could still change a task between
the final check and update. This is not an atomic concurrency guarantee.

The injected interface has a short renewable lease and removes itself when its
Desktop controller stops. Shadow DOM is used for styling, not as a security
boundary. Website content cannot authorize writes by itself.

## Privacy and permissions

The connector sends API requests only to the configured Kanboard address, using
the configured personal token read through Hermes secret scope. The token is not
sent to the page renderer, stored in feature blueprints or returned by the API.
Redirects are refused. Remote endpoints require HTTPS; HTTP is permitted only for
localhost addresses such as SSH tunnels.

The `graft_data` tool sends the selected sample of task text and project/owner
metadata to the active conversation, and therefore its model provider. Features,
reviewed changes and task titles in review history remain in the active profile's
Graft SQLite database. No telemetry or third-party analytics is included. Installing
the optional demo downloads the official version-pinned Kanboard Docker image.

## Development

Core checks require Python 3.11+:

```sh
python3 -m unittest discover -s tests -v
node --test tests/desktop.test.mjs
```

`python3 scripts/preview.py` serves an explicitly labelled sample-data renderer
preview on localhost port 8461. It cannot write to an app and does not call a model.

For Hermes admission, run `hermes plugins doctor <checkout>` and
`hermes plugins validate <checkout> --install-deps` once Hermes is installed.
Passing the unit tests does not replace those checks or a live integration test.

Official interfaces:

- [Desktop SDK](https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk)
- [Plugin developer guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)
- [Kanboard API](https://docs.kanboard.org/v1/api/)
