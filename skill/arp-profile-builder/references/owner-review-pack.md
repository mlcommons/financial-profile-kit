# Owner review pack (write to <workdir>/owner-review.md)

1. **What you are being asked to sign.** One paragraph: the bounded claim, and that a Level 1
   signature attests "this is what we believe we have deployed". It asserts nothing tested.
2. **The claim at a glance.** Tier, approval quality, ODD in one line, permitted and
   prohibited classes, controls present.
3. **Open conflicts.** A table: field, what the document says, what the configuration says,
   both citations. For each, the owner resolves (and records why), accepts, or leaves open.
   Open conflicts stay on the issued Profile as findings.
4. **Absent fields.** Each field no artifact could establish, and which artifact would.
5. **Decisions before signing.** Validity window (`valid_from`, `valid_until`), issue time,
   any risk acceptances, and whether the Profile should go to Level 2 testing.
6. **How to sign.** The command, and that any later edit voids the signature.
7. **How this draft was compiled.** The skill version and the assistant, model and version that
   ran it (as in `assurance.method`), and every artifact class you corrected after `manifest.py`
   proposed it: file, proposed class, your class, and why.
8. **Personal data in the evidence.** Every evidence file that contains customer, account,
   transaction or staff identifiers. None of them is quoted in the Profile; the owner decides who
   may see the evidence package itself.
