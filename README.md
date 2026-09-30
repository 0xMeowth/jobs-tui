# jobs-tui

Terminal app for tailoring one resume per job application. You keep a master resume in YAML. For each job the app copies it, imports the job description, hands both to a coding agent (Codex or Claude Code) running in a herdr pane, and lets you accept or reject the agent's proposed edits one by one. Accepted edits render to a two page PDF with Typst.

## Requirements

- macOS, Python 3.12 or newer, and [uv](https://docs.astral.sh/uv/).
- `typst`, `pdfinfo` and `pdftoppm` on your PATH. `brew install typst poppler`, or download the Typst release binary into `~/.local/bin`.
- The Nunito font for the default template: `brew install --cask font-nunito`.
- Optional: Google Chrome. Job pages that block plain HTTP fetches fall back to a browser.
- Optional: herdr with a Codex or Claude Code pane. Without it the app copies prompts to the clipboard for you to paste.

## Install

    git clone <this repo> && cd jobs-tui
    uv sync

## First run

1. Pick a data folder. Everything the app writes lives there, never in this repo.

        export JOBS_DIR=~/dev/jobs    # this is the default

2. Create the folder layout and starter files.

        uv run jobs-tui init

   This creates `templates/resume.typ` and `templates/resume-master.yaml` in `JOBS_DIR`, plus an empty `companies/` folder.

3. Put your own resume into `templates/resume-master.yaml`. The starter is a skeleton with bracketed slots. Keep the shape:

        name: <your name>
        contact: {phone: "...", email: "...", linkedin: "..."}
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
          - id: skills
            title: Skills & Interests
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

Open the app in one herdr pane and your agent in another. Press `p` in the app and pick the agent pane from the dropdown. Keys are listed at the top of every screen.

- `n` new application. Paste the posting URL and press Enter. Company and role fill in from the page, and you can correct them before the folder is created. LinkedIn URLs use the public guest endpoint. Other sites are fetched over HTTP, then with Chrome if needed. No URL? Paste the description and type company and role yourself.
- If no agent pane is paired yet, a dialog asks you to pick one. Then the brief dialog opens. Say what the agent should focus on, then press Start review. The app writes `review-request.md` into the application folder and tells the agent to read it.
- The review screen fills as the agent writes `proposed-edits.json`. `a` accepts and writes resume.yaml, `x` rejects, `e` lets you reword before accepting, `c` attaches a comment, which asks for a rework, even on a rejected edit. A reject keeps your original wording. `x` on a commented edit asks before it discards the comment. `u` undoes any verdict, and reverts an accepted replace or add if the bullet is unchanged since. Removes cannot be reverted. `s` sends all rework comments in one round, and marks the reworked edits as sent until the revision arrives. Revised edits show the previous wording, and `v` accepts that instead.
- `r` renders `resume.pdf` and shows the page count. `s` on that screen saves a copy of the PDF under a name you choose, in the application folder, once it fits two pages and is rendered from the current resume.yaml.
- `f` finalizes after you submit. It records the date and adds a row to `tracker.md`.
- Save and finalize both refuse while the review is unfinished: every edit must be accepted or rejected, and a sent brief must have produced proposed-edits.json.
- `x` on the list deletes a draft after confirmation. Submitted applications cannot be deleted.

## Data folder layout

    $JOBS_DIR/
      templates/resume-master.yaml    your resume
      templates/resume.typ            layout; the numbers at the top are the only knobs
      tracker.md                      one row per submitted application
      companies/<company>/<role>/
        application.json              company, role, url, dates
        resume.yaml                   this application's copy of the master
        jd.md                         imported job description
        review-request.md             your brief for the agent
        proposed-edits.json           written by the agent
        review-feedback.json          your decisions
        resume.pdf                    latest render
        <name>.pdf                    copies saved with s on the render screen

## Other commands

    uv run jobs-tui jd <url>    # print a job description as markdown without creating an application

## Development

    uv run pytest

Design notes are in `docs/superpowers/specs/2026-09-26-jobs-tui-design.md`.
