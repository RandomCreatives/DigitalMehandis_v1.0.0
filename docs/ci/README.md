# CI workflow — apply this by hand

`.github/workflows/test.yml` on `main` has **never run**. Every push since June
fails in 0 seconds with:

> This run likely failed because of a workflow file issue.

## Why

Line 30 of the committed workflow is:

```yaml
DATABASE_URL: sqlite+aiosqlite:///:memory:
```

Unquoted, that is **not valid YAML** — the colons either side of `memory` are
read as a nested mapping, so the parser dies before the workflow loads. No job,
no tests, ever.

## How to apply

The Assistant/App used to make these changes does not have the GitHub
`workflows` permission, so it cannot push to `.github/workflows/` (see issue
#23). Copy the corrected file into place:

```bash
cp docs/ci/test.yml .github/workflows/test.yml
git add .github/workflows/test.yml
git commit -m "Fix CI: quote SQLite URL so the workflow parses"
git push
```

## What the corrected workflow fixes

| Fix | Why |
|---|---|
| Quotes `DATABASE_URL` and `SECRET_KEY` | the bare `sqlite+aiosqlite:///:memory:` breaks YAML parsing |
| Adds `frontend/.eslintrc.json` | `eslint` and `eslint-config-next` were already installed, but with no config `next lint` prompts **interactively**, so CI hangs |
| Removes an orphan `eslint-disable ... @typescript-eslint/no-explicit-any` | that plugin is not configured; naming an unknown rule is itself an error |
| Adds a route-count smoke step | `modules.loader` logs import failures and continues, so a broken module silently drops its routes |
| Splits the frontend job into typecheck + lint | `tsc --noEmit` catches what lint misses |

Verified locally with the exact commands CI runs:

```
pytest --tb=short -q            ->  88 passed
python -c 'from app.main ...'   ->  97 routes registered
npx tsc --noEmit                ->  clean
npm run lint                    ->  exit 0
```
