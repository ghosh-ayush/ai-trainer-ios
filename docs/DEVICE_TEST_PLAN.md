# Native validation checklist

This is a test plan, not a report of tests already performed. Record device model, iOS version, build commit, configuration, and pass/fail evidence for each run. Use synthetic records; do not commit personal health data.

## P1 end-to-end

1. Fresh install: optional profile fields remain absent. An unsupported equipment/time combination does not fabricate a program. Release cannot enable the fixture library.
2. Debug: accept the fixture, explicitly set known loads and available steps, check in, and start. Log working, warm-up and extra sets with unknown and known RIR.
3. Save a set and immediately background/terminate/relaunch. Verify that the accepted prescription, actual record and rest-end time survive without duplication.
4. Pause and resume. End early for time. Verify the summary distinguishes original work, accepted work, recorded sets and omitted work.
5. After qualifying synthetic exposures, request a proposal. Verify before/after details. Accept once; repeated application must not increment again.
6. Correct an evidence set before acceptance. Verify the pending proposal expires. Correct a record with a stale revision and resolve the conflict explicitly.
7. Preview a shorter workout and an eligible substitute. Verify rest does not shrink, load does not transfer, and the following original session is restored after the temporary override.
8. Report pain or exclude an active exercise. Verify pause and suppression of conflicting guidance. Do not characterize this as clinical triage.
9. Turn Airplane Mode on. Repeat the entire logging flow. Export JSON locally; verify it contains no fabricated sensor data. Delete a session and then all data. Verify no app restore mechanism resurrects it.
10. Test protected-data startup while locked, low storage, interrupted writes, corrupt snapshot, Dynamic Type, VoiceOver, small displays and dark mode. Verify errors do not silently discard saved state.

## P0/P2 physical camera experiment

Record mounting angle, visible joints, distance, lighting, mirrors, multiple people, occlusion, clothing, left/right orientation and duration. Compare the experimental right-arm count to independently annotated video only under separate explicit recording consent. The app itself does not record video.

Check permission denial, camera interruption, leaving the view while the permission dialog is open, backgrounding, returning, restart/reset, thermal changes and battery use. Confirm that dropout cannot complete a partial rep and that camera outputs never become confirmed SetLog records. Report error and dropout metrics rather than declaring accuracy from a few successful reps.

## P3 HealthKit

Use a development device with synthetic Health data. Test all/partial/no readable samples, denied or limited permissions, stale records and multiple sources. Verify permission completion is not labeled access granted. Check that overlapping sleep samples are not aggregated into a fabricated duration or readiness score. Confirm clearing/exiting removes the local display and no plan changes occur.

## P4 meals

Enter a portion with explicit zeros and unknown inputs; unknown inputs should require completion rather than becoming zero. Scale a saved portion, edit an old meal, attempt a stale edit, inspect correction records in export, and delete the meal. Confirm P1 progression is unchanged by nutrition records. Check midnight and time-zone changes; historic travel regrouping is outside current coverage.

## Release blockers

Approved exercise/instruction/template content; reviewed concerns flow and privacy policy; production persistence/migration/sync design; robust data-retention controls; a real training/program coverage matrix; signed physical-device builds; UI/accessibility testing; app icons and distribution assets; validated P2/P3 policies; and phase-specific product/accuracy gates from the specification. Do not mark a phase complete solely because its screen exists.
