# IBM Z Datathon 2026: Abstract (The Debugging Table)

Project: **OutOfRole**, a recommender that catches insider snooping on LinuxONE.
Form: hack2skill > IBM Z Datathon 2026 > Submissions > Abstract Submission.
Closes Thu Oct 15, 1:29 PM CDT. Limits shown by the form: 200 / 200 / 1024 / 1024 characters. Every box is a single-line input, so each answer below is one line.

## Challenges

AI Secured: Innovation Without Exposure

## Define the Problem statement

Insiders with valid logins snoop on patient and customer records. Rule-based alerts miss it or flood analysts. Teams need to catch access that doesn't fit a person's role, without exposing more data.

## Describe your Proposed Solution

Like Netflix learning your taste, our model learns which files and machines each employee normally uses. Access it would never suggest is flagged, and an AI on the same server explains why.

## Who specifically will be your audience

(1) Security analysts at hospitals, banks and public agencies: a short, ranked list of explained alerts instead of thousands of rule hits. (2) Privacy and compliance officers (HIPAA, GLBA): a clear record of who accessed what and why it was flagged, for audits and breach reviews. (3) Identity and access admins: least-privilege suggestions, meaning permissions a user holds but the model says they never use or need. (4) Patients and account holders: their records are watched without their data leaving the platform or going to an outside AI service. (5) Organizations already running core records on IBM Z: the model runs next to the data, so no copy goes off-platform.


## What kind of data sets will you use

(1) CMU SEI CERT Insider Threat Test Dataset r4.2 (public, CMU KiltHub): synthetic activity logs for 1,000 employees over about 17 months, covering logons, USB device use, file copies, email and web browsing, plus monthly LDAP snapshots of role and department (about 4.5 GB compressed). (2) Its answer key labels 70 malicious insiders and their 7,323 malicious actions among 32.8 million events, so we can report precision and recall instead of just showing alerts. (3) Method: Spark builds a user x resource (PC, file, website) implicit-feedback matrix, ALS trains on the early months, and the later months are replayed as a held-out "live" stream for scoring.
