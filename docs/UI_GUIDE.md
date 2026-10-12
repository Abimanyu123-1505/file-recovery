# EXT4 Deleted File Recovery Workbench – User Guide for Officers

## Audience
This guide is written for police officers, investigators, and case handlers who need to recover deleted files from an EXT4 storage image without requiring a digital forensics or computer science background.

---

## Safety and Evidence Handling
- **Read-Only Evidence Guarantee:** The Workbench opens your original evidence image in read-only mode (`rb`). It never writes to, modifies, converts, or alters the source image under any circumstances.
- **Integrity Fingerprints (SHA-256):** Before analysis begins, the Workbench calculates and logs a cryptographic digital fingerprint (SHA-256) of your evidence image. Immediately upon finishing analysis, it calculates the fingerprint again. If the two fingerprints match, the report confirms: *"Evidence unchanged during analysis"*.
- **Integrity Safeguard:** If the before and after fingerprints do not match, the Workbench halts the workflow, displays a high-visibility warning banner, and locks file recovery and report generation to protect the integrity of your investigation.

---

## Quick-Start: 6-Step Workflow

### Step 1: Case Details
1. **Case Number (Required):** Enter your official case reference (e.g., `CR/2026/0412`).
2. **Case Title:** Brief subject or description of the case.
3. **Examiner Information:** Enter your name, rank/badge number, and department. These details will automatically populate the formal examiner declaration.
4. **Authority:** Enter the court warrant number, PACE authority, or requesting officer's name.
5. Click **"Save and continue"**.

### Step 2: Select Evidence
1. **Evidence File Path:** Provide the full path to your raw disk or partition image (e.g., `C:\Evidence\case-0412\disk.img` or `/mnt/evidence/disk.raw`). Supported formats include `.img`, `.dd`, `.raw`, `.bin`, and `.e01`.
2. Click **"Check file"**. The Workbench verifies that the file exists, is accessible with read permissions, and contains an EXT4 file system.
3. Once the green confirmation appears, click **"Start analysis"**.

### Step 3: Analysis
The analysis pipeline runs automatically through four stages:
1. **Checking the evidence copy:** Computes the pre-analysis SHA-256 fingerprint.
2. **Reading the file system:** Opens the EXT4 superblock and block groups.
3. **Looking for deleted files:** Scans directory records, inode tables, and unallocated blocks for recoverable deleted files.
4. **Final integrity check:** Recomputes the SHA-256 fingerprint and confirms that the evidence file was not altered.

You can monitor the progress bar and real-time status. If needed, click **"Cancel analysis"** safely at any time. When complete, click **"Review deleted files"**.

### Step 4: Review Deleted Files
1. **Overview & Filters:** View the total number of deleted files found and the number eligible for recovery. Filter by category (*All*, *Documents*, *Archives*, *Images*, *Other*) or use the search box.
2. **Name Confidence Indicators:**
   - **Name confirmed (Green):** The file name was recovered from a surviving directory entry. This is the most reliable source.
   - **Name uncertain (Amber):** The file name was identified from unallocated storage remnants. It may not be the original file name.
   - **Original name not available (Neutral):** No surviving name record could be found.
3. **Selection:** Check the boxes for the files you wish to recover, or click **"Select all recoverable"**.
4. Click **"Recover selected files"**.

### Step 5: Recover
1. **Confirmation:** Review the list of selected files and the destination folder path (`case/scan_{id}/recovered`).
2. Click **"Start recovery"** and confirm in the dialog prompt.
3. **Derived Copies:** Recovered files are extracted as new, independent files into the output folder. They are assigned finding references (e.g., `FIND-001`, `FIND-002`) and exhibit IDs.
4. **Results Table:** Review the recovery status:
   - **Fully recovered (Green):** All recorded blocks were extracted.
   - **Partly recovered (Amber):** Some data was missing or truncated.
   - **Could not be recovered (Red):** The recorded blocks could not be read.
5. Each recovered file has its individual SHA-256 fingerprint computed and displayed with a 1-click **"Copy"** button. If two recovered files share the exact same fingerprint, a duplicate notice is shown.
6. Click **"Generate report"**.

### Step 6: Report
1. **Report Type:**
   - **Investigator Summary Report:** Clear, plain-language 3–5 page summary suitable for briefings, SIOs, and courtroom presentation.
   - **Full Forensic Report:** Comprehensive report including full technical methodology, directory structures, and raw metadata appendices.
2. **Checklist:** Review the pre-flight checklist. Any missing details (such as examiner name or authority) will display an amber advisory note.
3. **Examiner Declaration:** Review your name, rank, date, and confirm the statutory statement:
   *"I confirm the contents are accurate to the best of my knowledge."*
4. **Preview:** Click **"Load preview"** to inspect the report contents directly on screen.
5. **Download Options:**
   - **Download Word document (.docx):** Forensic-grade report with tables, callout boxes, and signature blocks formatted for immediate submission or conversion to PDF via Word/LibreOffice.
   - **Data export (.json):** Machine-readable export for digital forensic units (DFU) and laboratory archival.

---

## Plain-Language Terminology Reference

| Technical Term | Plain-Language Label | Explanation |
| :--- | :--- | :--- |
| **Inode** | File record | An internal entry in the file system that stores information about a file, such as its size and storage locations. |
| **SHA-256 / Hash** | Digital fingerprint | A unique mathematical code calculated from the file contents. Any change to the file produces a different code. |
| **Integrity OK** | Evidence unchanged during analysis | The digital fingerprint before and after analysis was identical, confirming the original evidence was not altered. |
| **Deletion Time** | Date deleted | The recorded date and time when the file was removed, according to the file system. |
| **Extent Recovery** | Recovered from stored data | The file data was read directly from the areas of storage where it was originally written. |
| **Slack Space** | Leftover data | Small amounts of data that may remain in storage space that was previously used by a deleted file. |
| **Journal** | File system activity log | An internal log kept by EXT4 that records recent changes, used to verify file system consistency. |
| **PyTSK3 Cross-check** | Independent verification | The finding was confirmed using a separate forensic analysis tool (The Sleuth Kit). |

---

## Running the Application Locally

### Starting the Backend
```powershell
# From the project root:
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```
The API documentation is accessible at `http://127.0.0.1:8000/docs`.

### Starting the Frontend
```powershell
# From the frontend/ directory:
npm run dev
```
The Workbench will open in your web browser at `http://localhost:5173`.
