# Overleaf Compile Guide — Noesis ACM CODS-COMAD 2027 Submission

---

## Prerequisites

- Overleaf account
  (free tier sufficient —
  1 project,
  no GitHub sync needed;
  or paid Overleaf Premium
  for Git sync)

- All files in local folder
  `c:\Users\dhruv\Downloads\ASTRAOS\docs\paper\acmart\`
  zipped into one
  `noesis_acmart_submission.zip`
  (DO include:
  main.tex,
  references.bib,
  figures/figure1_architecture.svg;
  DO NOT include:
  OVERLEAF_COMPILE_GUIDE.md itself
  or any other unrelated files)

- Zip structure MUST be flat
  at zip root:
  main.tex and references.bib
  at top,
  figures/ folder
  as subfolder,
  no extra acmart wrapper directory
  (Overleaf auto-unzips flat).

---

## Step-by-Step (8 Steps)

### Step 1 — Upload zip to Overleaf

1. Open https://www.overleaf.com/project
   → New Project
   → Upload Project
   → Select the zip
   → Upload.

### Step 2 — Configure Compiler & Settings

2. Overleaf auto-creates
   noesis_acmart_submission project.
   Top Menu → Settings (gear icon):
   - Compiler = **LuaLaTeX**
     (NOT pdfLaTeX —
     we use includesvg for SVG
     and ACM-Reference-Format bib
     requires LuaLaTeX).
   - Set Main document = main.tex.
   - Set TeX Live version = 2024
     (most recent;
     if not available use 2023).

### Step 3 — First Recompile (warm-up pass)

3. Click **Recompile** button
   (first time may take 60–90s
   because LuaLaTeX loads
   acmart class
   + ACM-Reference-Format).
   Ignore 2–3 standard warnings
   (undefined refs,
   missing CCS XML —
   these resolve pass 2/3).

### Step 4 — Verify Biber ran (check cite keys)

4. **First pass** ends
   with warnings
   "Citation(s) undefined" (normal).
   Top Menu → Logs and output files
   → Click **Open Biber/BibTeX logs**
   → Verify it says
   "Found 30 cite keys,
   processing references.bib".
   If it says
   "0 cite keys found"
   → check you ran
   \bibliographystyle{ACM-Reference-Format}
   not plain —
   our main.tex line 264
   already correct.

### Step 5 — Second Recompile (resolve citations)

5. **Second pass: Recompile again**
   (mandatory —
   Overleaf does NOT auto-run biber
   between passes).
   Now citations should resolve,
   and References section shows
   all 30 entries
   numbered correctly.

### Step 6 — Third Recompile (resolve cross-refs)

6. **Third pass: Recompile one last time**
   to fix cross-reference
   Table \ref{tab:t2}
   and Figure \ref{fig:arch} links.
   Warnings now ≤ 3
   (acceptable for ACM sigconf review).

### Step 7 — Download PDF & Verify Page Count

7. Download PDF:
   Menu → Download PDF → `main.pdf`
   — verify pages:
   - front matter
     (title/abstract/CCS/keywords 1p),
   - §1 Intro (1p),
   - §2 Methodology+Fig1 (1p),
   - §3 C1 Gate (1p),
   - §4 C3 Memory (1p),
   - §5 Evaluation Tables T2-T5 (2-3pp),
   - §6 Threats + §7 Related + §8 Conclusion (2pp),
   - §9 References (1-2pp)
   → **Total 9–11 pages acceptable**
     for CODS-COMAD long paper
     10-page target.

### Step 8 — Final Pre-Submission Checks (3 subchecks)

8. **Final checks** before submission:

   (a) Wordcount of Abstract
       → exactly 250 ± 2
       (copy-paste from PDF Abstract
       into wc/wordcounter.net
       — main.tex line 74 abstract
       must be 248–252 range).

   (b) References:
       all 30 entries present
       numbered 1–30 in bibliography.

   (c) Figure 1 (architecture) renders clearly.
       If SVG-includesvg error "Missing PDF"
       see Troubleshooting below.

---

## Troubleshooting (Common Errors)

### E1: Missing acmart.cls

**E1: ! LaTeX Error: File `acmart.cls' not found.**
→ Fix:
Overleaf already has acmart.cls
preinstalled (ACM class).
In Settings ensure
the document class is recognized;
if not,
create a new empty
"ACM SIGCONF" template
from Overleaf Template Gallery
and copy-paste main.tex content
into it.

### E2: SVG includesvg missing PDF fallback

**E2: SVG Figure "! Package svg Error: File `figure1_architecture.pdf' is missing on first pass"**
→ includesvg runs Inkscape.

Fix 1:
Go to Menu → Settings
→ Enable Shell-escape (write18) = CHECKED.
Recompile.

Fix 2 (reliable fallback if Fix 1 still fails):
Locally convert SVG → PDF on Windows:
open figure1_architecture.svg in Chrome
→ Ctrl+P
→ Save as PDF
(use Print to PDF,
Landscape A4).
Upload resulting figure1_architecture.pdf
to Overleaf figures/ folder.
Change main.tex line 94
from \includesvg
to \includegraphics[width=\columnwidth]{figures/figure1_architecture}
— includesvg will automatically
pick up .pdf fallback,
or manually swap command
to \includegraphics.

### E3: All 30 citation keys undefined

**E3: Undefined citation warnings all 30 keys**
→ Biber didn't run.
Settings → Bibliography backend = **Biber**
(NOT BibTeX).
Then recompile TWICE.

### E4: Abstract exceeds word limit

**E4: Abstract too long (Overleaf Warning "Abstract longer than 300 words")**
→ Edit main.tex abstract
back to 250 ± 2 range
(max accept ACM hardcoded tolerance).

### E5: TeX capacity exceeded

**E5: ! TeX capacity exceeded, sorry**
→ SVG figure too large.
Run fallback E2 PDF conversion above.

---

## CODS-COMAD Portal Upload (mid-Nov 2026)

### Timeline & Registration

- Portal opens October 2026.
  Student registration:
  dhruv.shah@stu.upes.ac.in.

### Paper Category & Format

- Paper type: Full Research Paper
  (8–12 pages,
  formatted in ACM sigconf 9pt style
  — our output fits).

### Files to Upload

- Uploads:
  (1) final main.pdf,
  (2) zip LaTeX source files
  (same zip created in Prerequisites)
  as supplementary material
  for artifact review.

### Authors & Affiliations

- Authors:
  Dhruv Shah 500118979 1st,
  Manan Nasa 500123471 2nd,
  Dr. Archana Kumari 3rd (mentor).
  Affiliations all UPES SCS Dehradun 248007.

### Abstract (Portal Field)

- Abstract as submitted to portal
  = EXACTLY 250 words
  same as main.tex abstract.
  Don't re-write — copy-paste.

### Keywords (Portal Field)

- Keywords:
  from main.tex line 43
  (Multi-agent systems,
  capability-based security,
  HMAC capability gates,
  hierarchical memory systems,
  code generation benchmarks,
  Sanskrit agent nomenclature,
  formal access control).

---

*End of guide.*
*Compile success = 9–11 pp PDF with ≤ 3 warnings.*
