# Profile Lite rules (arp-lite/0.1, draft)

**Status: release candidate 2 of arp/1.0, prepared by the MLCommons Financial Services Working Group for pilot use and comment. Not a final MLCommons standard, certification scheme or endorsement.** Profile Lite is a draft (`arp-lite/0.1`).

A Profile Lite record is one row per agent deployment, for agent inventories and supervisory data requests (`spec/profile-lite.schema.json`). Every value is as reported by the institution; the record itself is not checked against evidence. A control status of `tested_held` or `tested_not_shown_to_hold` reports the outcome recorded in a Level 2 or 3 full Profile and is only as good as that Profile. A Lite record is a starting point for a full Profile, not a substitute for one.

The key words MUST, MUST NOT and SHOULD are used as in RFC 2119. The rules are implemented in `templates/arp_lite.py check` (workbooks and CSV files) and, inside inventory snapshots, as INV-010 by `regulator/arp_feed.py` and the Supervisory dashboard demo (`spec/FEED.md`).

| Rule | Severity | Requirement |
|---|---|---|
| LITE-001 | error | The record MUST match `spec/profile-lite.schema.json`: every required field present, values from the vocabularies, `inventory_ref` of 1 to 64 letters, digits, `.`, `_` or `-` starting with a letter or digit, and control statuses from `vocab/peer-control-status.json`. |
| LITE-010 | error | An action class MUST NOT be both permitted and prohibited. |
| LITE-011 | error | A record at autonomy tier T2 MUST have `human_approval` `every_material_action` (at T2 a person approves every material action). |
| LITE-012 | error | `tier_basis` MUST NOT be `substantiated` when `human_approval` is `none` (there are no approval records to substantiate it). |
| LITE-013 | error | A record whose `profile_level` is L1, L2 or L3 MUST give the full Profile's id in `full_profile_ref`. |
| LITE-W01 | warning | When `use_case_id` is in the use-case catalogue (`vocab/use-cases.json`), `business_line` SHOULD be the line it is catalogued under. |

**Within an inventory.** `inventory_ref` MUST be unique within one institution's inventory. In snapshots this is INV-011. Tools that write one file per record (for example `arp_lite.py to-profiles`) name files from `inventory_ref`, so the pattern in LITE-001 also keeps those names safe.

**Link to the full Profile.** When a deployment has a full Profile, its `inventory_ref` equals the Profile's `subject.deployment_id`. In snapshots this is checked as part of INV-021.

**Agreement with the full Profile.** Where a full Profile exists, the fields a record shares with it (business line, use case, use case id and models when both state them, autonomy tier and tier basis, permitted and prohibited actions, accountable owner role, `human_approval` for a T2 Profile, and the peer-set control statuses) SHOULD be derived from the Profile (`arp_lite.py from-profile`). A record that knowingly differs, for example while a reissued Profile is being prepared, declares it in the optional `divergence` object: the Lite field names (a control is `controls.<control_id>`), the date the divergence began and the reason. In snapshots an undeclared difference is an error and a declared one is a labelled warning (INV-023, `spec/FEED.md` §6). The workbook and CSV templates do not yet have a `divergence` column; add it to the record in JSON.
