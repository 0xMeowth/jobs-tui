# jobs-tui

Terminal app for tailoring one resume per job application. You keep a master resume in YAML. For each job the app copies it, imports the job description, hands both to a coding agent (Codex or Claude Code) running in a herdr pane, and lets you accept or reject the agent's proposed edits one by one. Accepted edits render to a two page PDF with Typst.

## Requirements

- macOS, Python 3.12 or newer, and [uv](https://docs.astral.sh/uv/).
- `typst`, `pdfinfo` and `pdftoppm` on your PATH. `brew install typst poppler`, or download the Typst release binary into `~/.local/bin`.
- The Nunito font for the default template: `brew install --cask font-nunito`.
- Optional: Google Chrome. Job pages that block plain HTTP fetches fall back to a browser.
- [herdr](https://herdr.dev/), the terminal multiplexer the app talks to your coding agent through. See "Getting started with herdr" below.

## Install

    git clone <this repo> && cd jobs-tui
    uv sync

## Getting started with herdr

The app never calls a model itself. It types prompts into a Codex or Claude Code pane running next to it, and reads the files the agent writes. [herdr](https://herdr.dev/) ([source](https://github.com/herdrdev/herdr)) is the terminal multiplexer that makes this possible.

1. Install it: `brew install herdr`, or one of the other options at [herdr.dev/docs/install](https://herdr.dev/docs/install/).
2. Start `herdr` and create a workspace. Give it a label: the label is how the app names panes in its picker, as in `codex · jobs`.
3. Split the workspace into two panes side by side. Start your agent in one, ideally in `$JOBS_DIR`, and run the app in the other:

        ┌─ herdr workspace "jobs" ─────────────────────────────┐
        │ jobs-tui                 │ codex or claude            │
        │ (review, render, save)   │ (reads review-request.md,  │
        │                          │  writes proposed-edits.json)│
        └──────────────────────────────────────────────────────┘

4. The app reaches the agent only when it is itself started inside herdr. Outside herdr you can still review, render and save, but not brief the agent or send feedback.
5. Optional, for `ctx: N%` in the pane picker: in Codex run `/statusline` and enable context-used; in Claude Code use a status line that prints `ctx: N%`.

## First run

1. Pick a data folder. Everything the app writes lives there, never in this repo.

        export JOBS_DIR=~/dev/jobs    # this is the default

2. Create the folder layout and starter files.

        uv run jobs-tui init

   This creates `templates/resume.typ` and `templates/resume-master.yaml` in `JOBS_DIR`, plus an empty `companies/` folder.

3. Put your own resume into `templates/resume-master.yaml`. The starter is a skeleton with bracketed slots. Keep the shape:

        name: <your name>
        contact: {location: "...", phone: "...", email: "...", linkedin: "..."}
        sections:
          - id: experience
            title: Experience
            entries:
              - id: job1
                org: <employer>
                title: <job title>
                dates: <start> – <end>
                bullets:
                  - id: job1.b1
                    text: <what you did and the result>
          - id: projects
            title: Projects
            entries:
              - id: proj1
                org: <project name>
                url: github.com/<you>/<repo>    # optional; dates are optional too
                bullets:
                  - id: proj1.b1
                    text: <what you built>
          - id: skills
            title: Skills
            bullets:
              - id: skills.b1
                text: "<area>: <tools>"

   Every entry and bullet has an `id`. Ids are how the agent addresses edits, so give each one a short stable name and never renumber.

4. Check the setup.

        uv run jobs-tui doctor

   Every line marked `!!` must be fixed before the app runs. Lines marked `--` are optional.

5. Start the app.

        uv run jobs-tui

## Daily use

Open the app in one herdr pane and your agent in another. On launch the app asks you to pick the agent pane. Press `p` later to change it. In the pane list, Enter pairs the highlighted pane and `c` pairs it and sends `/clear` to start a fresh conversation (skipped while the agent is working). The list labels each pane with its agent and workspace, and with its context use when the pane footer shows it: `ctx: N%` (a Claude Code status line) or `Context N% used` (Codex `/statusline` with context-used). Sending with `s` or Start review is refused until a pane is paired. Keys are listed at the top of every screen.

- `n` new application. Paste the posting URL and press Enter. Company and role fill in from the page, and you can correct them before the folder is created. LinkedIn URLs use the public guest endpoint. Other sites are fetched over HTTP, then with Chrome if needed. No URL? Paste the description and type company and role yourself.
- If no agent pane is paired yet, a dialog asks you to pick one. Then the brief dialog opens. Say what the agent should focus on, then press Start review. The app writes `review-request.md` into the application folder and tells the agent to read it.
- The review screen fills as the agent writes `proposed-edits.json`. `a` accepts and writes resume.yaml, `x` rejects, `e` lets you reword before accepting, `c` attaches a comment, which asks for a rework, even on a rejected edit. A reject keeps your original wording. `x` on a commented edit asks before it discards the comment. `u` undoes any verdict, and reverts an accepted replace or add if the bullet is unchanged since. Removes cannot be reverted. `s` sends all rework comments in one round, and marks the reworked edits as sent until the revision arrives. Revised edits show the previous wording, and `v` accepts that instead.
- `r` renders the PDF (kept in `preview/`), opens it, and shows the page count. `o` reopens it. `s` on that screen saves a copy of the PDF under a name you choose, in the application folder, once it fits two pages and is rendered from the current resume.yaml.
- Before the first save, `s` runs the final check over every job and project bullet: one spelling convention (the posting's, when it shows one), spacing, plain quotes and dashes, and trailing periods. Findings appear on the render screen: `a` fixes, `x` dismisses, `e` edits, `u` undoes. When none are left the PDF re-renders and the save dialog opens. The check runs once; the status bar shows `checked`, or how many bullets changed since. `S` saves without the check.
- `w` opens a notes editor for the selected application, on the list, review and render screens. Use it for text you wrote outside the CV, such as answers to portal questions. It is saved as `notes.md` without checks; saving it empty deletes it.
- `f` finalizes after you submit. It records the date and adds a row to `tracker.md`. `t` shows the tracker; its Notes column shows ✓ when the application has notes.
- Save and finalize both refuse while the review is unfinished: every edit must be accepted or rejected, and a sent brief must have produced proposed-edits.json.
- `,` opens settings on any screen. It turns the final check before saving on or off (on by default). Settings are stored in `$JOBS_DIR/settings.json`.
- `x` on the list deletes a draft after confirmation. Submitted applications cannot be deleted.
- The app keeps each application's `resume.yaml` read-only and only unlocks it around its own writes, so the agent cannot quietly edit it. The review screen shows CURRENT straight from the file and refuses edits whose claimed baseline no longer matches. If the file changes outside the app anyway, a warning points at the last app-written copy in `preview/resume.snapshot.yaml`; press `y` to adopt the outside change.

## Data folder layout

    $JOBS_DIR/
      templates/resume-master.yaml    your resume
      templates/resume.typ            layout; the numbers at the top are the only knobs
      tracker.md                      one row per submitted application
      settings.json                   settings from , (final check on or off)
      companies/<company>/<role>/
        application.json              company, role, url, dates
        resume.yaml                   this application's copy of the master
        jd.md                         imported job description
        review-request.md             your brief for the agent
        proposed-edits.json           written by the agent
        review-feedback.json          your decisions
        final-check.json              final check state before saving
        notes.md                      your notes for this application (w)
        <name>.pdf                    copies saved with s on the render screen
        preview/resume.pdf            latest render, plus page images
        preview/resume.snapshot.yaml  resume.yaml as the app last wrote it

## Other commands

    uv run jobs-tui jd <url>    # print a job description as markdown without creating an application

## Current limitations

- macOS only: PDFs open with the macOS `open` command, and the browser fallback for job pages expects Google Chrome in `/Applications`.
- Only Codex and Claude Code are tested. Other agents herdr detects appear in the picker and will probably work, since the prompts are plain text, but they are untested.
- The agent is not sandboxed. The read-only file, the live CURRENT display and the snapshot warning make a stray write fail or show up, but an agent that deliberately changes permissions can still edit files.
- One resume template: a single-column, ATS-friendly layout, built and tested by one person and optimised for exactly two A4 pages. Other ATS-friendly formats exist; this is the one provided.
- The final check covers job and project bullets only, in English, with a fixed British/American word list rather than a dictionary. Agent checks are not built yet.
- Accepting a remove the agent proposed cannot be undone. The brief tells the agent not to propose removals.
- Job import: LinkedIn postings use the public guest page. Pages behind a login cannot be fetched; paste the description instead.
- If the last agent pane closes while the app is running, the pane picker keeps the old entries until it finds panes again.
- Single user, local files only, no sync.

## Development

    uv run pytest
