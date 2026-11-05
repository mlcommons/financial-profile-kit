# Release Checklist

One checklist for both the taxonomy and the Kit. Copy it into the release issue and tick each item; the release approver signs off.

## Every Kit release

- [ ] All tests pass from the unpacked release zip, in a clean environment (README, *Tests*)
- [ ] `tools/sync_skill_bundle.py --check` reports the skill bundle in step
- [ ] `tools/check_taxonomy_vocab.py` reports no identifier or assignment mismatch against the pinned taxonomy release
- [ ] `COMPATIBILITY.md` updated: supported specification and taxonomy versions, known differences
- [ ] Derived files regenerated (workbooks, Viewer, dashboard demo, sample feed)
- [ ] `tools/RELEASE-MANIFEST.txt` reviewed; the zip ships only listed files
- [ ] CHANGELOG entry; VERSION updated
- [ ] Release zip and Builder skill zip attached to the GitHub release with SHA-256 checksums
- [ ] Status wording on every file still accurate (release candidate, pilot, not certification)

## Before the public Level 1 pilot release (Stage 2)

- [ ] MLCommons leadership approves release under the MLCommons name, the Apache 2.0 licence and any contributor agreement
- [ ] Named maintainers, specification editor and release approver ([maintainers.md](maintainers.md))
- [ ] Security contact confirmed in SECURITY.md
- [ ] Software assurance package: locked dependencies with hashes, SBOM, signed checksums, offline install, reproducible release instructions
- [ ] Vulnerability handling, patch and compatibility policy published
- [ ] A pilot institution's security team accepts the Kit for internal use

## Before 1.0

- [ ] At least two independent implementations pass the conformance vectors
- [ ] The pilot cohort has produced and reviewed real Profiles
- [ ] Builder skill re-run on at least two model families, with the evidence package, measuring unsupported claims, missed conflicts, citation accuracy, redaction failures and reviewer time
- [ ] Independent adversarial review
- [ ] Evidence that different teams interpret the specification, and classify the same deployments, consistently
- [ ] Signing and validity lifecycle: external signing (KMS/HSM), key enrolment, rotation, compromise and withdrawal records
- [ ] Use-case assessment policies before Level 2 is offered publicly
- [ ] Pinned to taxonomy 1.0; `check_taxonomy_vocab.py --strict` passes
- [ ] One capability and status statement reconciled across README, landing page, memo and release notes
