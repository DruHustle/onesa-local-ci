# PORTFOLIO-INVENTORY — verified baseline (21 November 2026)

Evidence levels: **repository readback**, **Vercel deployment metadata**, **Cloudflare configuration**, **CI result**, **staging E2E**, **production E2E**, **physical/customer acceptance**. They are independent. All customer/role E2E is **NOT TESTED** by this baseline. The source SHAs below were read from each repository's `main` branch, not inferred from README files.

| Canonical repository | main commit | Main protected | Vercel production deployment source matches main? | Business E2E |
|---|---|---|---|---|
| [pasofi](https://github.com/DruHustle/pasofi) | `51f3a0f92680e3fc00a3de51ed2529ca48ffa58f` | yes | yes — READY | NOT TESTED |
| [onesa-identity](https://github.com/DruHustle/onesa-identity) | `616ab3bb9573ba17146813bb787e6f75d84f45d6` | no | N/A — Oracle service | NOT TESTED |
| [onesa-documents](https://github.com/DruHustle/onesa-documents) | `da00ba33a2dcbc8336e4843c49ca4b6bda00198a` | no | yes — READY public frontend | NOT TESTED |
| [onesa-portal](https://github.com/DruHustle/onesa-portal) | `58c87dd2288c6935a3b20e53090351e2e6b988ce` | yes | yes — READY | NOT TESTED |
| [smart-farmer](https://github.com/DruHustle/smart-farmer) | `43afdcb92d3f4e0abfb1009a610ea690438d603b` | yes | yes — READY | NOT TESTED |
| [smart-logistics](https://github.com/DruHustle/smart-logistics) | `6b84847a31729040578f55b51d86af05343c53d6` | yes | **no** — latest READY production deployment is still `3ce88dec748691f8a375022d27f68ae171635d81`; no deployment found for current main | NOT TESTED |
| [smart-factory](https://github.com/DruHustle/smart-factory) | `cf67b240e334895fd701bab16c5188e6b8b7ac26` | yes | yes — READY | NOT TESTED |
| [onesa-mobile](https://github.com/DruHustle/onesa-mobile) | `d1036667bd1d0cd7daf714ac037d1f6ea744c626` | yes | yes — READY | NOT TESTED |
| [onesa-ai-platform](https://github.com/DruHustle/onesa-ai-platform) | `d83f7ce07eb62002516594468ea52004bb5fdba8` | yes | yes — READY (main) | NOT TESTED |
| [onesa-drone](https://github.com/DruHustle/onesa-drone) | `7f0b5ee1a9b10210b738728030980f2812caeaa0` | yes | yes — READY | NOT TESTED |
| [onesa-robot](https://github.com/DruHustle/onesa-robot) | `cbff8d0f7f3de3314863d284dc284a86e9eb36a3` | yes | yes — READY | NOT TESTED |
| [onesa-local-ci](https://github.com/DruHustle/onesa-local-ci) | `abb659e1ab6cf098907cb144d9add57f839ef421` | no | N/A — CI controller | Source-gate CI only |
| [onesa-security](https://github.com/DruHustle/onesa-security) | `4f8460fe85209e54eca865a0e086de0b0db89c4a` | no | yes — READY (frontend) | NOT TESTED |

**Vercel readback (21 November):** all 11 listed frontend projects have a READY production deployment. Ten latest production deployments match their current main SHA. Smart Logistics main has advanced to `6b84847a31729040578f55b51d86af05343c53d6`, but no Vercel deployment was found for that SHA; the latest READY production deployment remains at `3ce88dec748691f8a375022d27f68ae171635d81`. Its release workflow requires the exact API revision, authenticated acceptance, rollback evidence and explicit promotion, so no deployment was promoted. This does not establish domain response, API health, authentication, transactions, data migration, or signed native binaries. Connected projects include Onesa Portal's historically named Vercel project `onesa-company-portal`; the Git repository is correctly `onesa-portal`. Onesa AI Platform [PR #353](https://github.com/DruHustle/onesa-ai-platform/pull/353) was merged to **dev**, not to the installed main release.

**Known canonical web origins:** `portal.onesa.eu`, `docs.onesa.eu` (public), `docs.internal.onesa.eu` (private), `account.onesa.eu` (Identity UI), `auth.onesa.eu` (Auth0 issuer), `pasofi.mobile.onesa.eu`, `farmer.onesa.eu`, `logistics.onesa.eu`, `factory.onesa.eu`, `platform.onesa.eu`, `drone.onesa.eu`, `robot.onesa.eu`, `mobile.onesa.eu`, and `security.onesa.eu`. Hostname configuration does **not** prove served application acceptance.

**Portal path migration remains open:** repository source still uses `onesa-company-portal-frontend/` and `onesa-company-portal-backend/`; both must become `onesa-portal-frontend/` and `onesa-portal-backend/` through coordinated path/CI/deployment migration without renaming accepted production service identities. Source baseline: [dev](https://github.com/DruHustle/onesa-portal/tree/dev) `f92be36d0ef6a828947791159c93ac321dd0ddd4`.

**External/hardware status:** The Oracle running images, DB schema/backup restore, Auth0 application registry, payment merchant approval, physical K0/G0 guest sessions, RADIUS accounting, and app-store signing/device acceptance were **not** directly qualified in this readback. Details belong in restricted evidence storage, not this public controller.

**Release scope:** see [active gate](portfolio-gates-current.json): 29 client targets and 15 additional scope gates, all independently NO-GO until observed acceptance. The file `portfolio-gates-20261115.json` is retained as historical evidence.


**21 November active changes:** The only open pull requests across the 13 in-scope repositories are Smart Farmer [#52](https://github.com/DruHustle/smart-farmer/pull/52) and stacked [#55](https://github.com/DruHustle/smart-farmer/pull/55). Source CI passed for both PR heads. Native acceptance for #52 failed; #55's exact-head native workflow remains in progress and includes a failed iOS farm login job. Neither is merge-ready until required native acceptance passes. The 13-repository default-branch source workflows are successful or explicitly skipped; skipped release gates are not PASS. The portfolio remains NO-GO pending the customer, production, mobile, and hardware evidence recorded in the final release report.
