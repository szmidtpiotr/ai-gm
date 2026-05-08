# DEV/PROD Host Separation Plan

## Context

Today both DEV and PROD runtimes have been operated on the same machine: `192.168.1.61`.
This has caused environment drift and deployment mismatches, because some parts were built or restarted in DEV while other parts still came from PROD on the same host.

Current working assumption for this phase:

- `192.168.1.61` should become a **DEV-only** machine.
- The mounted workspace on the local machine points at the server files under `/home/piotrszmidt/remout_mount/ai-gm/`.
- A separate Proxmox VM will be created later for **PROD**.
- Future PROD deployment should happen from GitHub `main` only, and only after explicit user approval.

## Goal

Remove PROD runtime responsibilities from `192.168.1.61` and leave a clean, explicit DEV environment there.

## Target End State

- `192.168.1.61` runs **only DEV** services for AI-GM.
- DEV uses its own compose stack, ports, domains, env files, and persistent data.
- No PROD container, reverse-proxy target, systemd job, scheduled task, or deployment path remains active on `.61`.
- PROD is later recreated on dedicated host `192.168.1.63` with a clean deployment flow from `main`.

## In Scope

- Inventory and classification of all AI-GM runtime elements on `.61`.
- Disabling and removing PROD-specific runtime/configuration from `.61`.
- Verifying that DEV still works after cleanup.
- Preparing the future PROD cutover checklist for a separate VM.

## Out of Scope

- Deploying PROD on the new VM in this phase.
- Syncing `develop` to `main` in this phase.
- Deleting historical data before the new PROD machine is live and verified.

## Risk Areas

The dangerous part is not repository code cleanup but shared infrastructure on the same host:

- Docker containers, images, networks, and named volumes
- reverse proxy / Nginx / Nginx Proxy Manager routes
- PROD-only env files or secrets mixed with DEV files
- systemd units, background jobs, cron entries, deploy scripts
- shared host ports and DNS/domain mappings
- databases, uploads, backups, and any PROD-only persistent data

## Required Discovery Before Removal

Before deleting anything on `.61`, classify each item as `DEV-only`, `PROD-only`, or `shared/unclear`:

1. Compose files and active projects
2. Running/stopped Docker containers
3. Docker named volumes and bind mounts
4. `.env`, `.env.dev`, `.env.prod`, secret files, and deploy scripts
5. Reverse proxy config, domains, and port mappings
6. systemd user/system services
7. cron jobs or automation hooks
8. databases, uploads, backups, and generated assets

Anything marked `shared/unclear` must be resolved before PROD removal.

## Recommended Removal Order

1. Freeze changes and take inventory of the current `.61` runtime.
2. Back up PROD-specific config and data references before deleting anything.
3. Disable PROD ingress first:
   - domains
   - proxy routes
   - public listeners
4. Stop PROD application services.
5. Remove PROD containers/projects after confirming DEV uses different names/resources.
6. Remove PROD-only systemd/cron/deploy hooks.
7. Remove PROD-only env/config/build artifacts.
8. Keep PROD data backups archived until the new PROD VM is live and accepted.
9. Re-verify DEV end-to-end after cleanup.

## DEV Standards After Cleanup

To prevent future drift, DEV on `.61` should remain explicit and isolated:

- separate compose project for DEV
- separate ports for DEV only
- separate domain/subdomain for DEV
- separate env file naming
- separate Docker volumes
- no PROD deploy workflow targeting `.61`
- no manual PROD build or restart actions on `.61`

## Future PROD VM Expectations

When the new Proxmox VM is ready:

- clone from GitHub on the new machine
- deploy PROD from `main` only
- use separate secrets and env files
- use separate domains/ports/reverse proxy config
- validate health checks before switching traffic
- cut over only after explicit approval

## Confirmed Decisions

The following decisions were confirmed during planning:

- New PROD host IP: `192.168.1.63`
- Existing AI-GM PROD domains stay the same; reverse-proxy targets will be repointed to `.63`
- `192.168.1.61` remains the DEV machine and should be used for development + pushes to `develop`
- PROD should include the observability stack on the new host
- Initial PROD rollout should use manual script-based deployment, not GitHub Actions
- PROD runtime should support user-provided custom LLM configuration after install
- Existing PROD database may be reused on the new host
- Old PROD data on `.61` should be deleted only after `.63` is deployed and verified

## Current Host Audit

Initial SSH verification of `192.168.1.63`:

- Hostname: `ai-gm-prod`
- User prepared for access: `claude`
- OS: Ubuntu 24.04 LTS
- Current state: minimal host, no `docker` installed yet, no `git` detected yet
- `sudo` is available but requires a password

This is acceptable for the migration plan, because `install.sh` is intended to bootstrap a fresh machine.
However, no project bootstrap or deploy should be executed on `.63` until release approval for `main`.

## Remaining Checks

The high-level migration plan is already agreed.
Before destructive cleanup on `.61` or bootstrap on `.63`, the remaining work is technical verification:

1. Audit `install.sh` for fresh-host compatibility with dedicated PROD + observability
2. Audit `scripts/deploy_prod.sh` for dedicated PROD host use on `.63`
3. Audit docs / workflows that still assume `.61` is the PROD machine
4. Inventory actual PROD-only resources still present on `.61`
5. Decide the exact DB handoff method when PROD bootstrap starts on `.63`

## Phase Status

This document records the planning phase only.
No cleanup or server-side deletion has been executed yet.
