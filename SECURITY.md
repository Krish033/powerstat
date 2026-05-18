# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅ Yes     |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities as public GitHub Issues.**

To report a security vulnerability, email the maintainers at:

> **security@powerstats.example** *(replace with actual contact)*

Or use [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) if available on the repository.

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Potential impact assessment
- Any suggested fixes (optional)

### Response Timeline

- **Acknowledgement**: within 48 hours
- **Initial assessment**: within 7 days
- **Patch / advisory**: within 30 days for confirmed vulnerabilities

## Security Considerations

PowerStats collects **local system telemetry only**. No data is ever transmitted to external servers. Key security properties:

- All data is stored in `~/.local/share/powerstats.db` (user-owned SQLite).
- Configuration is stored in `~/.config/powerstats/config.json`.
- The daemon runs as the **current user** (not root).
- Intel RAPL access gracefully degrades without root — no privilege escalation.
- The "Force Stop" feature uses `kill -9` only after explicit user confirmation via GTK dialog.
- All subprocess calls use explicit argument lists (no shell=True).
