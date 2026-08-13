# Attribution

This skill is vendored from the open-source project **watermarks-remover**.

- Upstream: https://github.com/guillaumemeyer/watermarks-remover
- Source path: `skills/remove-ai-marks/`
- Commit: `6e5f9ce84e72dd7f71756473d4c819d933d8228b` (2026-08-13)
- License: MIT (see `LICENSE` in this directory)

## Local changes

None — files are copied verbatim from upstream.

## Not vendored

The upstream repo also ships tests, a `Makefile`, and `Dockerfile.synthid` for the
optional external reverse-SynthID scorer. Those are not included here. Anything in
`SKILL.md` that references `make docker-synthid-build` will not work in this repo;
use `scripts/setup_synthid.sh` directly, or fetch upstream if you need that path.

## Optional dependencies

Text and container paths (`.txt`, `.md`, `.html`, `.svg`, `.docx`, `.odt`) work on
stdlib Python 3 alone — verified in this repo. The image paths need extras that are
**not** installed here:

- `pillow` — required by `inspect_image.py` / `clean_image.py` (`pip install pillow`)
- `exiftool` — strongly preferred for PDF and EXIF/XMP strips
- `c2patool` — for reading/removing C2PA Content Credentials

## Updating

Re-clone upstream, copy `skills/remove-ai-marks/` over this directory, and refresh
the commit hash above.
