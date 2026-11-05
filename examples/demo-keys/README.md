# DEMO-ONLY keys — never use for a real Profile

`DEMO-ONLY-owner.key` and `DEMO-ONLY-assessor.key` are **public** Ed25519 private keys (raw 32
bytes). They exist only so that the fictional examples in `examples/` can carry signatures that
check. Anyone who downloads the Kit has them, so a signature made with them proves nothing.

- Never sign a real Profile with them. Create your own key: `python3 conformance/arp_conform.py keygen owner.key`.
- The reference checker and the Profile Viewer flag Profiles signed with a known demo key.
- The sample feed in `regulator/sample-feed/` uses separate DEMO-ONLY keys derived from a public seed
  (`regulator/gen_sample.py`), also for demonstration only.
