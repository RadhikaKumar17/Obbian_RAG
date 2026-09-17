# Validation status

- Static checks: Ruff passed.
- Automated tests: 23 passed (API/auth/rate/body limits, parser formats, PDF OCR rejection, DOCX tables, injection routing, citation validation, index consistency).
- Local semantic embedding smoke check: BAAI/bge-small-en-v1.5 loaded and returned 384-dimensional vectors.
- Offline holdout: 25/30 cases passed (83.33%). See `offline-test.json`; five failures remain. These deterministic hash-vector results do not estimate Groq answer quality and do not meet the default 90% release gate.
- Live Groq answer evaluation: NOT RUN; Groq API credentials were not available during this build.
- Docker build: NOT RUN; no Docker engine was available.
- Public deployment: NOT COMPLETED. Deployment files are prepared; Railway authentication/project selection and service secrets are required.

A production release needs a passing live Groq report plus manual review and a deployed smoke test. This is a tested implementation baseline, not a claim of completed production acceptance.
