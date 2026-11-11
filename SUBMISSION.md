# Graft submission materials

Public source folder: graft-public. It excludes private handoff notes, credentials, databases, the VPS address, scratch files and Git metadata.

## Repository

Suggested public repository: Nawf23/graft-hermes

Upload the CONTENTS of graft-public to the repository root. plugin.yaml must be at the root. Do not upload the outer folder as an extra directory.

## Catalog PR

Target: https://github.com/NousResearch/hermes-agent
Add one file: plugin-catalog/graft.yaml

The entry must pin the full 40-character commit SHA from the public plugin repository. Do not use a branch, tag, short SHA or placeholder.

Title: Add Graft: persistent in-app features for Kanboard

Body:
Graft turns a Hermes request into a persistent, interactive feature inside a supported web app. The Kanboard prototype supports cross-project metrics, workload charts and editable task tables. Record changes require an explicit review in Graft’s trusted Desktop pane.

Surfaces: four Python tools, a bundled builder skill, authenticated profile-scoped plugin API and Desktop SDK page-script integration. No runtime overrides of Hermes core, application-source modification or self-updater.

Disclosures: network calls go to the configured Kanboard endpoint; a bounded task sample is sent to the active model. The personal API token is read through Hermes secret scope and is never injected into the webpage. Feature definitions and review history use profile-scoped plugin data. The optional demo setup downloads a version-pinned official Docker image; core plugin operation launches no shell commands or background server.

Verified: live data, persisted in-app interface, reviewed owner write, fresh API read and reload recovery; 21 Python tests and a Desktop slow-network regression test. Initial model generation required a helper due to stale registration; the gateway has been reloaded, and the fresh-chat tool path and due-date write remain to be verified.

## X caption

Graft gives existing apps new features. A persistent release room inside Kanboard: live cross-project metrics, workload charts and task editing with review before writes. Built as a Hermes Agent plugin. @NousResearch

Attach the actual working-demo video, under 90 seconds.

## Form

https://form.typeform.com/to/FwJLvOln

Submit the catalog PR URL and X demo-post URL. No entry is submitted until both links are sent through the form.
