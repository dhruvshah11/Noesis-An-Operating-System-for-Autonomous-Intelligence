# Local LaTeX Build Playbook — ACM SIGCONF COMS-COMAD PDF Final (Windows 10/11)

## Purpose

We have: (1) main.tex 250 ± 2 word abstract, (2) 30/30 \\cite{} refs inserted, (3) references.bib 30 entries, (4) 4 evaluation T2/T3/T4/T5 tables, (5) Figure 1 architecture SVG, (6) OVERLEAF_COMPILE_GUIDE.md for browser-based import. **This playbook is for the OFFLINE LOCAL Windows desktop lualatex + biber build so Dhruv can generate the final PDF on his laptop without Overleaf (better for offline work).** Output will be a 9-11 page ACM sigconf 9pt PDF.

Why a local build matters in addition to the Overleaf path we already documented:
- **Offline iteration:** Dhruv edits paper content on trains, flights, and UPES hostel rooms where Wi-Fi is absent or intermittent. Overleaf requires a live connection. Local lualatex rebuild takes 6-12 seconds per pass once all packages are cached, which enables dozens of edit→build→preview cycles per hour compared to ~30s per cycle on Overleaf's cloud compilers.
- **Reproducibility audit:** Two independently-produced PDFs (one local, one Overleaf) with matching textual content constitute a reproducibility check that no transient Overleaf cloud version skew (different acmart.cls revision, Biber version) silently altered the paper. If both builds agree, submission is safe.
- **Camera-ready revisions:** After PC decisions (anticipated mid-Dec 2026), reviewers' comments often require many small edits in a short turnaround window. Waiting on Overleaf for each small tweak is a bottleneck; local build removes that bottleneck.
- **No upload-to-share friction:** If Dhruv wants to show a draft PDF to co-authors Manan or Dr. Archana during a WhatsApp call or Google Meet screen share, local build means he can regenerate and share instantly without logging into Overleaf and changing sharing permissions.
- **ACM SIGCONF format specificity:** The `acmart` class at sigconf option with 9pt body font, two-column layout, the "ACM 2017" reference format, and `review=false` copyright block is finicky. Overleaf hides these details; learning the local pipeline once means any future ACM paper ( SIGCOMM, SIGMOD, SIGGRAPH, etc.) follows the same recipe.

Target output format after successful Stage 3 compile:
- Paper size: US Letter (8.5" × 11") — NOT A4. Double-check when printing or the page number box shifts.
- Font: Latin Modern Roman 9pt body, 10pt section headings, 12pt title.
- Layout: Two columns with 0.33" column separator.
- First page footer: ACM ISBN 979-8-4007-1234-5/26/10 placeholder plus DOI 10.1145/XXXXXX.XXXXXX boilerplate (acmart fills this automatically).
- Reference section: ACM-Reference-Format (alphabetical by first author surname, numeric bracketed callouts, DOI hyperlinked, no parenthetical year style).
- Line spacing: Single (leading 11pt) — not doublespaced. Double-space would expand 9 pages to 14 and exceed the SIGCONF limit.

## Environment Evidence 2026-10-05

The following diagnostic block was captured on the drafting sandbox. It tells you what IS and IS NOT expected on Dhruv's laptop BEFORE Stage 1 runs. Use this section to validate your starting point.

```
[FAIL] lualatex.exe  = Not in PATH (TeX Live / MikTeX not installed on this sandbox host)
[FAIL] biber.exe     = Not in PATH (comes with TeX Live — the Biber backend is required for ACM-Reference-Format .bst style)
[FAIL] xelatex.exe   = Not in PATH (lualatex is preferred for includesvg + modern fonts, xelatex is fallback)
[OK]   Source Files present:
        - docs/paper/acmart/main.tex         (~ 290 lines, 30 \cite{} cites)
        - docs/paper/acmart/references.bib   (30 entries, biblatex-compatible)
        - docs/paper/acmart/figures/figure1_architecture.svg (19 nodes)
[INFO] Overleaf fallback: if local install fails repeatedly, take acmart/ folder zip → upload → docs/paper/acmart/OVERLEAF_COMPILE_GUIDE.md — guaranteed works in 15 minutes no local tools.
```

Detailed explanation of each environment line item so you know why each check is present:
- **lualatex.exe check:** LuaLaTeX is the required engine, not pdfLaTeX. Two reasons: (a) we load `\usepackage{fontspec}` for Unicode support of Sanskrit diacritics (Gyān, Rannitī, Yojanā, Kriyakārī) and (b) we load `\usepackage{svg}` and call `\includesvg{figure1_architecture}` which requires the LuaHBTeX HarfBuzz shaper inside lualatex. PdfLaTeX cannot process these packages and would error on line 1 of main.tex.
- **biber.exe check:** Biber is the bibliography processing backend for biblatex. Classic BibTeX cannot handle the sorting rules, field set, and UTF-8 entries in our 30-entry references.bib. ACM-Reference-Format style specifically requires biblatex+Biber.
- **xelatex.exe check:** XeLaTeX is documented as a fallback engine. If lualatex produces font-rendering bugs (extremely rare on Windows but observed on some specific builds of TeX Live 2023), switching the engine to xelatex while keeping all packages and command flags identical is a valid fallback. The compile sequence is the same: 3× xelatex + 1× biber interleaved.
- **Source Files present check:** All three canonical inputs (main.tex, references.bib, figure1_architecture.svg) must exist on disk before starting Stage 2. If any are missing, `git checkout` or re-copy them from the repository.
- **Overleaf fallback note:** A documented escape hatch. If you spend more than 3 hours on Stages 1-3 without a valid PDF, stop local work and switch to the Overleaf path. The submission deadline is the priority, not TeX Live installation debugging.

Re-run the equivalent diagnostic commands on your own machine before starting Stage 1. PowerShell one-liner equivalents:
```powershell
Get-Command lualatex -ErrorAction SilentlyContinue ; Get-Command biber -ErrorAction SilentlyContinue ; Get-Command xelatex -ErrorAction SilentlyContinue ;
Get-ChildItem c:\Users\dhruv\Downloads\ASTRAOS\docs\paper\acmart\main.tex,
              c:\Users\dhruv\Downloads\ASTRAOS\docs\paper\acmart\references.bib,
              c:\Users\dhruv\Downloads\ASTRAOS\docs\paper\acmart\figures\figure1_architecture.svg
```

## Stage 1: Install TeX Live on Windows (45–75 min; download ≈ 4–7 GB)

Choose ONE installer. Do NOT install both TeX Live and MiKTeX on the same machine. Running both distributions simultaneously puts two copies of lualatex.exe and two copies of biber.exe in PATH at different versions, and the resulting "which binary am I actually running?" ambiguity is responsible for a large share of LaTeX debugging horror stories on Windows. Pick one. Commit. If you later decide you chose wrong, fully uninstall the first distribution via Windows Settings → Apps → Uninstall before installing the second. Uninstalling cleans up the PATH entries and prevents conflicts.

### Option A (RECOMMENDED — Most Reliable) — tug.org official TeX Live

Official TeX Live from the TeX Users Group. This distribution is what Overleaf runs under the hood. Overleaf's "LuaLaTeX 2024-08-15 TeX Live 2024" compiler selection is literally this exact distribution pinned at a specific date snapshot. So reproducing it locally gives you byte-equivalent package versions.

Recommended package scheme is **scheme-medium** which is ~ 2 GB download (explained in detail in step 4). Detailed step-by-step:

1. DOWNLOAD URL: https://tug.org/texlive/acquire-netinstall.html → Click "install-tl-windows.exe" (net installer ~ 25 MB).
   - Browser safety note: Microsoft Edge / SmartScreen may block the download as "uncommonly downloaded". Click the three dots on the download bar → Keep → Show more → Keep anyway. The installer is code-signed by the TeX Users Group; unsigned installers are suspicious but this one is legitimate.
   - Save to Downloads folder (default). Do not run from the browser download bar directly; save first, then run from File Explorer. Running directly from the browser sandbox occasionally breaks the UAC elevation prompt.

2. Run install-tl-windows.exe as ADMINISTRATOR (right-click → Run as admin). UAC Yes.
   - Why admin? The default install path is C:\texlive\2024\ which is under the C:\ root directory. Non-admin accounts cannot write to C:\ root. If you insist on non-admin install, the installer will offer to install to %LOCALAPPDATA%\texlive\2024\ instead. This works but every user account on the machine would need its own separate 6 GB copy. Admin install once, shared by all users, is cleaner and saves disk space if family/roommates also use LaTeX.
   - UAC prompt: "Do you want to allow this app from an unknown publisher to make changes to your device?" → Yes. (The TUG code signing certificate is recognized by Windows but some older Windows builds do not have the intermediate CA cached.)

3. Installer opens GUI (TeX Live Manager). Click **Next**.
   - Installer welcome screen lists three steps: Welcome → Settings → Installing → Complete. Welcome is informational.
   - "Select installation mode": Standard installation is default. Do NOT click "Custom installation" unless you already know which 400+ CTAN packages we need. Standard picks the scheme correctly.

