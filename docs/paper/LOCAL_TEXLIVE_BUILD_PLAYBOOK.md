# Local LaTeX Build Playbook — ACM SIGCONF COMS-COMAD PDF Final (Windows 10/11)

## Purpose

We have: (1) main.tex 250 ± 2 word abstract, (2) 30/30 \\cite{} refs inserted, (3) references.bib 30 entries, (4) 4 evaluation T2/T3/T4/T5 tables, (5) Figure 1 architecture SVG, (6) OVERLEAF_COMPILE_GUIDE.md for browser-based import. **This playbook is for the OFFLINE LOCAL Windows desktop lualatex + biber build so Dhruv can generate the final PDF on his laptop without Overleaf (better for offline work).** Output will be a 9-11 page ACM sigconf 9pt PDF.

The ACM SIGCONF proceedings class requires specific toolchain versions. Overleaf handles this transparently in the cloud; this playbook reproduces that pipeline deterministically on a bare Windows machine. Follow every step verbatim — the exact compile order is non-negotiable (biber must interleave matters).

Expected deliverables at the end of Stage 3: a reproducible main.pdf (9–11 pages) + a SHA-256 hash saved for audit + zip source artifacts for the CODS-COMAD submission portal.

## Environment Evidence 2026-10-05

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

Environment notes:
- The sandbox host used for drafting this playbook does not have TeX Live installed (as shown above). The reader's laptop will not have this constraint after completing Stage 1.
- LuaLaTeX is required because `\includesvg` (used for Figure 1 architecture diagram) and `fontspec` (used for Unicode Sanskrit diacritics in names like Gyān / Rannitī / Yojanā / Kriyakārī) are OpenType/HarfBuzz features that pdfLaTeX cannot handle.
- Biber (not BibTeX) is required because the `acmart` documentclass with `ACM-Reference-Format` bibliography style uses biblatex extended features (alphabetical sorting by first author surname, disambiguation of same-author-year papers, DOI/URL field handling). BibTeX will produce either no bibliography or wrong sort order. Do not try BibTeX.

## Stage 1: Install TeX Live on Windows (45–75 min; download ≈ 4–7 GB)

Choose ONE installer. Do NOT install both TeX Live and MiKTeX on the same machine — PATH conflicts cause phantom "not recognized" errors that are very difficult to untangle. Pick A or B, commit, and never look back.

### Option A (RECOMMENDED — Most Reliable) — tug.org official TeX Live

Official TeX Live from the TeX Users Group. This distribution is what Overleaf runs under the hood. Package set is frozen once per year so builds are reproducible year-to-year. Recommended for authors submitting to ACM venues because all `acmart.cls` updates are vetted against this distribution.

1. DOWNLOAD URL: https://tug.org/texlive/acquire-netinstall.html → Click "install-tl-windows.exe" (net installer ~ 25 MB).
2. Run install-tl-windows.exe as ADMINISTRATOR (right-click → Run as admin). UAC Yes. Running as non-admin puts binaries in `%LOCALAPPDATA%` which works but other Windows user accounts cannot share the install; admin install is simpler and the default C:\\texlive path is used by every downstream tutorial.
3. Installer opens GUI (TeX Live Manager). Click **Next**.
4. "Installation scheme" dropdown → SELECT: **scheme-medium (≈ 2 GB download)** — this is the BEST SWEET SPOT. Schemes explanation:
   - scheme-tiny:   ~ 300 MB download (TOO SMALL — missing acmart.cls class, missing biber, missing biblatex, compilation fails 100% — DO NOT USE)
   - scheme-small:  ~ 900 MB download (barely OK but we need acmart sometimes absent — do not risk)
   - **scheme-medium:** ~ 2 GB — includes acmart, biber, biblatex, lualatex, fontspec, includesvg, makeindex — all we need. Download size 2 GB. Install size 6 GB on disk in C:\texlive\2024.
   - scheme-full: ~ 7 GB — everything; takes 2h to download install. You don't need for this paper.
