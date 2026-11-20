# MOBILE-STORE-READINESS — 20 November 2026

**No iOS or Android app is declared store-submission-ready by this inventory.** The eight product families below are target scope, **not** proof that every native target exists, is signed, or passed installed-device E2E.

| Product | Target iOS | Target Android | Signed artifact / real-device OIDC / store review |
|---|---|---|---|
| PasoFi | REQUIRED | REQUIRED | NOT TESTED / NO-GO |
| Smart Farmer | REQUIRED | REQUIRED | NOT TESTED / NO-GO; [iOS callback issue #50](https://github.com/DruHustle/smart-farmer/issues/50) |
| Smart Logistics | VERIFY native implementation | VERIFY native implementation | NOT TESTED / NO-GO |
| Smart Factory | VERIFY native implementation | VERIFY native implementation | NOT TESTED / NO-GO |
| Onesa Mobile | REQUIRED | REQUIRED | NOT TESTED / NO-GO; telecom pilot scope only |
| Onesa AI Platform | VERIFY native implementation | VERIFY native implementation | NOT TESTED / NO-GO |
| Onesa Drone | REQUIRED | REQUIRED | NOT TESTED / NO-GO; [iOS callback issue #99](https://github.com/DruHustle/onesa-drone/issues/99) |
| Onesa Robot | VERIFY native implementation | VERIFY native implementation | NOT TESTED / NO-GO; physical control not authorized |

## Store and installed-device release gates

For each *actual* native target, inventory application/bundle ID, exact signed Git SHA, framework, target SDK and Xcode version, version codes, signing/entitlements, associated domains and app links, privacy manifest/Data Safety, support/account deletion, legal listings, reviewer access, and policies currently applicable to that developer account. Do **not** infer compliance with Apple or Google policy from source compilation.

Require observed first install → system-browser Auth0 Code + PKCE → email verification/MFA → product grant → correct deep-link/Universal Link return → real API/backend → critical business workflow → logout/revocation → restart/recovery/offline and permission-denial flows. Verify on representative iPhone/iPad and Android devices in addition to simulators. Retain signed IPA/TestFlight and AAB/Play internal test receipts privately.

**Separation:** GitHub `native`/simulator CI, signing, device installation, TestFlight/Play internal testing, store review, and public publication are distinct evidence levels. Never mark an unsigned simulator archive as an app-store submission. No store credentials, release uploads, physical device installs, or public submissions were accessed/completed during this effort.

The current [29-client release gate](portfolio-gates-current.json) is NO-GO. Public store submission always requires separate owner authorization. Carrier/satellite provisioning, physical drone flight, and robot actuation remain separately uncommissioned scope.