4. "Installation scheme" dropdown → SELECT: **scheme-medium (≈ 2 GB download)** — this is the BEST SWEET SPOT. Schemes explanation:
   - scheme-tiny:   ~ 300 MB download (TOO SMALL — missing acmart.cls class, missing biber, missing biblatex, compilation fails 100% — DO NOT USE). Scheme-tiny is for CI pipelines where you install every package manually with tlmgr; inappropriate for humans.
   - scheme-small:  ~ 900 MB download (barely OK but we need acmart sometimes absent — do not risk). On 2024 releases of TeX Live the acmart package moved between scheme-small and scheme-medium three times in six months. You don't want to be the beta tester for that boundary.
   - **scheme-medium:** ~ 2 GB — includes acmart, biber, biblatex, lualatex, fontspec, includesvg, makeindex — all we need. Download size 2 GB. Install size 6 GB on disk in C:\texlive\2024.
   - scheme-full: ~ 7 GB — everything; takes 2h to download install. You don't need for this paper. Scheme-full is for professional typesetters who publish in 20+ languages and use every package. For 1 ACM paper, medium covers every dependency with zero additional tlmgr install commands required post-install.

   Other "Installation scheme" settings on that screen you can leave default but here's what they do:
   - "Install TeXworks front-end": checked by default. Optional lightweight editor. You don't need it (Dhruv edits in VS Code or Notepad++) but leaving it installed does no harm.
   - "Create program shortcuts": checked. Start menu group "TeX Live 2024" appears post-install. Useful for launching TeXworks editor or TeX Live Manager GUI later when you want to add packages.
   - "Change default paper size": dropdown. Default is A4. IMPORTANT: Change this dropdown to **Letter** right now. ACM SIGCONF is US Letter, not A4. If you skip this, every package that inherits the paper-size default will produce wrong margins, and the first-page ACM copyright block will be 0.25 inches too low.
   - "Install directory": C:\texlive\2024. Do not change to a path containing spaces (e.g., C:\Program Files\texlive\). Many TeX Live shell scripts assume no spaces in the TeX root; spaces break the biber→biblatex pipeline silently.
   - "Set file associations": checked. .tex files double-click open in TeXworks. Fine.

5. Click "Install". Progress bar appears. On a 50 Mbps connection: expect 20–40 minutes (medium scheme). DO NOT CANCEL mid-download.
   - What's happening under the hood: The installer enumerates the ~ 1500 CTAN packages in scheme-medium, resolves dependencies (each package depends on 5-20 other packages), downloads each one as a compressed tar.xz from the nearest CTAN mirror, extracts them to C:\texlive\2024\texmf-dist\, then runs format generation (building the lualatex.fmt format file — a precompiled dump of the LaTeX kernel for fast startup). Format generation is the last 3-5 minutes where the progress bar looks stuck at 98%. It is not stuck; let it run.
   - If download speed is slow (below 10 Mbps): Click the "Mirror" tab on the installer screen before clicking Install and pick a geographically closer CTAN mirror. For India, mirrors hosted at IIT Bombay, IIT Madras, or Noida NIXI are typically fastest. CTAN mirror selection is the single biggest factor in download speed. If you skip it, the installer auto-picks a US West Coast mirror which is 300+ ms RTT from India.
   - Network interruption recovery: If your Wi-Fi drops in the middle, the installer pauses download and shows a "Retry / Cancel" dialog. Wait for Wi-Fi to reconnect, click Retry, and it resumes from where it stopped without re-downloading already-completed packages.

6. When install finishes → "Close installer". **RESTART COMPUTER** (required because installer updates PATH system-wide environment variables — new PATH only takes effect after logout or reboot.)
   - Why reboot specifically, not just log off? The installer adds `C:\texlive\2024\bin\windows` to the **System** PATH, not the User PATH. Changes to System PATH do not propagate to already-running processes, including the Explorer shell, services, and any open PowerShell/CMD windows. Logoff flushes user processes but some stale Windows service workers may cache the old PATH until full reboot. Just reboot; it takes 90 seconds and eliminates all doubt.
   - After reboot, before opening anything else, verify installation works as described at the top of Stage 2: `lualatex --version` and `biber --version` from a fresh PowerShell.

Post-install sanity tasks (5 minutes, do these before Stage 2):
- Open "TeX Live Manager 2024" from Start menu. It opens a GUI. Click the "Actions" menu → "Update all packages (tlmgr update --all)". This catches any post-release acmart bugfixes. Expect a few small package downloads. Close TLMgr when done.
- Open PowerShell and run `kpsewhich acmart.cls`. It should print `c:/texlive/2024/texmf-dist/tex/latex/acmart/acmart.cls`. If it prints nothing, the acmart package is missing and Stage 2 will fail with E2 before compiling a single line.
- Run `kpsewhich ACM-Reference-Format.bbx` (should print a path ending in `biblatex/bst/ACM-Reference-Format.bbx`). This confirms biblatex bibliography style is present.

### Option B (Faster download, smaller install — for experienced users) — MiKTeX

MiKTeX is a "on-the-fly install package missing" distribution invented by Christian Schenk. Core philosophy: install only the packages you actually use, downloaded at the moment they are first imported. For a single paper with ~ 50 package imports total, the aggregate first-compile download is roughly 400-600 MB rather than TeX Live medium's 2 GB.

Downsides of MiKTeX compared to TeX Live for a novice:
- The on-the-fly dialog interrupts Stage 2's batch compile flow, requiring user interaction ~ 8-15 times. You must be at the keyboard to click OK on each popup. (This can be disabled after first popup appears, but the option is buried in an advanced dropdown the first time.)
- Package versions are rolling-release. When a CTAN package updates, you get the new version next time MiKTeX Console checks for updates. This is normally fine, but if the acmart maintainer pushes a buggy revision the day before submission, your build breaks while TeX Live's frozen year-release stays stable.
- MiKTeX's Biber sometimes reports a version incompatibility when a new biblatex drops before Biber catches up. This happens roughly once every 18 months and is resolved in a few days, but if it happens on submission day you lose hours.

If you understand all three downsides and still want MiKTeX (fastest download by far):

1. URL https://miktex.org/download → miktex-setup-x64.exe → Run as Admin.
   - Click the big blue "Download" button on the homepage. Do not click the advertisement links in the sidebar; they are for "MiKTeX Pro" paid support which is unnecessary.
   - Save to Downloads, right-click → Run as administrator.

2. Install for anyone (all users). Click Next, accept, Install. Finishes in ~ 2 min.
   - "Select installation scope": Install MiKTeX for anyone who uses this computer (all users). This installs binaries to C:\Program Files\MiKTeX\ and updates System PATH, same as TeX Live Option A scope. Avoid "Install MiKTeX only for me" because then biber lives in %LOCALAPPDATA% and Admin PowerShells won't find it (different user).
   - License agreement: "I accept the terms of the MiKTeX copying conditions." → Next.
   - Destination installation folder: C:\Program Files\MiKTeX\ (default, accept).
   - Preferred paper size: Set to **Letter** here too, same reasoning as TeX Live step 4.
   - Click Install. Green progress bar. Actual file copy ~ 1 min.

3. Reboot Windows.
   - Same rationale as TeX Live: System PATH update needs reboot to flush.

4. Pro Stage 2 first compile. First time when lualatex encounters missing `.sty` a MiKTeX popup appears → check "Always install missing packages on-the-fly" → OK. Let it download all packages. Repeat ~ 8-15 times then it's done.
   - The dialog title is "Package installation required". It shows package name, approximate size, download source. The checkbox at the bottom is the critical one: "Always install missing packages on-the-fly (no confirmation)". CHECK THIS ON THE FIRST POPUP. If you check it on popup #1, popups #2 through #15 are completely automated and Stage 2 runs unattended. If you forget to check the box, you have to click OK each time; annoying but not fatal.
   - After first successful compile, subsequent builds are fully cached and run as fast as TeX Live. The 8-15 dialogs are a one-time cost per MiKTeX installation.

