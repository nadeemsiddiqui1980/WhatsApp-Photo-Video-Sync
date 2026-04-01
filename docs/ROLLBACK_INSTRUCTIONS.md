# Rollback Instructions (Photo-Only Stable Baseline)

This runbook provides explicit rollback steps for humans and agents.
Use it when video rollout on branch `video-code` causes reliability or performance regressions.

## Scope

- Repository: Photo-Sync (Git initialized)
- Video branch: `video-code`
- Rollback target: photo-only stable checkpoint
- Target machines: 4 GB and 8 GB RAM
- Safety: non-destructive Git workflow only

## Safety Rules

1. Never run destructive commands such as `git reset --hard`.
2. Always fetch remote branches/tags before switching.
3. Verify commit SHA before and after rollback.
4. Record rollback action in changelog or incident notes.

## Naming Convention

- Stable branch: `stable/photos-only-YYYY-MM-DD`
- Stable tag: `v1-photo-stable-YYYY-MM-DD`

## Phase A: Create Stable Checkpoint

Run from project root before continuing video development:

```powershell
git checkout video-code
git add .
git commit -m "baseline: stable photo-only checkpoint before video rollout"
git push -u origin video-code

git branch stable/photos-only-2026-03-31
git push origin stable/photos-only-2026-03-31

git tag -a v1-photo-stable-2026-03-31 -m "Photo-only stable baseline before video rollout"
git push origin v1-photo-stable-2026-03-31

git rev-parse stable/photos-only-2026-03-31
git rev-list -n 1 v1-photo-stable-2026-03-31
```

Proceed only if both SHAs are identical.

## Phase B: Rollback Decision Flow

```text
                [Issue During Video Rollout]
                          |
                +---------+----------+
                |                    |
         [Need quick recovery]   [Need immutable known-good]
                |                    |
 checkout stable/photos-only...   checkout tag v1-photo-stable...
                |                    |
         continue operations     create recovery branch and continue
```

```text
[Stable Commit]
    |
    +--> stable/photos-only-2026-03-31   (recovery branch)
    |
    +--> v1-photo-stable-2026-03-31      (immutable reference)
```

## Phase C: Execute Rollback

```powershell
git fetch --all --tags --prune

# Option 1: Recover fast on stable branch
git checkout stable/photos-only-2026-03-31

# Option 2: Recover from immutable tag
git checkout v1-photo-stable-2026-03-31
git checkout -b recovery/from-photo-stable-2026-03-31

git rev-parse HEAD
```

## Phase D: Post-Rollback Validation

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\preflight.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run_pipeline.ps1
```

Validate:

1. Photo collection still works.
2. SFTP upload works.
3. No new video-path errors in logs.
4. Machine remains responsive.

Primary files to inspect:

- `logs/pipeline.log`
- `state/change_history.jsonl`

## Agent Checklist

1. Confirm active branch is `video-code` before development work.
2. Confirm stable branch/tag exist and SHA matches.
3. Fetch all remotes and tags.
4. Switch to selected rollback target.
5. Run preflight and runtime checks.
6. Validate logs and event health.
7. Record rollback action.
