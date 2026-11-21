# INFRASTRUCTURE-READINESS — observed configuration (21 November 2026)

## Cloudflare (read-only authenticated checks)

- The `onesa.eu` zone is **active** with 59 DNS records at the time of readback; this says nothing about application health.
- `auth.onesa.eu`: DNS-only CNAME to the Auth0-managed custom-domain edge. **Preserve** this mapping and keep provider endpoints separate from Account UI routing.
- `account.onesa.eu`: proxied CNAME to the existing `onesa-oracle-production-api` Cloudflare Tunnel. Tunnel reported `healthy` and four connections; its config includes explicit `account.onesa.eu` ingress. This does **not** prove the Identity container or login.
- The Smart Farmer production tunnel also reported `healthy` and four connections. Backend response and DB migrations were **not tested**.
- `docs.onesa.eu`, `portal.onesa.eu`, `factory.onesa.eu`, `logistics.onesa.eu`, `farmer.onesa.eu`, `pasofi.mobile.onesa.eu` have configured DNS entries. `docs.internal.onesa.eu` and `it-infrastructure.onesa.eu` have proxied AAAA entries; their application routes require independent checks.
- Vercel's **specific project-domain endpoint** confirmed that both `factory.onesa.eu` and `logistics.onesa.eu` are verified and assigned to their correct projects; a truncated project summary had omitted them. No DNS/domain changes were needed or made.

## Vercel production source alignment (read-only)

The 11 linked frontend projects each have a `READY` production deployment, but current Vercel metadata shows an exact GitHub `main` match for 10/11. Smart Logistics main is `6b84847a31729040578f55b51d86af05343c53d6`; its latest `READY` production deployment remains at `3ce88dec748691f8a375022d27f68ae171635d81`, and no deployment was found for current main. Exact SHAs and source names are in [PORTFOLIO-INVENTORY.md](PORTFOLIO-INVENTORY.md). Frontend `READY` alone is **not** a passed E2E test.

PasoFi: project `pasofi`, production deployment `dpl_6f7ULqi5JVDMSFkQAtFWmFNcohtZ` reports READY at GitHub main SHA `51f3a0f92680e3fc00a3de51ed2529ca48ffa58f`, with the canonical domain `pasofi.mobile.onesa.eu` attached and verified. Legacy `pamofi.onesa.eu`/`pamofi.vercel.app` aliases still exist; evaluate compatibility and redirect/remove in a reviewed change. Payment and customer internet functionality remain NO-GO.

Smart Logistics: the consolidated release workflow is deliberately manual and requires the running API to serve the exact consolidated SHA, authenticated acceptance, rollback evidence and explicit promotion. None of these gates were bypassed; no deployment was promoted during this check.

Portal: Vercel project still has historic resource name `onesa-company-portal` but is linked to canonical `DruHustle/onesa-portal`. Production `ONESA_IDENTITY_UI_ORIGIN` was privately checked and exactly equals `https://account.onesa.eu`; its update predates the latest READY Portal deployment. It does **not** establish working Auth0 credentials/callbacks or live registration.

## Oracle / databases / deployments

Oracle host, Compose images, Portainer/Kubernetes workloads, per-service readiness endpoints, backups, production DB migration history, restored snapshots, permissions, TLS origin path and runtime error logs were **NOT TESTED** in this inventory. No SSH, account deletion, backup restore, router change, environment update or production deployment was executed.

## CI and operations

Public `onesa-local-ci` must use **credential-free GitHub-hosted** CI; attaching a privileged Apple Silicon Mac self-hosted runner to the public repository is forbidden. PR [#17](https://github.com/DruHustle/onesa-local-ci/pull/17) passed hosted `Portfolio release matrix / validate` and merged. Build/test success does not imply a qualified platform or app store release.

**Required to clear infrastructure gate:** exact running source/image inventory, correct protected identity grants, protected route/host TLS smoke, database migration and isolated restore evidence, app-level health and 401/403 tests, monitoring and rollback, and authenticated real-browser/provider E2E.