5. Click "Install". Progress bar appears. On a 50 Mbps connection: expect 20–40 minutes (medium scheme). DO NOT CANCEL mid-download. If you cancel mid-download, the partial package database is left in a corrupt half-installed state and you must delete C:\\texlive manually and rerun from scratch.
6. When install finishes → "Close installer". **RESTART COMPUTER** (required because installer updates PATH system-wide environment variables — new PATH only takes effect after logout or reboot.)

Post-reboot sanity: open PowerShell and type `lualatex --version` before proceeding. Do not proceed until this returns a version banner.

### Option B (Faster download, smaller install — for experienced users) — MiKTeX

MiKTeX is a "on-the-fly install package missing" distribution (when it needs a package, it downloads automatically). Total download first compile ~ 500 MB (much less). MiKTeX is fine for this paper; the only reason it is not recommended is that the on-the-fly dialogs can interrupt the Stage 2 unattended compile sequence 8–15 times, which is annoying but harmless.

1. URL https://miktex.org/download → miktex-setup-x64.exe → Run as Admin.
2. Install for anyone (all users). Click Next, accept, Install. Finishes in ~ 2 min.
3. Reboot Windows.
4. Pro Stage 2 first compile. First time when lualatex encounters missing `.sty` a MiKTeX popup appears → check "Always install missing packages on-the-fly" → OK. Let it download all packages. Repeat ~ 8-15 times then it's done.

MiKTeX notes: click "Always allow" on the certificate prompt if one appears. Do not click "Ask me every time" or the popup will loop forever. After the first successful full compile run, subsequent runs are fully cached and identical in speed to TeX Live.

## Stage 2: First Compile Run (PowerShell Commands)

Open NEW regular PowerShell. Do NOT use an elevated (Admin) PowerShell for compilation — Admin shells sometimes have separate user temp paths that interact oddly with DVI/aux intermediate files. Regular user shell is correct.

Verify installed:
```powershell
lualatex --version
biber --version
```

Expected output (version numbers may differ slightly):
```
This is LuaHBTeX, Version 1.18.0 (TeX Live 2024)
biber version: 2.20
```

If above command says "not recognized" → Stage 1 didn't complete or you forgot reboot. Close + reopen PowerShell (the PATH refresh happens on new shell). If still not working → add manually: `$env:PATH = "C:\texlive\2024\bin\windows;$env:PATH"` and retry. For MiKTeX the path is typically `C:\Program Files\MiKTeX\miktex\bin\x64\` if you installed for all users.

cd to paper directory:
```powershell
cd c:\Users\dhruv\Downloads\ASTRAOS\docs\paper\acmart
```

Sanity check you're in the right folder:
```powershell
Get-ChildItem main.tex, references.bib, figures\figure1_architecture.svg
```
All three files must show up. If any are missing, you cd'd into the wrong directory.

COMPILE SEQUENCE = **3× LUALATEX passes + 1× BIBER pass in between**. You MUST run IN THIS EXACT ORDER for references+crossrefs+list of tables to settle correctly. The correct order: (PASS 1) LUALATEX → (PASS 2) BIBER → (PASS 3) LUALATEX → (PASS 4) LUALATEX. Run these commands verbatim:

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

Explanation of flags and why 4 passes:
- **Pass 1 lualatex: Scans `main.tex` for `\cite{key1,key2,...}` tokens and writes every cited keys to `main.aux`, plus writes `main.bcf` control file. No bibliography is rendered yet. Page numbers and cross-refs are placeholders.
- **Pass 2 biber:** Reads `main.bcf` → looks up those 30 keys in `references.bib` → sorts them alphabetically by first author surname per ACM-Reference-Format rules → writes formatted bibliography to `main.bbl`. If any key is missing from the bib file, biber warns here.
- **Pass 3 lualatex:** Ingests `main.bbl` and actually typesets the References section at end of document. Citation callouts in the text [1], [2], ... become correct numbers, but page numbers in forward-references (e.g. "see Table T2 on page 5") may still be wrong because inserting the bibliography shifted all the subsequent page breaks.
- **Pass 4 lualatex:** Final stabilization pass. All cross-references, page numbers, List of Tables, hyperref PDF bookmarks, and citation backlinks are now correct. The `.aux` file written at end of Pass 4 matches the one at start so a 5th pass would be a no-op.

