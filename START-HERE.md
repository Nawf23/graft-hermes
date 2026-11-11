# Install Graft

Requires Hermes Desktop 0.23+ and a reachable Kanboard instance.

1. Install this repository using Hermes Capabilities → Plugins → Install.
2. Enable the Agent and Desktop components. Start a fresh chat after enabling so its Python tools are included.
3. In Graft settings, enter the Kanboard address, username and personal API token. Keep the token in the masked settings field.
4. Open the same Kanboard address in Hermes’s embedded Browser and sign in.
5. Open the Graft pane. Type a feature request or use Fill with release-room example, then Create or revise feature.
6. Select the saved feature and Attach to app. Allow Graft’s page-script permission on that app origin.
7. Use Edit on a task to propose a change. Review and apply it in Graft’s Hermes pane.

Graft supports Kanboard, open tasks, metric cards, owner/project charts and editable task tables. It does not need macOS App Management or computer-control access for this workflow.

The optional scripts/seed-demo.py adds labelled example projects and tasks to a dedicated demo instance. It prompts privately for a personal token. Do not seed a production workspace.
