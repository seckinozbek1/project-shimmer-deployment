# The review desk: a short guide

The review desk is one plain page for running a single review and reading its results. It is part of
v1.0-alpha. It does everything through the same server as the full console, so a review started here is
the same review the console would start. This guide is in English; a Turkish version follows after the alpha.

For installing Shimmer and putting your material in place, see the [operator guide](USER_GUIDE.md),
sections 1 to 3.

## 1. Open it

1. Start Shimmer as usual (the desktop starter on Windows, the menu launcher on Linux or macOS). It
   prints the console address and gives you a token.
2. Open the console address in your browser and add `?view=desk` at the end, for example
   `http://127.0.0.1:8000/console?view=desk` (your port may differ).
3. Paste the token into **Token** and press **Connect**. The status beside the button changes to
   "connected".

Alpha: keyless for local trial only (loopback); a non-local address needs the token. The desktop
starter runs the server on 127.0.0.1 in keyless local mode, so the desk connects by itself with no
token ("connected (local trial: no token needed on this computer)") and step 3 is not needed. The server
refuses keyless mode on any other address, and answers only requests from this computer while it is on.

The page itself holds no data. Nothing is shown until you connect, and the token is never put in the
address bar or saved by the page.

## 2. The screens, top to bottom

**In place** lists the files already in `input/conventions`, `input/context` and `input/operational`
(names and sizes only, never their content) and the review rules compiled so far, by id.

**Start a review**
1. **Files**: choose the files for this review.
2. Give each file a role: **Review target** (the document to review), **Earlier version** (an older
   version of it), **Grounding** (reference material) or **Review rules file** (your review rules).
3. **Framing question** (optional): a question the review should keep in mind.
4. **Privacy**: choose **Normal** or **Sensitive**. Sensitive is refused while the privacy layer is not
   switched on; the page says so before anything is sent.
5. Read the plan the page shows, tick **I have read this plan**, then press **Start the review**. Nothing
   is sent before you tick the box.

**Waiting for a decision** lists runs that stopped to ask you something. Open the run, read the
question, add a reason if you like, and press **Approve** or **Deny**. Your answer is recorded; the run
reads it the next time it checks, so "recorded" does not yet mean "resumed".

**Runs** lists every run with its state and outcome. Press **Open** to see one.

**Run** shows the chosen run:
- its state and outcome, and its documents;
- **Progress (measured)**: documents done, time elapsed, the rate, and the time left at that rate. A
  value that cannot be measured yet says "not measurable" and why;
- **Findings**: each finding with its document, unit, rule, verdict and who wrote it. A finding written
  by a model is marked as such: it was not promoted and not checked by Python;
- **Read reviewed document**: the document with the findings quoted under its parts;
- **Cancel this run** (only while it is queued or running): stops further work. Nothing is deleted;
  whatever the run wrote stays in its folder;
- **Show the end of the log**: the last 40 lines of the run's log;
- **Download (zip)**: all deliverables, or one document's. An archive from a run that has not finished
  successfully is called partial.

The page refreshes a running run every few seconds, and never while you are typing a reason.

## 3. Sealed runs

A sealed run is a test whose answers must not leak. The desk shows it as counts and timings only: how
many documents are done, and how long it has taken. It shows no document names, no findings, no
reviewed document, no log, no download and no question text. A sealed run can still be cancelled or
answered.

## 4. If something goes wrong

| What you see | What it means |
|---|---|
| "not connected: ... 401" | The token is wrong or was pasted with extra characters. Paste it again. |
| "Choose Normal or Sensitive" | Pick a privacy choice before starting. |
| Sensitive is refused | The privacy layer is not switched on; use Normal or ask the operator. |
| "Refused, nothing started" | The server turned the plan down; the message says why. No review started. |
| A run shows "stopped" with an outcome other than "succeeded" | Open it and read the end of the log. |
| A button answers 403 | The run is sealed; only counts and timings are shown. |

## 5. What the desk does not do

It does not delete anything, change your review rules, or run on a rented cloud machine. For those, and
for every other view (pairs, amendments, replies, reports), use the full console at `/console`.

## How it was checked

Check 662 of the verification gate starts the server on a test folder with a stand-in for the review
pipeline, presses every control of this page in turn, and checks that each one calls the right server
route and reads or writes the right record, that sealed runs show counts only, and that no token or key
appears on any screen. It does it a second time in keyless local mode with no token at all. Check 681
proves that keyless mode is refused on a non-local address and refuses requests from another computer.
No real review is run by either check.
