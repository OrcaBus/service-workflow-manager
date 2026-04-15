.PHONY: test deep scan

check:
    # Audit dependencies (critical — advisory until pnpm#11265)
    # npm retired the legacy /v1/security/audits endpoint server-side; pnpm 10.x
    # still calls it and fails with HTTP 410. Tracked upstream in
    # https://github.com/pnpm/pnpm/issues/11265 — fix lands in pnpm 11. Until
    # we bump the monorepo to pnpm 11, Dependabot is the real security coverage
    # here, so this step stays advisory rather than silently masking the gap.
    # @pnpm audit
	@pnpm prettier
	@pnpm lint
	@pre-commit run --all-files

fix:
	@pnpm prettier-fix
	@pnpm lint-fix

audit-fix:
	@pnpm audit --fix

install:
	@pnpm install --frozen-lockfile

test:
	@pnpm test
