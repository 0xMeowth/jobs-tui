# jobs-tui

Terminal app for tailoring a resume per job application, with a Codex or Claude pane doing the writing.

## Setup

    brew install typst poppler   # or download the typst release binary from
                                  # https://github.com/typst/typst/releases into ~/.local/bin
    brew install --cask font-nunito
    uv sync
    export JOBS_DIR=~/dev/jobs        # default
    uv run jobs-tui init              # creates templates/ if missing
    uv run jobs-tui doctor

Replace `$JOBS_DIR/templates/resume-master.yaml` with your own content. Styling lives in `resume.typ`; the numbers at the top are the only knobs.

## Run

    uv run jobs-tui

Open it in a herdr pane next to your Codex or Claude pane. Keys are listed at the top of every screen. `p` picks the agent pane to pair with (on the review screen `p` renders, so click the pane box instead). `:` sends a message to the paired agent pane.

## Files per application

See `docs/superpowers/specs/2026-09-26-jobs-tui-design.md`.
