# PASOFI-COMMERCIAL-READINESS — 21 November 2026

**Commercial status: NO-GO for live electronic payments and for the six tracked hotspot-site gates.** This report separates verified *frontend source/deployment metadata* from real paid internet access. Customer, merchant, Oracle DB, RADIUS and physical guest acceptance were **not executed** in this session.

## Verified baseline

- Canonical customer origin: `https://pasofi.mobile.onesa.eu` (Vercel project domain verified).
- Vercel production deployment `dpl_6f7ULqi5JVDMSFkQAtFWmFNcohtZ` is `READY`; deployed source `51f3a0f92680e3fc00a3de51ed2529ca48ffa58f` matches GitHub `main` exactly.
- Historical frontend mismatch documented in [PasoFi #144](https://github.com/DruHustle/pasofi/issues/144) is no longer present in the connected Vercel readback. Backend schema/migrations, customer receipts and rollback remain unqualified.
- Vercel still records legacy `pamofi` aliases; they are not the canonical customer origin. Do not silently delete active customer entrypoints without an approved redirect/rollback plan.


## Read-only router resource observation (21 November)

The existing admin terminal sessions for **K0**, **K1** and **G0** responded to `/system resource print`. No configuration, interfaces, firewall, HotSpot, or RADIUS settings were changed.

| Router | Board | RouterOS | CPU load at snapshot | Free memory | Free disk |
|---|---|---|---:|---:|---:|
| K0 | hEX | 7.25.1 | 0% | 191.8 / 256 MiB | 4.8 / 16 MiB |
| K1 | hAP lite | 7.25.1 | 32% | 9.1 / 32 MiB | 7.3 / 16 MiB |
| G0 | hAP lite | 7.25.1 | 30% | 7.7 / 32 MiB | 6.7 / 16 MiB |

G0's live status indicator showed 0 bps transmit and receive during this brief read. These management/resource observations do **not** verify the guest bridge, captive portal, payment, RADIUS authorization/accounting, or internet access; the six site gates remain NOT TESTED.

## Independent site acceptance

| Site | Intended scope / network understanding from open issue | Payment + physical acceptance |
|---|---|---|
| K0 | Kuwadzana primary MikroTik hEX hotspot gateway / RADIUS NAS | NO-GO — NOT TESTED |
| K1 | Kuwadzana downstream hAP lite access point; verify bridge and guest transit | NO-GO — NOT TESTED |
| G0 | Goromonzi primary MikroTik hAP lite HotSpot / NAS; reported wired G0 → G2 → G3 | NO-GO — NOT TESTED |
| G1 | Future/uncommissioned downstream component per issue #142 | NO-GO — NOT TESTED |
| G2 | Downstream Mercusys radio/AP management, isolation and bridge required | NO-GO — NOT TESTED |
| G3 | Downstream Mercusys radio/AP management, isolation and bridge required | NO-GO — NOT TESTED |

**Payment channel gates:** Stripe web card — NO-GO; Apple Pay iPhone — NO-GO; Google Pay Android — NO-GO. Cash/paid voucher is a distinct channel and must pass independently. Do not infer merchant settlement or paid access from SDK availability or redirect success.

## Full real-customer acceptance contract

1. Off-device encrypted router recovery and observed physical port/bridge/VLAN/walled-garden baseline. No silent changes to live firewall/HotSpot/NAT.
2. One test device with mobile data **off** joins real customer SSID. No general Internet works before entitlement; captive portal/package/pricing appear.
3. A legitimate provider-confirmed **sandbox** payment, or authorized and audited paid voucher sale, yields **exactly one** entitlement; failed/duplicate/reversed payments yield none.
4. Original NAS sends authenticated RADIUS Access-Request; valid entitlement returns Access-Accept, invalid/expired returns reject; session authenticates and browses real internet.
5. Router and backend record Start/Interim/Stop, upload/download bytes, rate limits and expiry. Test refund/revocation, router restart, outage, roaming/cross-site voucher and recovery.
6. Record a separate explicit GO decision for `Site × Router × Package × Payment method × Device`, backed by private logs/signed receipt, redacted screenshots, actual counters and a tested rollback.

Open [PasoFi #142](https://github.com/DruHustle/pasofi/issues/142) and [PasoFi #144](https://github.com/DruHustle/pasofi/issues/144) remain blocking. Physical authorized site operation, merchant activation and Oracle backups require their own approval and qualified evidence. No real customer was charged and no router was reconfigured here.
