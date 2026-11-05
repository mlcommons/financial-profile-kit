# What conformance means, and what it does not

**Status:** release candidate 2 of arp/1.0, prepared by the MLCommons Financial Services Working
Group for pilot use and comment. Not a final MLCommons standard, certification scheme or
endorsement. Field names and rules may change before 1.0.

When the reference checker (`conformance/arp_conform.py`) or the Profile Viewer says a Profile
is **conformant** ("well-formed" in the Viewer), it means this and only this:

* The file is strict JSON and follows the Profile schema and rules ARP-001 to ARP-100 in
  `spec/SPEC.md`, release candidate `arp/1.0-rc2`.
* Its labels match its evidence: the headline level is the weakest axis, nothing untested is
  called `measured`, every claim field says where it came from, and every citation points to an
  item in the evidence manifest.
* The standard disclosures are present, for example "asserted by the institution and not
  tested" and "not comparable with other deployments".
* Open conflicts, contradicted claims and failed floors are carried as findings, and a failed
  floor stops the Profile from being issued.
* An issued Profile is signed by its accountable owner (and by its independent assessor for any
  Level 3 axis), and those signatures are valid for this exact file.

Conformance does **not** mean:

* that the claims are true;
* that the tests were adequate, or that enough of the Profile was tested;
* that the agent is safe, reliable, or compliant with any law or regulation;
* that the people who signed are who they say they are (a valid signature shows only that the
  signer held the key);
* that MLCommons, the Working Group or anyone else has reviewed the Profile.

Two cautions for anyone receiving a Profile:

* **A Level 1 Profile has not been tested.** It records what the institution believes it has
  deployed, compiled from its own documents and configuration. It is not comparable with any
  other Profile.
* **Warnings matter.** A conformant Profile can still carry warnings, for example a signature
  made with one of the published DEMO-ONLY keys in `examples/demo-keys/` (ARP-092), which proves
  nothing, or a Profile checked after its expiry date (ARP-080 with `--as-of`).

Where the reference checker and another implementation (including the Viewer) disagree, the
reference checker's result governs until the disagreement is fixed. Where the checker and
`spec/SPEC.md` disagree, the specification governs and the checker has a bug.
