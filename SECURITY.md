# Security Policy

## Supported Versions

Preceptly is currently in an early development stage (hackathon/early-stage project). At this time, only the `main` branch is actively maintained and supported.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue in Preceptly, please report it responsibly.

### How to Report

**Please do NOT create a public GitHub issue** for security vulnerabilities, as this could expose sensitive information.

Instead, please use one of the following methods:

1. **GitHub Security Advisories (Recommended)**
   - Go to the repository's Security tab
   - Click on "Report a vulnerability"
   - Create a private security advisory
   - This ensures that the issue is handled confidentially

### Information to Include

When reporting a vulnerability, please provide:

- A clear description of the vulnerability
- Steps to reproduce the issue
- The affected version/commit (if applicable)
- Potential impact and severity assessment
- Any suggested fixes or mitigations (if available)
- Your environment details (OS, Python version, Django version, etc.)

## Response Process

- **Acknowledgment**: We will acknowledge receipt of your report within 48 hours
- **Initial Assessment**: We will provide an initial assessment within 5 business days
- **Resolution**: We aim to address security issues promptly, with critical vulnerabilities prioritized
- **Disclosure**: Security issues will be disclosed responsibly after a fix is available, following coordinated disclosure practices

All security-related information will be handled confidentially and will not be shared publicly until a fix is available.

## LLM & Privacy Policy

- **PII Sanitizer**: Prompts are sanitized before AI usage (full name, address, email, phone, tax_id, dob, medical_info → `[REDACTED]`).
- **Mock Mode Default**: `MOCK_LLM=1` is enabled for demos and CI to avoid external LLM traffic unless explicitly disabled.
- **No Prompt Logs in Demo Mode**: User prompts/responses are not persisted when running with mock mode.
- **Sanitized Context Only**: Lesson plans are generated from sanitized context to reduce exposure of personal data.
- **Opt-in for Production**: Live AI calls require setting `LLM_API_KEY` and disabling `MOCK_LLM` explicitly.
- **Hackathon Demos**: During hackathon demos (e.g., CodeCraze Hackathon), Preceptly runs in `MOCK_LLM` mode with synthetic data only; no real student data or real LLM calls are used.

## Security Best Practices

When using Preceptly:

- **Never commit sensitive data** (API keys, passwords, real student data) to the repository
- **Use environment variables** for configuration (see `docs/RAILWAY_DEPLOYMENT.md`)
- **Keep dependencies updated** (Dependabot is configured to help with this)
- **Follow deployment guidelines** in `docs/RAILWAY_DEPLOYMENT.md` for production environments
- **Use strong passwords** and enable authentication features as appropriate
- **No hardcoded secrets**: `SECRET_KEY`, database credentials, and LLM keys are expected from environment variables; defaults in the repo are demo-only
- **Secure defaults**: In Produktion niemals mit `DEBUG=True` oder leeren `ALLOWED_HOSTS` betreiben; aktivieren Sie bei Bedarf `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` via ENV.

## Dependency Scanning

CI runs `pip-audit` to check for known vulnerabilities. If a vulnerability is found in a system or transitive package (e.g. pip itself) that cannot be fixed by upgrading our direct dependencies, add a justified ignore in CI and document it here. Do not ignore application dependency vulnerabilities without a clear mitigation plan.

### pip-audit: CVE-2026-3219 (pip) — RESOLVED

- **What it is:** pip misclassifies files that are valid **both as a tar archive and a ZIP archive** (so-called polyglot archives), always treating them as ZIP. This can lead to installing unexpected file contents when a package archive is such a polyglot.
- **Affected version:** pip < 26.1.
- **Fix version:** pip 26.1 (released 2026-07-02).
- **Resolution:** CI now pins `pip>=26.1.2` in the install step, which also fixes PYSEC-2026-196 (pip < 26.1.2) and CVE-2026-6357 (pip < 26.1). The `--ignore-vuln CVE-2026-3219` flag has been removed from the audit command.

### pip-audit: CVE-2026-4539 (Pygments)

