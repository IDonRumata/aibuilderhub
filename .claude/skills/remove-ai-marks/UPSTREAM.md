# Upstream

This skill is vendored, unmodified, from:

- Repo: https://github.com/guillaumemeyer/watermarks-remover
- Path: `skills/remove-ai-marks/`
- Commit: `e7e3b4ec90dab7cf01f87f7d8aac874692b0ef03` (2026-08-13)
- License: MIT (see `LICENSE`)

## Updating

```bash
git clone --depth 1 https://github.com/guillaumemeyer/watermarks-remover /tmp/wmr
rsync -a --delete /tmp/wmr/skills/remove-ai-marks/ .claude/skills/remove-ai-marks/ \
  --exclude UPSTREAM.md --exclude LICENSE
```

Then refresh the commit hash above.

## Not vendored

The upstream repo also ships tests, a `Makefile`, and Dockerfiles for the two
optional external backends (CtrlRegen pixel removal, reverse-SynthID scoring).
Those backends are heavy (~10 GB of model downloads), are not MIT-licensed, and
are never bundled — the skill degrades gracefully without them. Clone upstream
directly if you need them.

## Optional host tools

`c2patool` and `exiftool` are auto-detected when installed and improve C2PA and
PDF handling. Everything else is stdlib-only Python 3.
