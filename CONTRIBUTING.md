# Contributing & Team Workflow

Everyone works through GitHub. No exceptions — this history is part of your grade.

## The Loop (every task, every time)

1. **Create/claim an Issue** on GitHub (or pick one from the board)
2. **Create a branch** from `main`, named after the issue:
   - `feature/agreement-generation`
   - `fix/status-transition`
   - `docs/api-readme`
3. **Work on the branch.** Commit little and often with clear messages, e.g.:
   - `Add BondStatus model and migration`
   - `Fix document rejection reason not saved`
4. **Open a Pull Request** when done. In the PR description write `Closes #<issue-number>`
5. **Someone else reviews and merges.** Never merge your own PR.
6. Move the card to **Done** on the GitHub Projects board.

## Commit Message Style
- Start with a verb: `Add`, `Fix`, `Update`, `Remove`, `Document`
- One commit = one logical change. Small commits beat big ones.

## Rules
- Never commit directly to `main`
- Never commit `.env`, database files, or secrets
- Every PR must link an issue
- Blocked for more than 2 days? Comment on the issue and ask for help — silence is the only real failure

## Weekly Review (led by the Group Leader)
Every week, before the lab session:
1. Each member: show what was completed (merged PRs, moved cards)
2. Raise blockers
3. New issues created and assigned for the coming week
4. Decisions logged in `docs/decisions-log.md`
