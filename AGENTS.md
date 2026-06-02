# AI-GM Agent Notes

## Remote-Only Execution

- This workspace is a mapped NFS folder from `192.168.1.61:/home/piotrszmidt`.
- Edit files under `/home/piotrszmidt/remote_mount/ai-gm`, but execute runtime commands only on `piotrszmidt@192.168.1.61`.
- Do not run local Docker, local `pytest`, local dev servers, or local rebuilds for this project.
- After backend or frontend changes, perform any needed restart or rebuild on the remote dev environment.
- Use `https://aigm-dev.studio-colorbox.com/` to verify dev deployments unless the user explicitly requests another environment.

## Safe Defaults

- Default to the remote dev stack (`ai-gm-dev-*` containers), not production.
- Do not touch production containers unless the user explicitly requests it.

## Testing & TDD

- **Verify setup:** `./scripts/verify_testing_setup.sh`
- **Local pytest:** `./scripts/test_local.sh` (no SSH)
- **Docker pytest:** `./scripts/test_dev.sh` (container `ai-gm-dev-backend-1`)
- **Guide:** [`docs/TESTING.md`](docs/TESTING.md) · skill: `.cursor/skills/ai-gm-tdd/SKILL.md`
- **Live playtest:** `.claude/skills/game-test/SKILL.md` (not unit tests)
