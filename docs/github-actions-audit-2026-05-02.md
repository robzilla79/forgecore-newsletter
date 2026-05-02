# GitHub Actions Audit — 2026-05-02

## Objective

Reduce duplicate ForgeCore production automation by keeping only the workflows needed for the current AM/PM newsletter publishing system.

## Active workflows

### `.github/workflows/generate-am.yml`

Status: active.

Purpose: scheduled AM wrapper. Calls the shared generator with `issue_slot: am`.

Reason kept: this is part of the current production cadence.

### `.github/workflows/generate-pm.yml`

Status: active.

Purpose: scheduled PM wrapper. Calls the shared generator with `issue_slot: pm`.

Reason kept: this is part of the current production cadence.

### `.github/workflows/generate.yml`

Status: active.

Purpose: shared generation workflow used by AM and PM wrappers.

Reason kept: this is the production path for research, agent generation, improvement, quality gate, affiliate guard, render, verification, commit, Kit draft, and Cloudflare Pages deploy.

### `.github/workflows/operator-review.yml`

Status: active.

Purpose: daily operator review artifact and state update.

Reason kept: useful observability for the ForgeCore operator workflow. This does not publish newsletter issues.

## Disabled workflows

### `.github/workflows/deploy.yml`

Status: disabled.

Reason: legacy standalone deploy duplicated the shared generator deploy path. The active `generate.yml` workflow already runs `publish_site.py`, `verify_publish.py`, commits generated assets, and deploys `site/dist` to Cloudflare Pages.

Risk removed: duplicate Cloudflare deploys and duplicate Kit draft attempts after generated content commits.

### `.github/workflows/em-push.yml`

Status: disabled.

Reason: legacy Local-Em upload/deploy/send path is no longer the production publishing path. Current publishing should flow through the AM/PM generator wrappers.

Risk removed: parallel publishing path with `continue-on-error` deploy/send steps and `KIT_SEND_MODE: public`.

### `.github/workflows/improve.yml`

Status: disabled.

Reason: hourly autonomous improvement is redundant because `generate.yml` already runs `improve_until_passes.py` before quality gate, render, publish verification, commit, and deploy.

Risk removed: hourly production mutations, extra commits, duplicate deploys, and unexpected content drift.

## Definition of done

- AM generation remains scheduled through `generate-am.yml`.
- PM generation remains scheduled through `generate-pm.yml`.
- Shared generator remains callable through `generate.yml`.
- Standalone deploy, Local-Em push, and hourly improvement no longer run automatically.
- Disabled workflows remain as explicit audit markers rather than hidden deletions.

## Commit messages used

```text
ops: disable legacy standalone deploy workflow
ops: disable legacy local-em push workflow
ops: disable hourly improvement workflow
docs: add github actions audit
```
