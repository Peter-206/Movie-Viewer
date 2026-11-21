# Security

Only the latest source revision is maintained. There is no promise of a response time or long-term support.

Use the repository Security tab to report vulnerabilities privately if private reporting is enabled. If unavailable, open an issue asking for a private contact method without including vulnerability details. Do not post credentials, private catalogs or exploitable details publicly.

Run the host only on a trusted private network. Do not forward port 8443 from the internet. Verify pairing codes directly with the host owner, choose a unique password of at least 12 characters, and restrict Windows Firewall access to the intended private network.

Protect the app's user data directory. It contains usable bearer credentials and host private keys. SHA-256 password derivation is not a slow password-storage scheme, so use a long, randomly generated password. Do not share profiles, token files or identity folders in bug reports.

The current Windows package is unsigned. Only download releases from the intended repository, compare their SHA-256 checksums, and keep all dependency notices with the extracted app. The checksum detects changed downloads but does not replace code signing.
