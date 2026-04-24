# Code Smell Cleanup Specs

This folder contains the sprint specs for the repo-wide cleanup pass outside `api/routers/` and `api/services/`.

## Lanes

- `admin-workspace-shell.md` - split `AdminWorkspace.tsx` into smaller shell pieces
- `student-page-shell.md` - extract state and persistence from `page.tsx`
- `admin-e2e-fixtures.md` - move inline Playwright fixtures into shared builders
- `validate-profiles-cli.md` - remove `sys.path` surgery from the profile validator
- `api-models-split.md` - split the transport schema bag by domain
- `terraform-module-split.md` - break `terraform/main.tf` into modules

## Suggested Order

0. `implementation_plan.md`
1. `admin-workspace-shell.md`
2. `student-page-shell.md`
3. `admin-e2e-fixtures.md`
4. `validate-profiles-cli.md`
5. `api-models-split.md`
6. `terraform-module-split.md`

The first three are the best fit for a single frontend cleanup sprint. The last three are still valuable, but they are larger architecture or infra refactors and are easier to ship separately.
