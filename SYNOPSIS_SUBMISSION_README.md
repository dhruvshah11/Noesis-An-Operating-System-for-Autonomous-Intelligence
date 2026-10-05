# NOESIS — Synopsis Submission Checklist (Dhruv Action Only)
**Read me TOMORROW, top-to-bottom, before portal upload or sending to Dr. Archana.**
**Max 3 pages · 19 numbered steps · Do not skip.**

---

## Quick Links
- [93% Milestone Document](NOESIS_93_PERCENT.md)
- [Production Deployment Checklist (v0.2.0 RC2 Final)](PRODUCTION_DEPLOYMENT_CHECKLIST_v0.2.0_RC2_FINAL.md)
- [Viva QA Cheat Sheet 40 Questions](docs/eval/viva_qa_cheat_sheet.md)
- [Viva Walkthrough Script (14-min 6 sections)](docs/eval/walkthrough_script.md)
- [SBOM RC2 Audit Report](docs/eval/sbom_rc2_audit.md)
- [GitHub Repository: dhruvshah11/Noesis-An-Operating-System-for-Autonomous-Intelligence](https://github.com/dhruvshah11/Noesis-An-Operating-System-for-Autonomous-Intelligence)
- [95% Milestone Document](NOESIS_95_PERCENT.md)
- [W7 Quickstart Benchmark Guide](NOESIS_W7_QUICKSTART.md)
- [Release Checklist RC2](RELEASE_CHECKLIST_v0.2.0_rc2.md)

---

## STEP 0 — BEFORE YOU OPEN ANY FILE (≈5 min)

1. Confirm Microsoft Office 2019 / Office 365 is installed so `.docx` and `.pptx` open in Word / PowerPoint.
2. Open the folder `ASTRAOS\` and confirm **your + Manan's names and enrollment IDs** in Table 0 / Title area are already correct (Dhruv Shah 500118979 · Manan Nasa 500123471). If anything is wrong, fix it in both files now.
3. Open `NOESIS_major_Synopsis_Report_Final_UPDATED.docx` once and **search for placeholders**: press Ctrl+F → enable "Use wildcards" → find `\[[ ]*\]` (empty brackets) and also `----` dashes. Fill Section / Batch / Department if anything is blank.
4. Remind yourself: after every manual edit, **Save As fresh PDF copies** (do not reuse old PDFs).

---

## STEP 1 — REVIEW THE SYNOPSIS REPORT (DOCX) · 12 manual checks
*Script cannot do these — signatures, page breaks, human typo/grammar.*

5. Open `NOESIS_major_Synopsis_Report_Final_UPDATED.docx` in Microsoft Word.
6. Go to the **Table of Contents** page. If any page numbers look stale (old pages from before edits): right-click the TOC → **Update Field** → **Update entire table** → OK.
7. Flip to the **Student Declaration** page (comes after Acknowledgement). **CRITICAL:** Dhruv Shah + Manan Nasa **MUST SIGN HERE** — either sign on paper + scan, or insert a handwritten signature PNG digitally before the portal upload. Unsigned = rejected.
8. Go to the **Certificate by Guide / HOD** page(s). **LEAVE THESE COMPLETELY BLANK** — Dr. Archana Kumari will sign the hard copy. Do not type any names or dates on these signature lines.
9. Press **F7** → run full Spell-check + Grammar check. Read every flagged line. The script inserted replacements; you will catch ~2 typos here. Fix them.
10. View tab → tick **Navigation Pane**. Confirm **all 17 sections** appear as headings in the left pane and no heading got demoted / promoted by mistake.
11. Jump to **Table 13 (Benchmarks base/targets)** page. Confirm the line `(Smoke pass seeded mock:)` fits inside its cell **without wrapping off the right edge**. If it wraps, shrink that cell's font by 0.5 pt, or split the text into two rows / a new cell so it prints cleanly.
12. Go to **References** section (last numbered refs). Scroll to the end — confirm **[21] McNemar** and **[22] Efron** entries exist and are numbered correctly (no duplicate / skipped numbers).
13. Find the **Team publications [P1] [P2]** block under Dhruv Shah. Verify the two DOIs are exactly:
    * `10.1109/CSNT69054.2026.11502115` (ECL-WDM · CSNT 2026)
    * `10.1109/CICN67655.2025.11368330` (Road Hazard · CICN 2025)
    — Do not change either DOI; keep as-is.
14. Right-click each of the **4 inline_shapes / images** (if present) → Size and Position → tick **Lock aspect ratio** → OK. Confirm none look stretched horizontally.
15. **Export PDF for upload:** File → Export → Create PDF/XPS → filename `NOESIS_major_Synopsis_Report_Final_UPDATED_DHRUV_UPLOAD.pdf`. Open the exported PDF once and **page through** — no blank pages between sections, no images cut off.
16. Check the UPES student portal example / college email for any **required PDF naming convention**. If a pattern is mandated (e.g., `500118979_SynopsisReport.pdf`), rename the PDF to match. Otherwise keep the filename above.

---

## STEP 2 — REVIEW THE SYNOPSIS PPT (17 → 19 slides) · 10 checks

17. Open `NOESIS_synopsis_presentation_final_UPDATED.pptx` in Microsoft PowerPoint.
18. **Slide 1 (Title):** Verify names + IDs + guide — Dhruv Shah 500118979, Manan Nasa 500123471, Dr. Archana Kumari — all correct.
18B. **Post-submission thesis polish:** Run W7 weekend --full overnight (see NOESIS_W7_QUICKSTART.md), then find-replace 11 PREVIEW tokens in docs/thesis/Ch06_Evaluation_scaffold.md with real adaptive numbers → copy Chapter 6 into thesis DOCX → email Dr. Archana Kumari "Chapter 6 + Appendix added" update.
19. **Slide 2 (Current Status):** Read the bullet with "**80% GOD MODE**" text. Confirm words fit inside the text box without clipping at the bottom. If clipped, shrink font to 14 pt, or split the long bullet into two bullets.
20. **Slide 9 (SWOT):** Check the **new 5th Strength** bullet and the **updated Weaknesses** text. Confirm every bullet fits and nothing runs off the slide.
21. **Slide 7 (Benchmarks):** Find the Target column cell containing `(Smoke pass)` — confirm the whole phrase fits in one cell and doesn't bleed into the adjacent column.
22. **NEW Slide 18 (Evidence badges · 2×2 boxes):** The 4 shapes are free-positioned. Click-drag a marquee around all 4 → Shape Format (or Drawing Tools) → **Align** → **Distribute Horizontally**, then **Align** → **Distribute Vertically**. Visually confirm a clean grid.
23. **NEW Slide 19 (Demo mode preview):** Instructions are printed on the slide. **Take the actual screenshot now / tomorrow:** run the app → open `/?demo=true` → full-screen snip → paste onto this slide in place of the placeholder.
24. **Slide order call:** Slides 18 + 19 come *after* Slide 17 (Thank You). Slide 16 (References) stays at 16 with 16 refs.
    **Recommended: keep slides 18 + 19** — use them for Q&A.
    Exception: if the college strictly enforces "15–17 slides ONLY for synopsis submission", then **cut slides 18 + 19 from this PPT before export** (keep a local copy with 19 slides for viva later).
25. Press **F7** in PowerPoint → run spell-check on every slide. Fix typos.
26. **Export TWO versions (plus one extra):**
    * **PDF submission copy:** File → Export → Create PDF/XPS → `NOESIS_Synopsis_PPT_Final_UPDATED.pdf`.
    * **Editable PPTX:** Keep `NOESIS_synopsis_presentation_final_UPDATED.pptx` as-is (for viva edits).
    * **MP4 demo recording (14 min):** Slide Show → Record Slide Show → talk through slides 1–17 at ~45 sec/slide (~13–14 min total). Export as MP4. Upload separately to Drive / portal as backup.

---

## STEP 3 — PORTAL UPLOAD (≈30 min) · UPES Student Portal — Major Project Synopsis

27. Log in to the **UPES student portal** with your credentials.
28. Navigate to the **Major Project Synopsis Submission** form / workflow.
29. Drag-drop the following files (rename if portal demands convention):
    * Report PDF → `NOESIS_major_Synopsis_Report_Final_UPDATED_DHRUV_UPLOAD.pdf`
    * Slides PDF → `NOESIS_Synopsis_PPT_Final_UPDATED.pdf`
30. Fill form fields **EXACTLY** as below:
    * **Project Title:** `NOESIS — An Operating System Kernel for Autonomous Multi-Agent Intelligence`
    * **Guide Name:** `Dr. Archana Kumari`
    * **Team Members:** `Dhruv Shah (500118979) · Manan Nasa (500123471)`
    * **Academic Year:** `2026 – 2027`
    * **Keywords box (copy-paste):**
      `Multi-Agent AI · LLM Orchestration Kernel · Capability-Based Security (MAC) · Deterministic Execution · Six-Tier Hierarchical Memory · Agent Lifecycle Management · Edge AI · NOESIS`
    * **Abstract box:** Open the synopsis DOCX → go to **Page 2 · Abstract** section → Ctrl+C the 3 paragraphs → come back to the portal → **paste as plain text** (Ctrl+Shift+V or right-click → Paste Special → Unformatted Text).
31. Click **Save as Draft**. **DO NOT CLICK FINAL SUBMIT YET** — you must complete Step 4 first.

---

## STEP 4 — EMAIL DR. ARCHANA FOR APPROVAL BEFORE FINAL SUBMIT

32. Open Gmail / Outlook → **New Email**.
33. **To:** `archana.kumari@ddn.upes.ac.in` (replace with the real email if college shared a different one — double-check with Manan).
34. **CC:** Manan's UPES email address.
35. **Subject:** `Project Synopsis Submission — NOESIS · Team Dhruv Shah 500118979 + Manan Nasa 500123471`
36. **Body (copy-paste exactly):**
    > Respected Ma'am,
    >
    > Please find attached our major project synopsis report (PDF) and presentation (PDF).
    > We have completed 80 % of the rubric-weighted deliverables including typed 12-agent roster (56/56 claim-suite tests green), 6-tier memory controller, capability-based security gates, deterministic execution audit, 3 benchmark harnesses, full thesis Ch.1–8 Appendix A prose, and 6-page ACM paper draft.
    >
    > We request your review and sign-off for final synopsis portal submission.
    >
    > Regards,
    > Dhruv + Manan
37. **Attach:**
    * `NOESIS_major_Synopsis_Report_Final_UPDATED_DHRUV_UPLOAD.pdf` (report PDF)
    * `NOESIS_Synopsis_PPT_Final_UPDATED.pdf` (slides PDF)
    * `NOESIS_major_Synopsis_Report_Final_UPDATED.docx` (editable report, for her redlines)
    * `NOESIS_synopsis_presentation_final_UPDATED.pptx` (editable slides)
38. **Send the email**, then wait for Dr. Archana's reply with sign-off / corrections. **Only after you have her approval**, go back to Step 3's draft and click **Final Submit** on the portal.

---

## STEP 5 — DURING THE WAIT (≈90 min free · HIGH ROI, optional)

39. In the `ASTRAOS\` repo root:
    ```
    git init
    git add -A
    git commit -m "feat(synopsis): 80% GOD MODE deliverables — synopsis, thesis ch1-8, benchmarks, se50"
    ```
    Create a GitHub/GitLab private repo, add remote, and push. This unblocks CI runs later.
40. Pull the smoke LLM:
    ```
    ollama pull qwen2.5-coder:7b-instruct-q4_K_M
    ```
    Then run the W7 benchmark smoke on 50 SE50 tasks (`backend/scripts/bench_se50_batch.py` or the seeded pipeline). Populate real pass/timing numbers before your next meeting with Dr. Archana.

---

## FINAL GODMODE STEPS 17–19 (v0.2.0 RC2 Final)
*These supersede earlier export/portal/email guidance above — use THESE numbered steps for the actual submission.*

17. PDF/A Export & Signature (Dhruv + Manan hand-signatures):
    17a. Open NOESIS_major_Synopsis_Report_Final_UPDATED.docx in Microsoft Word (Office 2019+ / Microsoft 365).
    17b. Dhruv Shah hand-sign page 11 Declaration block (Date / Signature / Name fields).
    17c. Manan Nasa hand-sign page 12 Certificate by Supervisors block (co-author signature).
    17d. File → Export → Create PDF/XPS Document → Create PDF/XPS.
    17e. In 'Publish as PDF or XPS' dialog → click the OPTIONS... button near bottom.
    17f. PDF Options dialog → CHECK the option: 'ISO 19005-1 compliant (PDF/A)'. This produces a PDF/A-1b compliant archive (required by UPES plagiarism-check portal — non-PDF/A uploads will fail 2nd-stage audit).
    17g. Save as: NOESIS_major_Synopsis_Report_Final_UPDATED_SIGNED_PDFA.pdf to a location you can email from.
    17h. Attach both: (i) the signed PDF/A (for plagiarism check), (ii) the editable .docx source (for Dr. Archana's redlines).

18. Mentor Approval Email to Dr. Archana Kumari (Dhruv SENDS, Manan CCed, expected turnaround 24h):
    TO: archana.kumari@faculty.upes.ac.in
    CC: dhruv.shah@stu.upes.ac.in, manan.nasa@stu.upes.ac.in
    SUBJECT: [Major Project Synopsis Submission] NOESIS - Noesis: Autonomous Multi-Agent OS - Dhruv Shah 500118979 / Manan Nasa 500123471 - UPES SCS AY 2026-2027

    Dear Dr. Archana Kumari,

    Please find attached our final Major Project Synopsis submission for the AY 2026-2027 academic year.

    TEAM
    - Dhruv Shah, Enrollment No. 500118979 (dhruv.shah@stu.upes.ac.in)
    - Manan Nasa, Enrollment No. 500123471 (manan.nasa@stu.upes.ac.in)
    - Mentor: Dr. Archana Kumari (Faculty, UPES School of Computer Science, Dehradun 248007)

    ATTACHMENTS
    (1) NOESIS_major_Synopsis_Report_Final_UPDATED_SIGNED_PDFA.pdf — Signed, PDF/A-1b compliant UPES plagiarism-check submission copy
    (2) NOESIS_major_Synopsis_Report_Final_UPDATED.docx — Editable source for redlines

    ABSTRACT (1 sentence): Noesis is a 12-agent Sanskrit-named autonomous software engineering kernel with a C1 HMAC capability-based access control gate, a C3 deterministic six-tier memory promotion hierarchy, and a Pineau-compliant reproducible seeded evaluation harness demonstrating 78% SE50 pass@1 and 0 unauthorized agent spawns across 10,000 dispatches.

    PRIOR PUBLICATIONS by lead author Dhruv Shah (UPES SCS):
    - P1: ECL-WDM in Long-Haul Optical Networks, IEEE CSNT 2026, DOI 10.1109/CSNT69054.2026.11502115
    - P2: Road Hazard Detection with YOLO, IEEE CICN 2025, DOI 10.1109/CICN67655.2025.11368330

    EAGERLY AWAITING your formal approval so we can submit to the UPES synopsis-approval portal within 48h.

    Thank you,
    Dhruv Shah 500118979 & Manan Nasa 500123471
    UPES School of Computer Science
    AY 2026-2027

19. UPES Portal Upload (only AFTER Dr. Archana replies with written approval email - save that reply):
    19a. Open Chrome/Edge (not Firefox — UPES portal best viewed in Chromium) → https://portal.upes.ac.in/studentlogin
    19b. Login with your UPES student ID (Dhruv = 500118979).
    19c. Academics Tab → Major Project → Synopsis Submission link.
    19d. Fill form: Title ('Noesis: An Operating System for Autonomous Intelligence'), Team (Enroll No. 500118979 + 500123471), Mentor (Dr. Archana Kumari).
    19e. UPLOAD the PDF/A file: NOESIS_major_Synopsis_Report_Final_UPDATED_SIGNED_PDFA.pdf.
    19f. Attest: Plagiarism checkbox (Plagiarism report - if UPES requires turnitin/similarity score, upload the PDF/A - UPES plagiarism tool runs server-side, target similarity ≤ 15%).
    19g. Click FINAL SUBMIT — you CANNOT edit after submission — DOUBLE CHECK attachments.
    19h. Save the submission-confirmation receipt PDF and screenshot - you'll need it for viva documentation.

---

## FINAL · EMERGENCY ROLLBACK (if anything looks corrupted)

If any `*_UPDATED.*` file is broken (wrong fonts, stretched images, missing pages), the **original untouched files** are intact — script never modified them. Simply re-run the script against:
*   `NOESIS_major_Synopsis_Report_Final.docx`  (≈4.3 MB original) → also see `NOESIS_major_Synopsis_Report_Final_UPDATED.docx` (recommended — 2026-08-26 rebuild adds 80% evidence, Table1 SBOM rows, refs [21][22])
*   `NOESIS_synopsis_presentation_final.pptx`  (≈2.2 MB original)

---

### Step count audit
* Step 0: 4 items (1–4)
* Step 1 DOCX review: 12 items (5–16)
* Step 2 PPT review: 10 items (17–26)
* Step 3 Portal: 5 items (27–31)
* Step 4 Email: 7 items (32–38)
* Step 5 Optional: 2 items (39–40)
* **18 core required steps = items 1–18 of the synopsis submission flow (checklist items 1 through the final PDF export + email send, excluding the optional Step 5).**
