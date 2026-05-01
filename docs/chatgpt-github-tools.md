# ChatGPT GitHub Tooling Profile (ForgeCore)

## Scope
- Primary repository: `robzilla79/forgecore-newsletter`
- Operating mode: autonomous on feature branches, PR-based integration

## Required repository permissions
- Metadata: **Read**
- Contents: **Read and Write**
- Pull requests: **Read and Write**
- Actions: **Read and Write**
- Checks: **Read**
- Commit statuses: **Read**

## Required exposed actions/tools
1. `create_branch`
2. `fetch_file`
3. `create_or_update_files`
4. `commit_files` (or equivalent multi-file commit)
5. `create_pull_request`
6. `update_pull_request`
7. `dispatch_workflow`
8. `get_commit_status`
9. `fetch_workflow_run_jobs`
10. `fetch_workflow_job_logs`

## Default safety policy
- Autonomous commits are allowed only on non-default feature branches.
- Direct pushes to `main` are denied by default.
- Force push is denied.
- PR merge requires explicit human approval.
- Deployment requires successful validation and publish verification.

## Governance notes
- Classify each PR as exactly one: **Stabilization**, **Hardening**, or **Expansion**.
- Treat workflow/control-plane changes as high-risk unless explicitly authorized.
- Disclose partial completion, blockers, and follow-up work in every PR report.
