---
title: "OutOfRole: Getting the Data"
subtitle: "The Debugging Table, IBM Z Datathon 2026"
date: "October 15, 2026"
---

# What we use

The **CERT Insider Threat Test Dataset, release r4.2**, published by Carnegie Mellon's Software Engineering Institute. It is synthetic activity logs for **1,000 employees** from January 2010 to May 2011, with **70 labeled malicious insiders** across three scenarios. We also need the **answer key**, which names those insiders and their exact malicious events.

- Dataset page: <https://kilthub.cmu.edu/articles/dataset/Insider_Threat_Test_Dataset/12841247>
- Citation DOI: 10.1184/R1/12841247

Only download **r4.2** and **answers**. The other releases (r1 to r6.2) are not needed.

# Files and direct links

| File | Size | Direct download | MD5 |
|----------------|--------|----------------------------|--------------------------------|
| r4.2.tar.bz2 | 4.82 GB | <https://ndownloader.figshare.com/files/24856766> | cf64caa378acb77cd0c608a5576d998c |
| answers.tar.bz2 | 1.25 MB | <https://ndownloader.figshare.com/files/24857828> | c0c96eaa06915e417504f932756f58d8 |
| README (SEI) | 1.4 KB | <https://ndownloader.figshare.com/files/24860765> | 3168963335887132baccc4179f46c467 |

Links and checksums come from the figshare API for article 12841247.

# Download on the LinuxONE VM (recommended)

Download straight onto our LinuxONE Community Cloud VM so the 4.8 GB never has to be uploaded from a laptop. After SSH-ing in:

```bash
mkdir -p ~/outofrole/data/raw && cd ~/outofrole/data/raw
curl -L -C - -o r4.2.tar.bz2    https://ndownloader.figshare.com/files/24856766
curl -L -C - -o answers.tar.bz2 https://ndownloader.figshare.com/files/24857828
md5sum r4.2.tar.bz2 answers.tar.bz2      # compare with the table above
mkdir -p ../r4.2 ../answers
tar -xjf r4.2.tar.bz2    -C ../r4.2
tar -xjf answers.tar.bz2 -C ../answers
```

`-C -` resumes an interrupted download, so rerun the same line if the connection drops. On a Mac, use `md5 -q` instead of `md5sum`. Expect roughly 10 to 15 minutes to download at 7 MB/s. The archive plus the extracted files need about **20 GB of free disk** (`df -h ~` to check); if the VM is short, extract only the core files: `tar -xjf r4.2.tar.bz2 -C ../r4.2 --wildcards "*logon.csv" "*device.csv" "*file.csv" "*LDAP*"`.

# What is inside

**Dataset** (`r4.2/r4.2/` after extracting; 15 GB in total):

| File | Size | Rows | Columns | Use |
|---|---|---|---|---|
| logon.csv | 58.5 MB | 854,859 | id, date, user, pc, activity | Core: who logs into which PC, and when |
| device.csv | 29.0 MB | 405,380 | id, date, user, pc, activity | Core: USB connect and disconnect |
| file.csv | 193 MB | 445,581 | id, date, user, pc, filename, content | Core: files copied to USB |
| LDAP/ (18 files) | 0.1 MB each | 1 file per month, Dec 2009 to May 2011 | employee_name, user_id, email, role, business_unit, functional_unit, department, team, supervisor | Core: role and department for peer groups |
| psychometric.csv | 45 KB | 1,000 | employee_name, user_id, O, C, E, A, N | Skip: personality scores |
| email.csv | 1.36 GB | | id, date, user, pc, to, cc, bcc, from, size, attachments, content | Stretch only |
| http.csv | 14.5 GB | | id, date, user, pc, url, content | Stretch only; too big for a first pass |
| readme.txt, license.txt | small | | | Read license.txt once (see below) |


**Answer key** (`answers/answers/`):

- `insiders.csv`: one row per insider: dataset, scenario, details file, user ID, start and end time. Filter to `dataset == 4.2` for our 70 rows.
- `r4.2-1/`, `r4.2-2/`, `r4.2-3/`: one file per insider (30, 30 and 10 files) listing that insider's malicious events. These are **not proper CSV**: rows vary in length and the first column says which log the row came from.
- `scenarios.txt`: plain-English descriptions. Scenario 1 is after-hours USB use plus uploads to wikileaks.org; scenario 2 is job hunting followed by heavy thumb-drive data theft; scenario 3 is a disgruntled system administrator with a keylogger.

# Rules and housekeeping

- **Downloading data before the event is allowed.**
- **Never commit the data to GitHub.** Add `data/` to `.gitignore` in our repo. The final submission only needs the code link.
- Start the pipeline with the logon, device and file logs. The web-browsing log is by far the largest file; use it only if time allows.
- Credit the dataset in the README and video, with the page link and DOI above.
- **Do not pass copies around.** Each teammate or VM downloads from the CMU links above.
- If we show actual rows in the video or README, add the notice "Copyright 2011 ExactData, LLC, All Rights Reserved." Summaries and charts of the data need no notice.
