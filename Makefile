.PHONY: test deep scan

check:
	@pnpm audit
	@pnpm prettier
	@pnpm lint
	@pre-commit run --all-files

fix:
	@pnpm prettier-fix
	@pnpm lint-fix

audit-fix:
	@pnpm audit --fix

toolchain:
	@npm install --global corepack@latest
	@corepack enable pnpm
	@echo node version `node --version`
	@echo pnpm version `pnpm --version`

install: toolchain
	@pnpm install --frozen-lockfile

test:
	@pnpm test
