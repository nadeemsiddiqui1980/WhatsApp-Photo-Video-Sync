# WhatsApp Photo Automation Plan (Windows 10/11, No Containers)

## Objective
Build a fully automated, zero-cost, open-source workflow that:
- collects new image messages from one WhatsApp group,
- stores them in `/photos/YYYY/MM/DD`,
- uploads them to HostingRaja via SFTP,
- records a timestamped change history,
- runs on Windows 10 and 11,
- is reusable and easy to share,
- explains exactly what each script does to build end-user trust,
- supports both automatic and manual dependency installation.
- provides a single pre-share cleanup command for secrets/runtime artifacts.

## Phases
1. Portable project bootstrap
2. Prerequisite detection and auto-install
3. WhatsApp ingestion worker
4. Date-based organization
5. SFTP upload to HostingRaja
6. Windows automation with startup recovery
7. Change-history and operational logging
8. Packaging for reuse and migration

## Key Decisions
- Native Windows runtime (no containerization)
- Selenium-based WhatsApp Web automation
- SQLite state tracking
- SFTP upload with retry/backoff
- Append-only JSONL change log
- Trust-first documentation with script-by-script behavior and side effects
- Manual dependency links and official reference articles included in docs

## Verification
1. Fresh setup on Windows 10
2. Fresh setup on Windows 11
3. End-to-end message-to-server flow
4. Duplicate prevention across restarts
5. Network failure recovery
6. Change history event validation