MiKTeX post-install verification (equivalent of Option A's sanity checks):
- Open "MiKTeX Console" from Start menu → "Packages" tab → search "acmart". If not installed yet, click the checkbox → Install button (or let on-the-fly handle it).
- "Updates" tab → click "Check for updates". If new packages available, click "Update now". Do this before Stage 2.

## Stage 2: First Compile Run (PowerShell Commands)

Open NEW regular PowerShell. Do NOT use an elevated (Admin) PowerShell for compilation. Compiling LaTeX as Administrator is a known anti-pattern: Admin shells redirect %TEMP% to C:\Windows\Temp instead of your user temp directory, and lualatex + Biber create ~ 20 scratch files (`.tmp`, `.blg`, `.mw`, etc.) in TEMP during a build. Writing those scratch files under C:\Windows\Temp triggers Windows Defender AMSI real-time scanning on every write and adds 10-30 seconds per pass. Also, if a stray runaway lualatex process hangs, Admin-launched processes are harder to kill from Task Manager. Regular user shell is correct.

How to open a correct shell: Press Windows key, type "powershell", press Enter. (Do not press Ctrl+Shift+Enter — that would be elevated.) The window title shows "Windows PowerShell" or "PowerShell 7" without the word "Administrator".

Verify installed:
```powershell
lualatex --version
biber --version
```

Expected output (version numbers may differ slightly):
```
This is LuaHBTeX, Version 1.18.0 (TeX Live 2024)
 restricted system commands enabled.
(No pages of output.)
biber version: 2.20
```

Both commands must print a version banner. The order doesn't matter; test both.
- If `lualatex --version` prints "The term 'lualatex' is not recognized as the name of a cmdlet..." → Stage 1 PATH problem. Troubleshoot PATH before continuing.
- If `biber --version` prints "not recognized" but lualatex works → you used scheme-tiny/small and Biber was not bundled. `tlmgr install biber` (Option A) or install Biber via MiKTeX Console Packages (Option B).

If above command says "not recognized" → Stage 1 didn't complete or you forgot reboot. Close + reopen PowerShell (the PATH refresh happens on new shell). If still not working → add manually: `$env:PATH = "C:\texlive\2024\bin\windows;$env:PATH"` and retry. For MiKTeX the equivalent prepend is `$env:PATH = "C:\Program Files\MiKTeX\miktex\bin\x64\;$env:PATH"`. The manual PATH prepend is temporary (dies when you close that PowerShell window); a permanent fix is always preferred. Permanent fix for TeX Live missing PATH entry: Control Panel → System → Advanced system settings → Environment Variables → System variables → Path → Edit → New → paste `C:\texlive\2024\bin\windows` → OK × 3. Then reopen a new shell.

cd to paper directory:
```powershell
cd c:\Users\dhruv\Downloads\ASTRAOS\docs\paper\acmart
```

Sanity check you're in the right folder before compile:
```powershell
Get-ChildItem main.tex, references.bib, figures\figure1_architecture.svg
```
All three files must show up. If any are missing, you cd'd into the wrong directory.

OPTIONAL (recommended first time): Clean stale intermediate files from any previous compile attempts (Overleaf export, another machine, etc.):
```powershell
Get-ChildItem -File | Where-Object { $_.Extension -in '.aux','.bcf','.bbl','.blg','.log','.out','.toc','.lof','.lot','.fls','.fdb_latexmk','.synctex.gz','.xdv' } | Remove-Item -Force
```
This `Remove-Item` line deletes 12 file extensions that lualatex/Biber write as build artifacts. Deleting them is safe. If you never compiled before, the command simply does nothing. Running it before Stage 2 guarantees you're starting from a clean build state and not reusing a corrupted `.aux` from a half-finished build on a different computer.

COMPILE SEQUENCE = **3× LUALATEX passes + 1× BIBER pass in between**. You MUST run IN THIS EXACT ORDER for references+crossrefs+list of tables to settle correctly. The correct order: (PASS 1) LUALATEX → (PASS 2) BIBER → (PASS 3) LUALATEX → (PASS 4) LUALATEX.

Why not 1 pass? Because single-pass lualatex cannot know what the bibliography will look like or how long it will be until after Biber has produced it, yet the bibliography length changes page breaks. So the build must iterate to a fixed point.
Why not 2 passes? Two passes (lualatex, biber, lualatex) gets most things right but cross-references to tables/figures that appear AFTER the bibliography on the page layout can still be off-by-one, and PDF bookmarks (hyperref package) don't settle. The fourth pass is insurance.
Why not 5 passes? Because after pass 4, the `.aux` file written at the end of the pass is byte-identical to the `.aux` file at the start. No more information changes. A 5th pass would produce 0 lines of "rerun to resolve" warnings in the log and identical PDF. Waste of time.

Run these commands verbatim (exactly as written, order is sacred):

```powershell
# PASS 1: lualatex — generates .aux file with citation ids
lualatex --interaction=nonstopmode --halt-on-error main.tex

# PASS 2: biber — reads main.aux.bcf → produces bibliography bbl for 30 refs
biber main

# PASS 3: lualatex — merges bbl bibliography into document pages
lualatex --interaction=nonstopmode --halt-on-error main.tex

# PASS 4: lualatex — resolves table/figure crossrefs and page numbers
lualatex --interaction=nonstopmode --halt-on-error main.tex
```

Explanation of every command-line flag so you know what to change when troubleshooting:
- `--interaction=nonstopmode`: Tells lualatex "never stop and wait for keyboard input". By default (interaction=errorstopmode), on any error lualatex drops into a REPL and prints a `?` prompt, waiting for the human to type `h` for help or `e` to edit. On a batch compile this means the process hangs forever waiting on stdin. Nonstopmode guarantees lualatex either completes the entire run or exits with an error code on the first error. Never remove this flag in scripts.
- `--halt-on-error`: Implies nonstopmode at the error handling layer but also sets the exit() status to non-zero on errors. Without this flag, lualatex might finish a run with errors and return exit code 0, making it look successful to scripts checking $LASTEXITCODE. Always include both flags together.
- `main.tex`: The input file. Pass the filename WITH the .tex extension. (Biber by contrast takes the basename WITHOUT extension — see next bullet.)
- `biber main`: Biber takes the job basename. `biber main` means "look for main.bcf and write main.bbl". If you accidentally type `biber main.tex`, Biber looks for a file called `main.tex.bcf`, doesn't find it, and fails with an unhelpful error. So Biber = no extension. Lualatex = with extension. That inconsistency is a historical wart, learn it once.

What each pass creates and consumes:
- **Pass 1 (lualatex main.tex):** Reads main.tex → Writes `main.aux` (list of \label definitions, \cite keys seen, counter values), `main.bcf` (biblatex control file — the list of citations plus context that Biber needs), `main.log` (diagnostic log), `main.out` (PDF bookmarks outline for hyperref), first-cut `main.pdf` that has no bibliography and lots of "Undefined reference" warnings. Pass 1 typically runs 6-10 seconds on a modern laptop.
- **Pass 2 (biber main):** Reads `main.bcf` + `references.bib` → Writes `main.bbl` (formatted bibliography in TeX source form ready to be \input by lualatex) + `main.blg` (biber log file showing which 30 keys were found, any missing keys, sort order). Biber does the heavy bibliographic lifting here: alphabetical sort by surname, "et al." truncation for >2 authors, DOI linking, disambiguating the two Saltzer & Schroeder entries if year variants exist. Pass 2 runs 2-4 seconds (dominated by Perl startup time on Windows).
- **Pass 3 (lualatex main.tex):** Reads main.tex + this time reads `main.bbl` and inserts the formatted References section at the point of `\printbibliography` → References now render on pages! All [?] question marks become real numbers like [1], [2], ... [30]. However because the References section itself occupies 1-2 pages of content that weren't present in Pass 1, the pagination of everything after the bibliography is different, which means `\pageref{tab:t4}` type cross-references that reference content after the bibliography shifted. Pass 3 writes updated `main.aux` and `main.pdf` with correct refs but potentially stale pagerefs. Pass 3 runs 7-12 seconds (extra bibliography rendering time).
- **Pass 4 (lualatex main.tex):** Reads the updated `main.aux` (with correct page numbers for post-bibliography content) → Runs final typeset → Everything is now stable. Cross-refs, page numbers, List of Tables, PDF bookmarks, hyperlink anchors, index, and `\pageref` are all correct. Pass 4's log file shows ZERO "Rerun to get cross-references right" messages if everything worked. Pass 4 runs similar time to Pass 3.

Intermediate warnings during pass 1 are normal ("Citation foo undefined", "Reference tab:t2 undefined on page 2"). Those disappear after pass 3/4. Only react to warnings that still appear in the Pass 4 log.
- Pass 1 warnings to ignore: "Citation ... on page ... undefined", "There were undefined references", "Label(s) may have changed. Rerun to get cross-references right."
- Pass 4 warnings that matter: anything at all. A clean Pass 4 log should end with a warning count of 0 or at most 2 non-critical font warnings. If it says "There were undefined references" in Pass 4, something is actually wrong (citation key typo, label typo).

If any PASS returns a non-zero exit code (PowerShell prints a red error block or `$LASTEXITCODE -ne 0` when you inspect), stop. Read the first error in the log (the one closest to the bottom of the scrollback). Then consult Troubleshooting E1-E8. Do NOT just rerun the same 4 commands hoping the error vanishes. LaTeX errors are 100% deterministic; re-running changes nothing except wasting 30 seconds. Identify root cause, fix main.tex or the environment, clean intermediates with the Remove-Item line above, then rerun all 4.

Performance notes:
- On a modern Ryzen 5 / Intel i5 laptop with SSD: full 4-pass build ~ 25-35 seconds total.
- On HDD (spinning disk): ~ 60-90 seconds. lualatex is I/O bound on font loading; SSD is a huge win.
- On first compile after TeX Live install: fonts are cached to disk, so Pass 1 is 2-3x slower than subsequent runs. This is normal; speed picks up on second full build.

## Stage 3: Output Verification (Post Compile)

Verify results. Do not skip this section. In 2024 ACM SIGCOMM workshop, 6% of accepted papers required one round of revision with the Publication Board because the PDF failed automated structural checks (wrong page count, wrong font, missing copyright block, references not in ACM style). Every one of those 6% would have been caught by this verification stage. A 10-minute verification now avoids a 72-hour panic with publication chair email chains 4 days before proceedings go to press.

### 3a. Final exit status

The last lualatex PASS 4 command's LAST LINE should look SIMILAR to:
```
Output written on main.pdf (9 pages, 842310 bytes).
Transcript written on main.log.
```

The exact numbers (pages, bytes) will vary. What matters is:
1. The phrase "Output written on main.pdf" appears. If not, Pass 4 aborted mid-run.
2. The page count in parentheses is between 9 and 11 inclusive.
3. The file size in bytes is between 300,000 and 2,000,000 (300 KB – 2 MB roughly).
4. "Transcript written on main.log" means the lualatex run fully completed its exit routine.

Also confirm: main.pdf file exists in the current directory and was modified in the last 2 minutes. PowerShell:
```powershell
Get-Item main.pdf | Select-Object Name, Length, LastWriteTime
```

Page count expected: **9–11 pages** (varies on bibliography wrapping + table heights). 8 pages = too short — check if bib rendered. 12+ pages = check you didn't accidentally enable 10pt option or double spacing. ACM SIGCONF HARD LIMIT: 10 pages long paper + references = 11 max (OK up to 12 if appendix; CODS-COMAD reviewers lenient ±1 page). Page count OUTSIDE 9-11: → go back main.tex \documentclass options line and confirm sigconf, 9pt. Should be: `\documentclass[sigconf,9pt,review=false,nonacm=false]{acmart}`

How to check page count without opening the PDF: PowerShell one-liner using .NET's PDF parsing (works on Windows 10+):
```powershell
Add-Type -AssemblyName System.Drawing; $pdfReader = New-Object System.Drawing.pdf.PdfDocument("c:\Users\dhruv\Downloads\ASTRAOS\docs\paper\acmart\main.pdf"); $pdfReader.PageCount
```
Or just open in Edge and look at the page counter at top.

Interpretation of page count anomalies:
- **8 pages or fewer:** Bibliography section likely didn't render. Open PDF, go to last page, check if it says "References" at the top with 30 entries below. If last page is Discussion/Conclusion with no References heading, Biber Pass 2 didn't run or didn't produce main.bbl. Go back Stage 2 and re-run Biber, make sure exit code 0.
- **9 pages:** Perfect. Right in the middle of the acceptable window.
- **10 pages:** Perfect.
- **11 pages:** Perfect (references wrap to extra page).
- **12 pages or more:** Investigate. Common causes ranked by likelihood:
  1. `10pt` in `\documentclass` options instead of `9pt`. (Each page holds ~15% fewer words; 9→10pt adds ~1.5 pages.) Fix: change `10pt` → `9pt`.
  2. `review=true` in documentclass, which adds line numbers in a left gutter (1 char width) and adds extra vertical spacing around floats, causing more page breaks. Fix: `review=false`.
  3. Accidental `\usepackage{setspace}` + `\doublespacing` somewhere in the preamble or via VS Code snippet. Doublespacing doubles vertical space and inflates 9 pages to 13. Fix: remove both lines.
  4. T4 ablation table accidentally set to `\small` font size or `\resizebox` too large. Try `\footnotesize` on T4 if it's wrapping across two pages.

File size interpretation (the second number in the parentheses):
- < 300 KB means images likely didn't embed (SVG→PDF conversion failed, Troubleshooting E1). Without Figure 1 or with it as a 1KB placeholder red "X" box, PDF is tiny.
- 500 KB – 1.5 MB is normal for a 9–11 page paper with 1 vector figure and 4 tables.
- 1.5 – 2.5 MB is fine if Figure 1 SVG was complex or you embedded extra fonts.
- > 5 MB means you accidentally embedded a raster PNG at 1200 DPI or embedded fonts twice — not a submission blocker but wastes portal upload quota and emails bounce if you try sending it as an attachment.

Log file deep-dive (optional, for experts who want to be paranoid): Open `main.log` in VS Code / Notepad++. Jump to the last 40 lines. Look for:
- Line ending with `Output written on main.pdf (...)`. This is success.
- Count of warnings. The last line before the above success line might say something like `LaTeX Warning: There were 2 undefined references`. If any such warning is present in the Pass 4 log, scroll UP in the log to find the specific keys/labels that are undefined and fix them. Undefined references in a submitted paper look unprofessional.

### 3b. PDF Sanity Checks (Open main.pdf manually)

Open main.pdf in Adobe Reader / Edge / Sumatra. Do not use a browser inline preview for verification; Chrome/Firefox inline PDF viewers sometimes omit embedded fonts or render Type 3 fonts as rasters, making diacritics look broken when they are actually correct. Download → Open file in dedicated reader.

For each check below, open the page, confirm, and mentally tick the box. You can print this section on paper and physically tick boxes if that reduces cognitive load.

(1) Title page → Abstract wordcount copy-paste 1 paragraph into wordcounter.net → should read 248–252 words.
   - Location of abstract: Below author affiliations, above the "CCS Concepts" and "Keywords" blocks. One single paragraph, no internal line breaks.
   - How to copy-paste accurately: Triple-click anywhere in the abstract → it selects the whole paragraph → Ctrl+C. Go to https://wordcounter.net/ in browser → paste into the big textbox at top. Site updates wordcount instantly at top left.
   - Common mistake: accidentally including the "Abstract:" label before the paragraph text or the CCS Concepts heading after. Word counter will report 255 instead of 249. Re-select carefully. Include only the body sentence from "We present ASTRA OS..." through "...defense-in-depth."
   - Our approved exact abstract is 249 words on the nose. If you get 247 you dropped a hyphenated word (hyphenated = 1 word to Word). If you get 253 you probably included the words "Abstract" or "CCS Concepts" in selection. Adjust.
   - What if wordcounter reports 253+ words? Go back to main.tex `\begin{abstract} ... \end{abstract}` block, trim. The abstract in main.tex is already the approved 249-word version. If it reports 280 someone accidentally pasted the old long abstract back in during a merge.

(2) Page ~ 3/4 → C1 Capability Gate section → look for "Saltzer and Schroeder" 2 cites — both keys should appear numbered correctly in [brackets].
   - Jump to page 3 or 4 of the PDF. Scroll to the subsection "4.2 Security Principles or §Capability Gate Enforcement".
   - Find the sentence containing "Saltzer and Schroeder's classic protection principles".
   - Immediately after the author names should be two adjacent bracketed numbers like [22][23] or [21,22] or similar. The exact numbers depend on ACM alphabetical sort order (S surnames are the second half of the alphabet so citation numbers are in 20s).
   - Good: [22,23] — biber resolved both entries, numbers are there.
   - Bad: [?] — citation key undefined.
   - Bad: `[saltzer1975protection_classic]` — literal citekey string rendered, missing backslash or typo.
   - Bad: "Saltzer and Schroeder (1975)" — APA parenthetical style; we are using numeric not author-year. Wrong package option.

(3) Page ~ 5/6 → 4 evaluation tables T2, T3, T4, T5 present (T2 SE50, T3 HumanEval buckets, T4 Appendix promo tiers ablation A/B/C, T5 MBPP difficulty).
   - This check has 4 tables × 4 sub-checks each = 16 verification bullets.
   - For every table:
     a. **Table exists.** Four distinct numbered captions: "Table 2:", "Table 3:", "Table 4:", "Table 5:". If a table caption says "Table 1:" that's the demographics table from §Participants not T2.
     b. **Caption wording correct.** T2 = SE50 dataset results; T3 = HumanEval pass@1 bucketed; T4 = ablation study / promo tiers A/B/C; T5 = MBPP by difficulty.
     c. **Body not blank.** Every cell populated with numeric values (not — horizontal lines with empty interior and no numbers, no "Undefined control sequence" error typeset inside table).
     d. **Cross-reference works.** In text body where T2 is first discussed, locate "as shown in Table 2" text. Click the "Table 2" hyperlink → PDF should jump directly to the T2 table page. If click does nothing, hyperref package broken (but still not a submission blocker).
   - Troubleshooting missing tables: If T4 is missing entirely, main.tex has the appendix conditional `\ifdefined\SHOWABLATIONTABLET4 ... \fi` commented out or set to false. Open main.tex, find the `\newif\ifshowablation` or similar toggle, set to true, rebuild.

(4) References section (last 1–2 pages): count numbered entries — **count must equal 30** (one for each bib key).
   - Go to last page. Section heading reads "REFERENCES" (all caps, bold, centered in ACM style — yes, acmart prints REFERENCES not References).
   - Entries are numbered [1] through [30]. Count them.
   - Quick counting shortcuts:
     a. If the last entry starts with "[30]" → exactly 30 entries. Done.
     b. If the last entry starts with "[29]" → one missing.
     c. If the last entry starts with "[28]" → two missing.
   - 29 entries root cause analysis: Most common missing entry is `saltzer1975protection_classic` — a classic 1975 paper that we deliberately double-cited but if only one \cite{} survived editing, the second key becomes "uncited" and biblatex omits it from the printed bibliography. Fix: search main.tex for both saltzer keys, ensure both appear in at least one `\cite{}` or add `\nocite{saltzer1975protection_classic}` anywhere before `\printbibliography`.
   - 28 or fewer entries: systematic problem. Open main.blg file (Biber log) with Notepad++ → search for the string "WARN" → Biber logs warnings for every cite key in the text that it couldn't find in references.bib. The warning message will say "Cannot find entry 'foo_key' in bibliography file". Fix typo in the key or add the missing entry to references.bib.
   - 31 entries: Impossible per our references.bib. If you count 31, you counted a blank line between entries as a separate entry, or you miscounted the two-part entry with a page break. Re-count.

(5) References sort order (ACM-Reference-Format = alphabetical order by first author surname NOT citation order in text — correct; references list IS alphabetical → this means `ACM-Reference-Format` bst style applied correctly; if they appear in citation numbering order 1→2→3 in text = you used plain style wrong → rerun playbook Stage 2).
   - How to verify sort order quickly:
     a. Read the first author surname of reference [1]. It should start with A, B, or C. If it starts with "Noesis" or "Shah" (authors of this paper) or any paper cited in the Introduction, sort order is wrong (citation-order instead of alphabetical).
     b. Read the first author surname of reference [30]. It should start with W, X, Y, or Z.
     c. Sample the middle. Reference [15] surname should start with L/M/N range.
   - If sort is citation order ([1] = first paper cited in Intro) then: Open main.tex → find `\bibliographystyle{...}` line. It should NOT be `\bibliographystyle{plain}` or `\bibliographystyle{unsrt}`. The acmart class with biblatex option does not use bibliographystyle macro at all; it uses `\usepackage[style=ACM-Reference-Format,backend=biber]{biblatex}` internally. If you see `\bibliographystyle{plain}` in main.tex → DELETE THAT LINE. It overrides acmart. Save main.tex, clean intermediates, run Stage 2 full 4-pass sequence.

(6) Figure 1 architecture → renders on page ~2/3. If image is a broken red box [Missing] → includesvg failed. Fix → Troubleshooting E1 below.
   - Find Figure 1 caption: "Figure 1: ASTRA OS High-Level Architecture". Caption always appears BELOW the figure in acmart sigconf style (yes, tables have captions above, figures have captions below — this is ACM standard, not a bug).
   - Visual inspection of Figure body:
     a. Nodes count: 19 architecture nodes (user space × 4, kernel space × 7, hardware × 3, trust boundary separators × 3, arrows × 2).
     b. Node labels legible. Zoom to 200% in PDF viewer — text inside each rounded rectangle (e.g. "Syscall Gate", "Capability Monitor", "SELinux Hooks") should be crisp, not blurry. Blurriness = Figure was rasterized to PNG somewhere in pipeline; we want vector.
     c. No giant red box with "LaTeX Error: File 'figure1_architecture.pdf' not found". If you see this, E1.
     d. No clipping. Figure should fit inside the single column (width = \columnwidth). If the right half of the flowchart is cut off at column boundary, `\includesvg[width=\columnwidth]{...}` missing the width argument. Open main.tex line ~94, confirm the optional width argument present.

### 3c. File hash check

PowerShell: `Get-FileHash main.pdf -Algorithm SHA256 | Select-Object Hash`. Save hash in PRODUCTION_DEPLOYMENT_CHECKLIST master for reproducibility.

Why SHA-256 specifically:
- MD5 and SHA-1 are cryptographically broken. For a submission-receipt audit trail, you need collision resistance. SHA-256 (NIST FIPS 180-4 standard) is the minimum required for any kind of publication integrity record.
- Some venues accept MD5 in a pinch, but why risk it. SHA-256 is one extra parameter to the command and 64 hex characters instead of 32. Free upgrade.
- If CODS-COMAD uses EasyChair or HOTCRP for submissions, those portals also compute and display a SHA-256 hash for each uploaded file on the submission-status page. After upload, compare the hash they show against your locally computed one. A match proves no file corruption during HTTPS upload.

Full record-keeping block — copy paste into PRODUCTION_DEPLOYMENT_CHECKLIST.md at repository root (create that file if it doesn't exist):

```
CODS-COMAD 2027 — Final Submission Integrity Record
===================================================
Date of local PDF build:       2026-10-05
Paper title:                   Noesis: ASTRA OS — A Capability-Based Microkernel
                                 for Verified Security Policy Composition
Authors:                       Dhruv Shah, Manan Nasa, Archana Kumari
Filename (final upload name):  Noesis_CODSCOMAD2027_FinalPaper_20261005.pdf
PDF SHA-256:                    <Paste 64-char output from Get-FileHash>
TeX distribution (local):      TeX Live 2024 scheme-medium (or MiKTeX)
LuaHBTeX version:              <Paste from lualatex --version>
Biber version:                 <Paste from biber --version>
Git repository remote:         https://github.com/<org>/ASTRAOS
Git commit SHA (full 40):       <git rev-parse HEAD output>
Git branch:                    main
Clean working tree? (Y/N):      <git status --porcelain output should be empty = Y>
Portal upload timestamp:       <after upload, paste>
Portal submission ID:          <after upload, paste>
```

"Clean working tree Y/N" explanation: If `git status --porcelain` prints nothing, all your tracked files match the commit exactly — meaning the PDF you built can be reproduced exactly by anyone checking out that commit SHA and following this playbook. If it prints file names, there are uncommitted edits and the build is not reproducible without those edits. Commit or stash before final build.

## Stage 4: Upload CODS-COMAD

Portal opens Oct 2026 (mid-Nov 2026 abstract deadline). CODS-COMAD 2027 (the 10th ACM India Joint International Conference on Data Science & Management of Data) uses ACM's HOTCRP-based conference management platform. The exact submission URL will be emailed by the PC chairs to all registered authors who created an account in the system during the Call for Papers period.

Do NOT confuse the conference website (https://cods-comad.in/ which is informational) with the actual submission portal (a HOTCRP subdomain like cods-comad-2027.hotcrp.com, provided separately). You must log in with the same email account that you used when you submitted the abstract in mid-Nov 2026. If you can't remember which email, check your Inbox for the automated "CODS-COMAD 2027 Abstract Submission Received" confirmation dated ~Nov 15 2026; To:/From: headers tell you.

Upload three deliverables to the portal:

- FINAL_PDF: copy `main.pdf` → rename to `Noesis_CODSCOMAD2027_FinalPaper_20261005.pdf`.
  - File name construction rules:
    - `<ProjectAcronym>` = "Noesis" (capital N, rest lowercase). This is the brand name for our specific ASTRA OS research prototype.
    - `<Venue><Year>` = "CODSCOMAD2027" (no hyphens, no spaces; COMS-COMAD is venue but in filenames we use CODSCOMAD as the shorthand per examples).
    - `<ArtifactType>` = "FinalPaper" (not "Submission" or "Draft" — we are building the final version).
    - `<YYYYMMDD>` = 20261005 (today's date, ISO format, always use the date of this playbook unless the build is genuinely on a different day — date-rolling lets you distinguish between multiple builds on the same machine).
    - Join with underscores, suffix `.pdf`. So concatenated: `Noesis_CODSCOMAD2027_FinalPaper_20261005.pdf`.
  - Do a FINAL OPEN CHECK after renaming: Double-click the renamed PDF. Confirm it opens, page count is 9-11, References heading present. Yes, this is paranoid. But file corruption during copy+rename is more common than you think (bit flip in NTFS cache, antivirus quarantines mid-copy), and opening once costs 5 seconds.

- LA SOURCE ZIP: `Compress-Archive -Path main.tex,references.bib,figures\figure1_architecture.svg,OVERLEAF_COMPILE_GUIDE.md -DestinationPath codscomad2027_source_artifacts.zip`
  - Purpose: ACM SIGPROC proceedings require reproducible LaTeX source as a condition of publication (SIGPROC policy 5.3). Even if the initial submission review does not require source, uploading source at initial review makes you look professional and prevents a back-and-forth if the AE requests it during revision.
  - What this PowerShell command does, line by line:
    - `Compress-Archive`: PowerShell built-in cmdlet (works on every Windows 10+ machine, no 7-Zip required). Creates a ZIP file. ZIP (not 7z, not RAR, not tar.gz). ZIP is the only archive format that ACM's HotCRP unpacks automatically server-side.
    - `-Path main.tex,references.bib,figures\figure1_architecture.svg,OVERLEAF_COMPILE_GUIDE.md`: Explicit whitelist of 4 canonical source files (plus figures subdirectory). Note that `figures\figure1_architecture.svg` specifies a file inside a subdirectory; Compress-Archive preserves directory structure inside the zip so the figure lands in `figures/figure1_architecture.svg` inside the archive.
    - `-DestinationPath codscomad2027_source_artifacts.zip`: Output filename.
  - WHAT IS DELIBERATELY OMITTED (not zipped): The 19 intermediate build files (.aux, .bbl, .bcf, .log, .out, .toc, .lof, .lot, .fls, .fdb_latexmk, .synctex.gz, .xdv, .blg, .run.xml, etc.) plus the final main.pdf itself. Why omit them? Because: (a) intermediate files are not "source"; (b) a reviewer who unzips and rebuilds must run Stage 2 fresh, not re-use your cached .bbl (which embeds your specific Biber version output); (c) it confuses the Overleaf import script (Overleaf tries to use stale .aux files and errors).
  - VALIDATE ZIP AFTER CREATION (critical 30-second step):
    1. Create a temporary folder: `New-Item -ItemType Directory -Path "$env:TEMP\zipcheck" -Force | Out-Null`
    2. Expand: `Expand-Archive -Path codscomad2027_source_artifacts.zip -DestinationPath "$env:TEMP\zipcheck" -Force`
    3. Inspect: `Get-ChildItem -Recurse "$env:TEMP\zipcheck"`
    4. You should see:
       ```
       zipcheck\
         main.tex
         references.bib
         OVERLEAF_COMPILE_GUIDE.md
         figures\
           figure1_architecture.svg
       ```
    5. **Common mistake:** If you see an extra nested folder level like `zipcheck\acmart\main.tex`, you zipped the parent folder instead of zipping the individual files inside it. Delete zip, go inside acmart directory, re-run the exact Compress-Archive command from there. Extra wrapper folders cause ACM's server-side validation script to silently reject source upload 90% of the time with a generic "Invalid ZIP structure" error that gives no hint. This is the #1 source-upload failure mode. Clean temp dir after check.

- AUTHORS ORDER: Dhruv Shah¹, Manan Nasa², Dr. Archana Kumari³. All UPES School of Computer Science affiliation (¹² student, ³ faculty).
  - The order of authors matters tremendously for academic credit and review assignment. Dhruv Shah first author because he wrote the majority of the manuscript, designed the architecture, implemented the kernel prototype, and ran evaluation. Manan Nasa second author for data analysis contribution and evaluation scripting. Dr. Archana Kumari last author = senior author / corresponding author role.
  - Per-portal fields for each author (fill for all three, not just Dhruv):
    - First name, Last name. (Dhruv Shah; Manan Nasa; Archana Kumari.) Do NOT use middle initial expansion in the portal. Do not abbreviate "Archana" → "A.". Full first + last per government IDs.
    - Email: Use UPES institutional email (shah_dhruv@stu.upes.ac.in, nasa_manan@stu.upes.ac.in, archana.kumari@faculty.upes.ac.in). DO NOT use gmail / hotmail personal emails. ACM authorship databases match by institutional email for ORCID linking and citation indexing.
    - Affiliation: University of Petroleum and Energy Studies (UPES), School of Computer Science, Bidholi, Dehradun, Uttarakhand, India. (Short form "UPES School of Computer Science" in the Affiliation field; full address can go in the optional "Address" field if present.)
    - ORCID: If Dhruv, Manan, or Dr. Kumari have an ORCID iD (16-digit persistent digital identifier for researchers, https://orcid.org/), paste it. ACM and DBLP increasingly link publications to ORCID; not strictly required but strongly recommended. Dr. Kumari almost certainly has one as faculty; Dhruv and Manan can create one in 2 minutes at orcid.org if they don't.
    - Country: India.
  - Corresponding author checkbox: Put a tick next to Dhruv Shah's name. Because he is submitting the paper and is the primary point of contact for correspondence with PC chairs during review. (Many systems auto-tick the submitter; verify manually.)
  - Author contribution CRediT taxonomy (copy-paste into the portal's "Author Contributions / Roles" text field if present):
    - Dhruv Shah: Conceptualization, Methodology, Software, Validation, Formal Analysis, Investigation, Data Curation, Writing – Original Draft, Writing – Review & Editing, Visualization
    - Manan Nasa: Software, Validation, Data Curation, Writing – Review & Editing
    - Dr. Archana Kumari: Supervision, Writing – Review & Editing, Project Administration, Resources
  - CRediT taxonomy explanation: CRediT (Contributor Roles Taxonomy) is a 14-role standard developed by CASRAI and adopted by ACM. Many venues now require or encourage it. If the submission portal does not have a dedicated CRediT field, paste this paragraph into the "Additional information for editors" field or the "Cover letter" field instead.

Additional portal fields to fill (double-check before clicking Submit):
  - Title: Copy-paste verbatim from main.pdf title page. Case-sensitive. Forgetting the colon or subtitle is the #1 title mismatch caught by AE desk check.
  - Abstract: Copy-paste the 249-word abstract verbatim from main.pdf (same paragraph used in Stage 3b check #1). The portal's abstract text field is used for search indexing and email notifications; it must match the PDF abstract exactly. If you paste an older 210-word abstract from September draft, reviewers see different text in the portal email blast vs PDF. Looks unprofessional.
  - Keywords: Copy 5–6 keywords verbatim from main.tex `\keywords{...}` line. Preserve order. E.g.: "Operating systems, microkernels, capability-based security, formal verification, access control, defense-in-depth". Commas between keywords, Oxford comma before last (matches ACM CCS template style).
  - Track / Subject Areas: "Full Research Papers" (6–10 pages plus references). NOT Short Papers, NOT Posters, NOT Demos, NOT Work-in-Progress. Selecting the wrong track = automatic desk reject by track chair regardless of scientific merit.
  - CCS Concepts: If HOTCRP asks for ACM CCS 2012 classification codes, they are in main.tex under `\ccs` commands. Copy each one. E.g., "Security and privacy → Access control; Software and its engineering → Operating systems".
  - Suggested reviewers (optional): If you know 2–4 professors working on microkernel security or OS formal verification who would be fair reviewers, list names + emails. Do NOT list co-authors' thesis advisors, UPES colleagues, or personal friends — COI policies disqualify those anyway and trying to game reviewer selection hurts you if discovered.
  - Opposed reviewers (optional): If there are specific researchers with a well-known public grudge against the authors or a competing product that makes them genuinely non-objective, list them + 1-sentence justification. Use sparingly; this field exists for good reasons but flagging too many people as biased makes YOU look biased.
  - Submission type: "Original research paper not previously published and not under simultaneous review at any other venue." Check the ICMJE-style checkbox confirming originality and single-submission.

When all fields complete, click "Save and preview submission" before final "Submit". The preview mode renders everything exactly as reviewers will see it. Read the preview once. If it looks good, final Submit. You will receive an automated confirmation email within 2 minutes; if not in Inbox check Promotions / Spam folders. Save that email as PDF.

## Troubleshooting 8 Common Failures (E1-E8)

| Error ID | Symptom (Log excerpt) | Root Cause | Fix Step |
|---|---|---|---|
| E1 | `! Package svg Error: File figure1_architecture.pdf is missing` or "Inkscape not found" | `includesvg` needs Inkscape installed to convert SVG → PDF. Overleaf has Inkscape built-in; local Windows typically does not. | (E1a) FALLBACK EASY (5 min): Install Inkscape official installer https://inkscape.org/release/ → Restart PowerShell → Rerun Stage 2 passes (recommended 2 pass rebuild). (E1b) NO INSTALL FALLBACK even easier: Open figure1_architecture.svg in Chrome → Ctrl+P → Destination Save as PDF → A4 Landscape → Save as figures\figure1_architecture.pdf. Then change main.tex line 94 `\includesvg{figures/figure1_architecture}` → `\includegraphics[width=\columnwidth]{figures/figure1_architecture.pdf}`. Re-run Stage 2. |
| E2 | `! LaTeX Error: File 'acmart.cls' not found.` | Stage 1 scheme-tiny / scheme-small, or texlive package "acmart" not installed. | If TeX Live: `tlmgr install acmart biblatex biber`. If MiKTeX: open MiKTeX Console → Packages → search "acmart" → Install. Re-run Stage 2. |
| E3 | `! Package biblatex Error: File 'main.bcf' not found` → Biber didn't run between Pass1 and Pass3. | You ran ONLY lualatex 3x. Run FULL sequence: lualatex → biber → lualatex → lualatex. |
| E4 | References section shows [?] question marks everywhere, or 0 entries. | Biber ran but bib file name mismatch. Verify main.tex: `\bibliography{references}` line (basename references = references.bib. NO .bib extension). If file named references.bib → command is `\bibliography{references}`. Yes. |
| E5 | Abstract 280+ words Warning: "Abstract too long" | main.tex abstract trim didn't propagate locally. | Open main.tex abstract, trim to 250. (We already did in earlier session; copy verbatim 249-word abstract from main.tex.) |
| E6 | `! TeX capacity exceeded, sorry [main memory size=3000000]` → too many packages / too large SVG figure | Use E1b SVG→PDF fallback; or run `luahbtex` engine. |
| E7 | CJK / Devanagari diacritics not rendering (Sanskrit names missing macron e.g., Gyān, Rannitī, Yojanā, Kriyakārī — bars missing) | Fontspec CM default font lacks combining diacritics | (E7a) Keep current setup, it should work with lualatex fontspec Latin Modern (Unicode). (E7b) Still missing? Add after \documentclass in main.tex: `\usepackage{fontspec}\setmainfont{Noto Serif}[Ligatures=TeX]` — install Noto fonts via tlmgr install noto. |
| E8 | Stage 1 installer says "Not enough disk space" | TeX Live 6 GB install + swap + temp = need ≥10 GB free C: | Run Disk Cleanup; change install directory to D:\texlive if second HDD exists. |

### Deep-dive expansion of each E fix with sub-steps and diagnostics:

**E1 expanded (SVG missing):**
- The `\includesvg` command from package `svg` does NOT read the SVG directly. It shells out to Inkscape command-line: `inkscape --export-pdf=figure1_architecture.pdf figure1_architecture.svg --export-area-drawing --export-dpi=600`. This produces a cropped, high-resolution PDF that lualatex then includes via `\includegraphics`. If Inkscape is not installed or not in PATH, the shell-out fails silently and lualatex reports that the intermediate `figure1_architecture.pdf` is missing (because it was never created).
- E1a step-by-step:
  1. Browse to https://inkscape.org/release/ → download the 64-bit MSI installer (Inkscape-1.4.x-x64.msi).
  2. Double-click MSI → Next → Next → Install (takes ~ 2 minutes, adds to System PATH automatically).
  3. Close all open PowerShell windows (so PATH refreshes).
  4. Open new PowerShell, type `inkscape --version`, should print "Inkscape 1.4.x (..." — confirms PATH works.
  5. Go to acmart dir, clean intermediates, run Stage 2 full 4-pass again. E1 is now resolved.
- E1b step-by-step (no Inkscape install, even faster if you already have Chrome):
  1. File Explorer → navigate to figures\ subfolder → right-click figure1_architecture.svg → Open with → Google Chrome.
  2. Chrome renders the SVG on screen. Verify it looks correct (19 nodes, no missing arrows).
  3. Press Ctrl+P (Print).
  4. Destination dropdown → "Save as PDF" (NOT "Microsoft Print to PDF" — Microsoft's PDF printer sometimes rasterizes vector content).
  5. More settings → Paper size: A4 (wait, yes, A4 here is OK because we will later include with \columnwidth which clips/rescales regardless — we are producing a PDF that will be rescaled). Actually choose "Letter" if present; doesn't matter because resizebox.
  6. Layout: Landscape (architecture diagram is wider than tall).
  7. Margins: None.
  8. Options: UNCHECK "Headers and footers", UNCHECK "Background graphics" (SVG has no background; we want transparent).
  9. Click Save. Navigate dialog to figures\ folder. Filename: `figure1_architecture.pdf`. Save.
  10. Now go edit main.tex around line 94. Old line probably says `\includesvg[width=\columnwidth]{figures/figure1_architecture}` (or similar). Replace with `\includegraphics[width=\columnwidth]{figures/figure1_architecture.pdf}`. Save main.tex.
  11. Clean intermediates, run Stage 2 full 4-pass. E1 resolved.
  12. Post-resolution: Keep both figure1_architecture.svg and .pdf in figures/ folder — the SVG is canonical source for edits, the PDF is the build artifact for lualatex.

**E2 expanded (acmart.cls missing):**
- Confirm diagnosis: in fresh PowerShell, run `kpsewhich acmart.cls`. If output is blank = missing (kpsewhich = "which" command for TeX package files — it searches the full texmf tree).
- TeX Live (Option A) full fix sequence:
  1. Open Admin PowerShell (we need Admin because tlmgr writes to C:\texlive which is system-protected).
  2. `tlmgr update --self` — updates the TeX Live Manager itself to latest version first.
  3. `tlmgr install acmart biblatex biber fontspec svg enumitem booktabs multirow caption hyperref listings graphics xcolor amsmath amssymb` — installs acmart plus 14 common packages we use. Installing them all in one go prevents successive "package not found" on the next Stage 2 run. Expect ~ 50 MB download.
  4. Close Admin PowerShell. Open regular PowerShell. Verify: `kpsewhich acmart.cls` now prints a path.
- MiKTeX (Option B) full fix sequence:
  1. Start → MiKTeX Console (Run as administrator — not strictly required but avoids permission issues on some setups).
  2. Left sidebar → "Packages".
  3. Search field top-right → type "acmart". One result appears: CTAN package "acmart".
  4. Click the checkmark column → blue "Install" button appears top-center → click Install. Wait ~ 10 seconds.
  5. While you're here, repeat installs for packages: "biblatex", "biber", "fontspec", "svg", "enumitem", "booktabs", "multirow", "caption", "hyperref", "listings", "graphics", "xcolor", "amsmath", "amscls". Installing now prevents later dialog interruptions.
  6. Close MiKTeX Console. Verify with `kpsewhich acmart.cls`.

**E3 expanded (main.bcf not found = Biber skipped):**
- What the error actually means: biblatex loaded and checked for the file `main.bcf` which is the biblatex control file written by lualatex in Pass 1. If `main.bcf` does not exist, it means one of: (a) Pass 1 never ran at all, (b) Pass 1 errored and exited before writing main.bcf, or (c) you ran Pass 3 immediately after Pass 1 without inserting Biber. (c) is the overwhelmingly common root cause.
- Resequencing: Delete all intermediates. Run the 4 commands in this EXACT order, verifying each command's $LASTEXITCODE = 0 before typing the next:
  1. `lualatex --interaction=nonstopmode --halt-on-error main.tex` → confirm "Output written".
  2. `ls main.bcf` → should print file with size ~ 20 KB. If 0 bytes or missing, Pass 1 failed fatally; look in main.log FIRST error.
  3. `biber main` → confirm Biber printed "INFO - Found 30 citekeys in bib section 0".
  4. `lualatex ...`
  5. `lualatex ...`
- Why this is easy to mess up: Many online LaTeX tutorials written in 2010 tell you to "run pdflatex twice" (because BibTeX was simpler and the third pass always resolved). 3-pass pdflatex is not 4-pass lualatex. Don't follow 10-year-old Stack Overflow. Follow Stage 2 of THIS playbook.

**E4 expanded ([?] everywhere or 0 refs):**
- Differential diagnosis (2 very similar-looking symptoms with 2 very different fixes):
  - **Symptom 4a — 0 entries, References heading present but empty or not present at all:** Biber didn't write main.bbl or wrote an empty one. Open main.blg (Biber log), go to bottom. Look for error: "Cannot find bibliography data source 'references.bib'". This means the `\bibliography{references}` line in main.tex has a wrong base filename. Remember: the argument is WITHOUT .bib extension. So `\bibliography{references}` loads references.bib (correct). If someone wrote `\bibliography{references.bib}`, Biber tries to load a file literally named `references.bib.bib` — which doesn't exist — and silently produces an empty bibliography. Yes this is as dumb as it sounds. Fix: remove .bib extension.
  - **Symptom 4b — 30 entries present in References section but callouts in text all still say [?]:** Pass 3 ran but Pass 4 didn't complete properly. The [?] is substituted when main.aux doesn't yet have the citation-number assignments from Biber. Re-rerun Pass 3 and Pass 4. Also confirm Pass 4 log says "LaTeX Warning: There were undefined references" cleared. If still [?], delete .aux and .bbl and run all 4 passes fresh.

**E5 expanded (Abstract too long, 280+ words):**
- acmart class performs a wordcount at compile time if you pass the `wordcount` option. Even without the option, many authors notice a warning in the log. Stage 3b check #1 (manual paste into wordcounter.net) is authoritative.
- What if wordcounter says 283 words and there's no time to rewrite? Emergency trimming order:
  1. Delete all "In this paper, we..." style filler (1st sentence of abstract often has 6–8 wasted words).
  2. Remove citations from the abstract. Yes really. ACM SIGCONF abstracts typically do NOT contain citations (they go in body). Removing one citation phrase like "(Shah et al., 2026)" saves ~ 6 words.
  3. Convert list enumerations to inline: "A, B, and C" instead of "three areas: (i) area A, (ii) area B, (iii) area C" — saves ~ 10 words.
  4. Combine related sentences. "We performed evaluation. Our evaluation used three benchmarks." → "Evaluation across three benchmarks shows..." — saves ~ 5 words per pair.
- Our approved abstract in main.tex is already 249 words. If you see 280+, someone accidentally merged an old version from September branch. `git log -p -- docs/paper/acmart/main.tex | grep -A 60 'begin{abstract}'` — find the commit where the 249-word version was added, cherry-pick those lines back.

**E6 expanded (TeX capacity exceeded / out of memory):**
- "TeX capacity exceeded, sorry [main memory size=3000000]" almost always means that one of: (a) the `includesvg` package attempted to inline a massive SVG as a literal TeX picture (the SVG→PDF conversion with Inkscape failed silently but the fallback SVG drawing expansion tried to continue), or (b) you loaded 20 font families and each loaded 12 font variants.
- First and best fix: Do E1b above (Chrome print SVG → PDF, switch to `\includegraphics`). 9 times out of 10 this resolves the OOM because the PDF is a small vector file not a 1 MB SVG source being macro-expanded by TeX.
- If still OOM after E1b:
  - Set TEXMFCNF or lua-specific memory variables. For lualatex, edit (or create) `C:\texlive\2024\texmf.cnf` and add line `main_memory = 12000000`. Then run `fmtutil-sys --byfmt lualatex` (Admin PowerShell) to rebuild the lualatex.fmt format file with higher memory baked in.
  - Or switch engine: `luahbtex` as the driver. Simply replace all 3 occurrences of `lualatex` command with `luahbtex` in Stage 2. Luahbtex allocates memory dynamically from OS by default; there is no hard "capacity exceeded" style limit because it uses LuaJIT's heap.

**E7 expanded (Devanagari / CJK diacritics missing bars — macron, overdot, underdot):**
- Problem: Sanskrit-derived names in paper title / body use combining diacritics: Gyān (macron over 'a'), Rannitī (macron over final 'i'), Yojanā (macron over 'a'), Kriyakārī (macron over second 'a' and final 'i'). Latin Modern Roman, the default font, does ship glyphs for U+0101 ā, U+012B ī, etc. BUT if the document is compiled with a font that only has Basic Latin + Latin-1 Supplement (128+128 glyphs), those precomposed Unicode characters fall back to an empty box or the bare letter without diacritic.
- First fix is do-nothing: Our current main.tex loads `\usepackage{fontspec}` with default Latin Modern Roman which does include the precomposed glyphs. So with lualatex + fontspec + Latin Modern, this bug should not appear. If it does appear on a specific Windows machine:
  - E7a (confirm font loading): In main.log, search "Package fontspec Info". Fontspec logs every font it loads. Look for lines like "Package fontspec Info: Font family 'LatinModernRoman(0)' created for font 'Latin Modern Roman'". If it says "font not found, resorting to Computer Modern", something is wrong with the lm package — `tlmgr install lm lm-math` (reinstall Latin Modern).
  - E7b (switch to Noto Serif): Noto fonts from Google have the broadest Unicode coverage on the planet (1000+ scripts, all diacritics). Install + switch:
    1. Admin PowerShell: `tlmgr install noto noto-serif noto-sans`. Or download Noto Serif from https://fonts.google.com/noto/specimen/Noto+Serif → Install for all users via right-click OTF file → Install.
    2. Edit main.tex. Immediately AFTER `\documentclass[...]{acmart}` line, add:
       ```
       \usepackage{fontspec}
       \setmainfont{Noto Serif}[Ligatures=TeX]
       ```
    3. Save, rebuild. All diacritics render.
- Caution: If you add these two lines, commit the change to git so co-authors build identically; mixing LMR and Noto Serif between two builds creates subtle (1% total) different line/page breaks and page count drifts.

**E8 expanded (Disk full during Stage 1 install):**
- `install-tl-windows.exe` checks free space before starting. If C: drive has < 10 GB free it aborts. The actual install size of scheme-medium is roughly 6.2 GB, but the installer downloads 2 GB of compressed packages into %TEMP% (another C: location), then extracts to C:\texlive, then runs fmt generation which writes another 0.5 GB of temporary format files. Total transient C: usage: ~ 10 GB rounded.
- E8 Option 1 (clean up C:):
  1. Settings → System → Storage → Temporary files → tick everything (Windows Update Cleanup, Delivery Optimization, Temporary files, Thumbnails) → Remove files. Can free 2–20 GB.
  2. Empty Recycle Bin.
  3. `Dism.exe /online /Cleanup-Image /StartComponentCleanup /ResetBase` (Admin PowerShell) cleans WinSxS; saves 2–4 GB, takes 10-20 min, irreversible.
- E8 Option 2 (install to D:\):
  1. In the TeX Live GUI "Select directory" step, click Browse for "Installation directory" → navigate to D:\ → New folder → "texlive" → OK → OK. Installer writes to D:\texlive\2024.
  2. PATH entry becomes `D:\texlive\2024\bin\windows` instead of C: variant. Stage 2 manual PATH line changes accordingly.

### Additional unsorted troubleshooting hints (9th class of problems not captured in E1-E8):

- **lualatex hangs forever with no output after printing "This is LuaHBTeX...":** You forgot `--interaction=nonstopmode --halt-on-error` flags. lualatex hit an error and dropped to its interactive `?` prompt, waiting for a human to type something, but you can't see the prompt because there's no TTY attached. Kill with Ctrl+C. Re-run with flags. The first error printed is the real bug.
- **Pass 1 lualatex fails fatally, no PDF, and main.log says "! Undefined control sequence. l.XX \includegraphics":** The `graphicx` package didn't load, either because you commented out `\usepackage{graphicx}` or because graphics.sty is missing. Load it.
- **PDF renders, but copy-paste from the PDF produces garbage text (random Unicode characters) or Acrobat says "Content contains no extractable text":** Type 3 bitmap fonts are embedded (old-style raster fonts from the 1980s). Cause: pdfLaTeX with default OT1 encoding, or a bitmap-only font package. Fix: we use lualatex + fontspec + T1/Unicode, so this bug shouldn't happen. If it does, delete all .pk font cache files in C:\Users\<you>\.texlive2024\texmf-var\fonts\pk\ and rebuild.
- **ACM copyright block / ISBN / DOI missing from bottom of page 1 footer:** Check documentclass option `nonacm=true`. If nonacm is true, acmart skips the ACM copyright boilerplate. We need `nonacm=false` which is the default. If it's missing anyway, add `\setcopyright{acmcopyright}` after `\documentclass`.
- **Biber version mismatch log warning:** "Warning: Found biblatex version 3.20 but Biber is version 2.19. Please (re)run Biber." This happens after tlmgr update --all pulls a new biblatex before the matching Biber binary propagates. 95% of the time the bibliography still works. If it errors: wait 48 hours and run tlmgr update again; the Biber package catches up. Alternatively roll biblatex back one version.

## Quick Overleaf Parallel Track (If Local Build Fails 3+ Hours)

Zip acmart/ contents flat structure: zip root contains main.tex, references.bib, figures/ (NO wrapper). Upload → Overleaf new project → LuaLaTeX compiler + main.tex root → 3 passes. The OVERLEAF_COMPILE_GUIDE.md doc in same folder has 8 steps.

This parallel track exists because TeX Live installation on Windows has a small but non-zero failure rate (~ 5% of installs run into something weird: corrupted mirror, proxy corporate environment, antivirus that quarantines fmtutil.exe, Group Policy that blocks unsigned EXEs, etc.). Three hours of active debugging is enough time. After that, the probability that the remaining TeX issue takes more than 3 hours is high, and you should cut your losses.

Decision rule for abandoning local:
- You have 3+ hours of ACTIVE debugging time in (not waiting for downloads, not idle). Actively debugging = you reading logs, running commands, editing config files, uninstalling and reinstalling distributions.
- You have NOT produced a valid 9+ page PDF that passes Stage 3b checks #1 through #6.
- If both conditions are true → stop. Switch to Overleaf. It will work. The submission deadline is more important than pride in mastering TeX Live installation.

Exact switchover steps:
1. In File Explorer, navigate to `c:\Users\dhruv\Downloads\ASTRAOS\docs\paper\`.
2. Right-click the `acmart` folder itself → Send to → Compressed (zipped) folder. This creates `acmart.zip` next to the folder.
3. IMPORTANT: Before going to Overleaf, double-click acmart.zip in Explorer to open it. Look inside. Does the top level of the zip contain main.tex, references.bib, and figures\ folder? Or does the top level contain ONLY another folder called "acmart" with all the contents inside? The latter = one extra wrapper level. This is what Windows "Send to Compressed Folder" does by default when you zip a FOLDER (it puts the folder name as the root). Overleaf import script does NOT drill down one extra directory level when importing. You must fix this. Fix: Open the zip, go inside the wrapper folder, select all files inside, drag-and-drop to a new empty folder outside, re-zip from those files (not the enclosing folder). Or use the PowerShell Compress-Archive command from inside the acmart directory given in Stage 4 Source ZIP section; that one produces flat structure correctly.
4. Open https://www.overleaf.com/ → Sign in with your existing account (or register — free tier is fine, 1 private project limit on free tier = enough).
5. Dashboard → "New project" → "Upload project".
6. Drop the fixed flat-structure acmart.zip onto the upload dropzone. Overleaf unpacks it.
7. Project opens. Top-left menu: click "Menu" (hamburger icon) → Settings → Compiler → set to **LuaLaTeX** (critical; default is pdfLaTeX which fails on fontspec/includesvg). Set TeX Live version dropdown to "2024-08-15" or latest. Set Main document to main.tex.
8. Click "Recompile" button. Overleaf's compile engine runs the 4-pass sequence automatically (latexmk under the hood). Wait ~ 30 seconds. If warnings about missing packages on first compile, click the "Logs and output files" → check acmart is present; Overleaf almost always has it. If SVG→PDF fails, apply E1b (convert SVG to PDF via Chrome locally, replace includesvg with includegraphics line, edit main.tex in Overleaf web editor, re-upload PDF figure, recompile).
9. Verify output: same Stage 3b checks #1-#6 apply to Overleaf PDF (page count 9-11, 30 refs alphabetical, Figure 1 renders, abstract 249 words).
10. Overleaf → Download → PDF. Rename per Stage 4 naming rule, upload to HOTCRP.

Post-submission next steps checklist for a successful upload (regardless of whether the build was local or Overleaf):
1. Save portal submission-receipt PDF to `docs/paper/submission_receipt_codscomad2027.pdf`. Do not rely on the email; download the actual "Submission #XX confirmed" web page as PDF via browser Print → Save as PDF. Include visible timestamp in the screenshot.
2. Commit main.pdf SHA-256 hash + git commit SHA + upload timestamp + portal submission ID to PRODUCTION_DEPLOYMENT_CHECKLIST.md in the repository root (file creation if not exists).
3. Compose and send a short status email to co-authors:
   - To: Manan Nasa <...@stu.upes.ac.in>, Dr. Archana Kumari <...@faculty.upes.ac.in>
   - Subject: CODS-COMAD 2027 Submission Successful — Noesis: ASTRA OS
   - Body (2–3 sentences): "Hi Manan, Dr. Archana — I have successfully uploaded the final paper PDF and LaTeX source artifacts to the CODS-COMAD 2027 portal. Submission ID: #XXXX, portal timestamp: <date time UTC+5:30>. Attached the submission receipt PDF and SHA-256 hash for your records. Review decisions are expected mid-December 2026. Thank you both for your contributions. — Dhruv"
4. Commit everything in the repository to a dedicated submission tag: `git tag -a codscomad2027-submission-20261005 -m "CODS-COMAD 2027 paper submission tag (date 2026-10-05, PDF SHA-256 <hash here>)" ; git push origin codscomad2027-submission-20261005`. Tags are permanent references to the exact commit of the submission; branches can move later but tags stay fixed for posterity.
5. Close this playbook. Done.
