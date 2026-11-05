# Builder skill trial run: ta-ob-2 (rc1)

**What this is:** one trial of the Profile Builder skill on the synthetic open-banking deployment
`ta-ob-2` of *Incredibly Trusted Bank Ltd (fictional)*, from the Working Group's September 2026
hackathon. Everything in it is fictional. It is illustrative, **not a validation of the skill**.

**Limits of this run, to fix before 1.0:**

- **It predates the final rc edit to the tier rule.** The run finished at 2026-09-27 02:01; the rule
  in `references/axis-extraction.md` §1 (T2 cannot be asserted when the approver is not shown the
  resource; record T3) was added at 02:02. The draft records **T2** although its own evidence says the
  approver "is not shown the resource". A run of the current skill should record T3.
- **The assistant and model that ran it were not recorded.** Skill 0.2 records them in
  `assurance.method` (`skeleton.py --run-on`).
- **The evidence package is not included**, so the run cannot be reproduced from the kit.
- **One model family only.** The distribution memo requires a reference run on at least two model
  families before the skill is called model-agnostic.

**Required before 1.0:** re-run the shipped skill on this package with at least two model families,
record assistant, model and version for each, ship the synthetic evidence package, and compare the
outputs field by field.

The institution name in `work/` was marked "(fictional)" on 2026-10-22; nothing else in the outputs
was changed. The earlier development run (`ta-ob-2`, not conformant) is in `history/skill-trial/`.