- **What it is:** **Regular Expression Denial of Service (ReDoS)** in Pygments’ **AdlLexer** (GUID/ID regex in `archetype.py`). An attacker who can force parsing of malicious input through that lexer could cause high CPU use. Advisories often rate this **Low** because exploitation typically requires **local** or **controlled** input paths, not generic internet-facing RCE.
- **Issue:** Affected versions include PyPI’s latest **2.19.2** (metadata version string unchanged until the next release).
- **Upstream fix:** [pygments/pygments#3064](https://github.com/pygments/pygments/pull/3064) (commit `24b8aa76…`).
- **Our mitigation:**
  1. **`requirements.txt` pins Pygments from that git revision** so installs get the **patched source**, even though the package still self-reports version **2.19.2**.
  2. **CI** keeps `pip-audit --ignore-vuln CVE-2026-4539` until **Pygments > 2.19.2** exists on PyPI (otherwise the audit tool flags the metadata version only).
- **Preceptly:** The app does not use that lexer on untrusted user content; residual risk is mostly transitive/tooling (e.g. highlighting in dev dependencies).
- **Follow-up:** When PyPI publishes a release **> 2.19.2**, switch to `Pygments==<version>`, remove the git pin, and **remove** the `pip-audit` ignore for this CVE.

### pip-audit: Twisted 26.4.0 (via Daphne) — OPEN, stand 24.10.2026

Twisted ist keine direkte Abhängigkeit, sondern kommt über **Daphne** (der Webserver). Es gibt kein stabiles Release mit
den Korrekturen: Sie stehen erst in `26.10.0rc1` (Vorabversion), eine Lücke hat gar keinen Fix. Entscheidung von Andreas
am 24.10.2026: ignorieren mit Begründung, nicht auf eine Vorabversion des produktiven Webservers wechseln.

| Lücke | Betrifft | Nutzt Preceptly das? | Umgang |
|---|---|---|---|
| CVE-2026-106454 | `twisted.mail.imap4` (ReDoS bei IMAP-LIST) | Nein, kein IMAP-Server | dauerhaft ignoriert (kein Fix verfügbar) |
| CVE-2026-115774 | IMAP4-Server (Endlosschleife) | Nein | ignoriert |
| CVE-2026-115778 | `twisted.conch` Telnet (Speicher) | Nein | ignoriert |
| CVE-2026-115775 | XML-Element-Stream (Speicher) | Nein | ignoriert |
| CVE-2026-115776 | `twisted.words` IRC-Server (Speicher) | Nein | ignoriert |
| CVE-2026-83813 | `twisted.names` DNS-Client (gefälschte DNS-Antworten, Cache-Poisoning); am 28.10.2026 gemeldet | Nein: weder Daphne noch Autobahn, Channels oder der Anwendungscode nutzen `twisted.names`, Twisted löst Namen über seinen Thread-Resolver auf | ignoriert |
| CVE-2026-115877 | `twisted.web.http.HTTPChannel`: bloßes CR oder LF im Header-Wert wird nicht abgelehnt (Request-Smuggling) | **Ja**, Daphne nutzt `twisted.web.http` | **befristet** ignoriert |

- **Zu CVE-2026-115877:** Ein Angriff braucht einen vorgeschalteten Proxy, der denselben Zeilenumbruch anders deutet.
  Preceptly läuft hinter einem solchen Proxy; die Einschätzung des Restrisikos steht im nicht öffentlichen Sicherheitsplan.
- **Nächster Schritt:** Sobald **Twisted 26.10.0 (stabil)** auf PyPI steht: Daphne mit der neuen Version testen, die
  Ignores für 115774, 115775, 115776, 115778, 83813 und 115877 aus `.github/workflows/ci.yml` entfernen und prüfen, ob 106454
  inzwischen einen Fix hat. Bis dahin bei jedem Dependabot-Hinweis zu Twisted/Daphne nachsehen.
- **Zusätzlich am 24.10.2026 behoben (kein Ignore nötig):** `pillow` 12.3.0 → 13.0.0 (37 Meldungen), `pypdf` 6.20.0 → 6.21.2
  (9 Meldungen), `certifi` 2026.7.22 → 2026.10.19 (CA-Bundle mit kompromittiertem emSign-Root).

## Acknowledgments

We appreciate the security research community's efforts to help keep Preceptly secure. Responsible disclosure helps protect all users of the application.