Intermediate warnings during pass 1 are normal ("Citation foo undefined", "Reference tab:t2 undefined on page 2"). Those disappear after pass 3/4. Only react to warnings still present in the Pass 4 log. A Pass 1 or 3 warning about undefined refs is not a bug.

If any PASS returns a non-zero exit code, stop and read Troubleshooting section E1–E8 before rerunning. Do not blindly rerun hoping the error vanishes — LaTeX errors are deterministic.

## Stage 3: Output Verification (Post Compile)

Verify results. Do not skip this section. Papers that pass compile but fail verification get desk-rejected by ACM venue admins for reasons that are trivial to catch here.

### 3a. Final exit status

The last lualatex PASS 4 command's LAST LINE should look SIMILAR to:
```
Output written on main.pdf (9 pages, 842310 bytes).
Transcript written on main.log.
```

Page count expected: **9–11 pages** (varies on bibliography wrapping + table heights). 8 pages = too short — check if bib rendered. 12+ pages = check you didn't accidentally enable 10pt option or double spacing. ACM SIGCONF HARD LIMIT: 10 pages long paper + references = 11 max (OK up to 12 if appendix; CODS-COMAD reviewers lenient ±1 page). Page count OUTSIDE 9-11: → go back main.tex \documentclass options line and confirm sigconf, 9pt. Should be: `\documentclass[sigconf,9pt,review=false,nonacm=false]{acmart}`

Interpretation of file size:
- < 300 KB means images likely didn't embed (SVG→PDF conversion failed, Troubleshooting E1)
- 500 KB – 1.5 MB is normal for a 9–11 page paper with 1 vector figure and 4 tables
- > 5 MB means you accidentally embedded a raster PNG at 1200 DPI or embedded fonts twice — not a submission blocker but wastes portal upload quota

### 3b. PDF Sanity Checks (Open main.pdf manually)

Open main.pdf in Adobe Reader / Edge / Sumatra. Do not use a browser inline preview for verification; browser previews sometimes omit embedded fonts or render Type 3 fonts as rasters.

(1) Title page → Abstract wordcount copy-paste 1 paragraph into wordcounter.net → should read 248–252 words. The abstract is the single paragraph immediately below the author block. Do not count title / authors / keywords. If 253+ words, editors' automated tooling will flag. If 240- words, reviewers may feel the contribution is underspecified. Our target is 249 words on the nose per the abstract that was already signed off in `00_abstract_and_title_authors.md`.

(2) Page ~ 3/4 → C1 Capability Gate section → look for "Saltzer and Schroeder" 2 cites — both keys should appear numbered correctly in [brackets]. The exact cite form is expected to be [22] and [23] but the number can shift if bibliography order changes (ACM is alphabetical so Saltzer & Schroeder 1975 lands near the S entries which are the second half). The point is: no [?], no bold keys, no raw citekey visible. If you see `\cite{saltzer1975protection_classic}` typeset literally as source code, you left off a backslash or introduced a space in the source.

(3) Page ~ 5/6 → 4 evaluation tables T2, T3, T4, T5 present (T2 SE50, T3 HumanEval buckets, T4 Appendix promo tiers ablation A/B/C, T5 MBPP difficulty). Every table must have a numbered caption above it ("Table 2: ...", "Table 3: ..."), must have the `\label{tab:t2}` etc. cross-reference link working, and must display the correct 3-column numerical body from our evaluation results. If a table body is blank, the `\input{}` or inline tabular was commented out in main.tex. If T4 is missing entirely, the appendix-include conditional in main.tex needs toggling.

