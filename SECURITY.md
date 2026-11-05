# Reporting a problem

**Contact (to be confirmed by MLCommons): participation@mlcommons.org.** Please mark the subject
"ARP Kit security" or "ARP Kit checker bug".

Report privately, before publishing:
- a Profile or snapshot that the checker accepts but should reject, or the reverse (include the file);
- a way to alter a signed Profile or snapshot without the signature check failing;
- content that runs code or loads anything from the network when opened in the Profile Viewer or the
  Supervisory dashboard demo;
- a way for a tool to write outside the folder you gave it, or to overwrite files without asking.

Please do not include real evidence, real customer data or private keys in a report. We will
acknowledge a report within 5 working days (target, to be confirmed).

The Kit is a release candidate for pilots. Conformance is not certification, and signatures prove
possession of a key, not identity (`spec/SPEC.md` §2, §7). Do not rely on the Kit alone for
decisions about real deployments.
