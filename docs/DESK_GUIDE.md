# The review desk: a short guide

The review desk is one plain page for running a single review and reading its results. The review desk was built for v1.0-alpha (the current state of the code, not a release that reached its targets) and was fixed after the alpha freeze, on 22 November 2026. It does everything through the same server as the full console, so a review started here is
the same review the console would start. The desk and this guide are in English only in the alpha; a Turkish version follows after it. The top of the page says where the review runs: Local (the review runs on the computer that runs this server, with a local model; document text is not sent to model providers and there are no provider charges) or Cloud (document text goes to the configured model providers and usage is charged). Costs and run reports are in the full console.

For installing Shimmer and putting your material in place, see the [operator guide](USER_GUIDE.md),
sections 1 to 3.

## 1. Open it

1. Start Shimmer as usual. The desktop starter on Windows opens the desk by itself (button **Open review
   desk**); the menu launcher on Linux or macOS prints the console address and gives you a token.
2. If the desk is not open, open the console address in your browser and add `?view=desk` at the end,
   for example `http://127.0.0.1:8000/console?view=desk` (your port may differ). The full console also
   links to it (**Simple review desk**).
3. Only when the page asks for it: paste the token into **Token** and press **Connect**. The status beside
   the button changes to "connected".

Alpha: keyless for local trial only (loopback); a non-local address needs the token. The desktop
starter runs the server on 127.0.0.1 in keyless local mode, so the desk connects by itself with no
token ("connected (local trial: no token needed on this computer)") and step 3 is not needed. While
keyless mode is on, it opens every protected route of this server with no token, not only the desk:
the full console's data, starting runs, answering a run's questions, logs and downloads. Any program or
other user on this computer can use them; other computers are refused. The server refuses keyless mode
on any other address. Set `SHIMMER_KEYLESS_LOCAL=0` before starting to require the token.

The page itself holds no data. Nothing is shown until you connect, and the token is never put in the
address bar or saved by the page.

## 2. The screens, top to bottom

**In place** lists the files already in `input/conventions`, `input/context` and `input/operational`
(names and sizes only, never their content) and the review rules compiled so far, by id.

**Start a review**
1. **Files**: choose the files for this review.
2. Give each file a role: **Review target** (the document to review), **Earlier version** (an older
   version of it), **Reference (background)** or **Rules file (the server decides)**. The first file starts as the review
   target. Reference and rules files are sent the same way: the server reads each one and decides whether it is a
   rules file.
3. **Framing question** (optional): a question the review should keep in mind.
4. **Privacy**: choose **Normal** or **Sensitive**. Sensitive is refused while the privacy layer is not
   switched on; the page says so before anything is sent.
5. Read the plan the page shows, tick **I have read this plan**, then press **Start the review**. Nothing
   is sent before you tick the box, and any change to the files, roles, privacy or question clears the tick.
   In keyless local mode the Token field is hidden.

**Waiting for a decision** lists runs that stopped to ask you something. Open the run, read the
question, add a reason if you like, and press **Approve** or **Deny**, then confirm in the dialog. Your answer is recorded; the run
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

While a run is running the page reads its progress again every few seconds. It draws the run again only when its state or documents change, never while you are typing a reason, and it never clears an open reviewed document, the log or a recorded decision.

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
| An answer with code 403 in keyless mode | The request may also have been refused because it did not come from this computer (another address, a proxy or a tunnel). |

## 5. What the desk does not do

It does not delete anything or change your review rules. Whether document text is sent to model providers depends on the server's profile, shown at the top of the page (Local or Cloud).
Costs, run reports and every other view (pairs, amendments, replies) are in the full console at `/console`.

## How it was checked

Check 662 of the verification gate starts the server on a test folder with a stand-in for the review
pipeline, presses every control of this page in turn, and checks that each one calls the right server
route and reads or writes the right record, that sealed runs show counts only, and that no token or key
appears on any screen. It does it a second time in keyless local mode with no token at all. Check 681
proves that keyless mode is refused on a non-local address and refuses requests from another computer.
No real review is run by either check.