(4) References section (last 1–2 pages): count numbered entries — **count must equal 30** (one for each bib key). If only 29 counted: the saltzer1975protection_classic duplicate cite might not have rendered (check it got cited in §Results). If < 29 you missed an \cite{} somewhere. How to count quickly: entries are numbered [1] through [30] — the last reference block should start with "[30]". If it stops at [28] then 2 entries exist in the bib but were never `\cite`d in the body, which means the biblatex `\printbibliography` correctly omits uncited entries — go find which 2 and add `\nocite{key1,key2}` or `\cite` them properly in text (we already inserted all 30 cites in a prior editing pass so this failure mode indicates a key typo).

(5) References sort order (ACM-Reference-Format = alphabetical order by first author surname NOT citation order in text — correct; references list IS alphabetical → this means `ACM-Reference-Format` bst style applied correctly; if they appear in citation numbering order 1→2→3 in text = you used plain style wrong → rerun playbook Stage 2). Spot check: [1] should be a paper whose first author surname starts with a letter early in the alphabet (e.g. A, B, C), not whatever was cited first in Introduction. Alphabetical = ACM format is correct (alphabetical) plain style is wrong (citation order plainnat or plain wrong here for SIGCONF.

(6) Figure 1 architecture → renders on page ~2/3. If image is a broken red box [Missing] → includesvg failed. Fix → Troubleshooting E1 below. The figure caption is "Figure 1: ASTRA OS High-Level Architecture" and shows 19 architecture nodes; if it shows 18 nodes you opened an outdated PNG export or edited wrong version. If the figure renders but labels inside the flowchart arrows overlay incorrectly shifted text, the SVG→PDF Inkscape conversion went wrong — use the fallback E1b.

### 3c. File hash check

PowerShell: `Get-FileHash main.pdf -Algorithm SHA256 | Select-Object Hash`. Save hash in PRODUCTION_DEPLOYMENT_CHECKLIST master for reproducibility.

Why this matters: CODS-COMAD portal accepts a PDF upload. If 6 months later a reviewer says "the version I downloaded has a different table T4 value than the one I approved", the SHA-256 is the only proof that the file you upload today is the same one we verified locally. Record it alongside the date and the git commit SHA of the source this repository. Example line for the record:
```
Date: 2026-10-05
Git:  <your commit sha here after commit>
PDF:  <sha256 from command>
Name: Noesis_CODSCOMAD2027_FinalPaper_20261005.pdf
```

## Stage 4: Upload CODS-COMAD

Portal opens Oct 2026 (mid-Nov 2026 abstract deadline). The CODS-COMAD 2027 submission system is managed via the ACM HOTCRP instance at a URL that will be emailed by the PC chairs. Do not upload to the wrong conference the general ACM article templates page. Upload:

- FINAL_PDF: copy `main.pdf` → rename to `Noesis_CODSCOMAD2027_FinalPaper_20261005.pdf`.
  - File naming format required per CODS-COMAD: `<ProjectAcronym>_<Venue><Year>_<FinalPaper_<YYYYMMDD>.pdf. No spaces, no Unicode characters in filenames or the portal will silently reject.
  - Before upload, reopen the renamed PDF once to double-check no artifacts introduced nothing happened during copy/rename.
- LA SOURCE ZIP: `Compress-Archive -Path main.tex,references.bib,figures\figure1_architecture.svg,OVERLEAF_COMPILE_GUIDE.md -DestinationPath codscomad2027_source_artifacts.zip`
  - This zip is what ACM admins request for the "LaTeX source required for camera-ready. Not all venues require source at initial review submission, but providing it up front signals professionalism and eliminates a back-and-forth if the PC asks for it.
  - The Compress-Archive command above deliberately does NOT zip up the 18 intermediate files (.aux, .bbl, .bcf, .log, .out, .toc, ...) — only the 4 canonical inputs plus figures folder subdirectory. If you zip the whole directory via Explorer "send to → compressed folder" you will accidentally include the intermediates which is not a bug but bloats the zip and makes your build non-clean reviewers cannot reproduce from source.
  - Validate the zip after creation: expand it to a temp folder and confirm main.tex + references.bib are at the zip root (not nested inside an extra acmart/ wrapper folder). Many a source upload has been rejected by the artifact extract script because of one extra wrapper folder.
- AUTHORS ORDER: Dhruv Shah¹, Manan Nasa², Dr. Archana Kumari³. All UPES School of Computer Science affiliation (¹² student, ³ faculty).
  - Author contribution CRediT taxonomy (copy-paste into the portal's Author Roles field):
    - Dhruv Shah: Conceptualization, Methodology, Software, Validation, Formal Analysis, Investigation, Data Curation, Writing – Original Draft, Writing – Review & Editing, Visualization
    - Manan Nasa: Software, Validation, Data Curation, Writing – Review & Editing
    - Dr. Archana Kumari: Supervision, Writing – Review & Editing, Project Administration, Resources

Double-check submission portal fields:
  - Corresponding author email: Dhruv's UPES student email (not personal gmail — ACM correspondence goes to institutional addresses preferred).
  - Track: Full Research Paper (not Short Paper, not Poster, not Demo — our 10 page format is full paper).
  - Keywords copy-paste from main.tex exactly as typeset below the abstract, in same order, comma-separated.

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

Additional unsorted troubleshooting hints for weird edge cases not in table:
- If lualatex hangs indefinitely with no output: you forgot `--interaction=nonstopmode` flag and LaTeX stopped at an error prompt waiting for keyboard input. Ctrl+C kill, rerun with flags from Stage 2, read the first error.
- If `biber main` says "Cannot find 'main.bcf'" after Pass 1 ran: Pass 1 lualatex failed with a fatal error before it could write main.bcf. Scroll up the Pass 1 log — the first error in Pass 1 is the real error, not the downstream biber failure.
- If the PDF opens but all text is selectable garbage or the PDF viewer says "cannot extract text": Type 3 bitmap fonts embedded. Ensure \usepackage[T1]{fontenc} is loaded (acmart loads it). Delete all .pk bitmap font cache and recompile.
- If the references render successfully but the ACM copyright block at bottom of first page is missing or shows boilerplate "AcM wrong class. The correct line should be "© 2026 Copyright held by the owner/author(s). Publication rights licensed to ACM." This is injected by `\setcopyright{acmcopyright}` inside acmart — if missing, double-check nonacm=false (the \documentclass option we have it set already.

## Quick Overleaf Parallel Track (If Local Build Fails 3+ Hours)

Zip acmart/ contents flat structure: zip root contains main.tex, references.bib, figures/ (NO wrapper). Upload → Overleaf new project → LuaLaTeX compiler + main.tex root → 3 passes. The OVERLEAF_COMPILE_GUIDE.md doc in same folder has 8 steps.

Decision rule for abandoning local and switching tracks: if you have invested 3 hours of active debugging local TeX Live / MiKTeX installation issues without a successful 9+ page PDF, stop. The Overleaf path is guaranteed to work in <15 minutes because it has every package preinstalled and Inkscape already configured. Local build is nice-to-have for offline iteration; a submission deadline is the actual milestone. Save the broken local install state in a git branch if you want to debug after the deadline, but get the paper into Overleaf now, verify the PDF there, submit from there, and come back to fix local TeX at leisure.

Post-submission next steps checklist for a successful upload:
1. Save portal submission-receipt PDF to `docs/paper/submission_receipt_codscomad2027.pdf`.
2. Commit main.pdf sha256 hash + git commit + upload timestamp to the PRODUCTION_DEPLOYMENT_CHECKLIST in repository root.
3. Email co-authors Manan + Dr. Archana a note that submission was successful with a link to the portal submission status page.
4. Close this playbook. Done.
