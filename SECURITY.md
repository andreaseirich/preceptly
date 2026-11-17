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

### pip-audit: CVE-2026-4539 (Pygments) — RESOLVED 17.11.2026

- **What it is:** **Regular Expression Denial of Service (ReDoS)** in Pygments' **AdlLexer** (GUID/ID regex in `archetype.py`). An attacker who can force parsing of malicious input through that lexer could cause high CPU use; advisories rate it **Low**.
- **Affected:** Pygments up to 2.19.2. **Fixed in 2.20.0** (on PyPI since 2026-03-29); the current release is 2.21.0.
- **Resolution:** `requirements.txt` pins `Pygments==2.21.0`. This replaces the git-revision pin we used while PyPI had no fixed release, and the `pip-audit --ignore-vuln CVE-2026-4539` flag is gone from CI. `backend/apps/core/tests/test_dependency_assumptions.py` fails if a git pin comes back.
- **Preceptly:** The app does not use that lexer on untrusted user content; the exposure was mostly tooling.

### pip-audit: Twisted (via Daphne) — BEHOBEN am 17.11.2026

Twisted ist keine direkte Abhängigkeit, sondern kommt über **Daphne** (der Webserver). Am 24.10.2026 gab es mit Twisted 26.4.0
acht Meldungen und noch kein stabiles Release mit den Korrekturen; Andreas entschied damals, mit Begründung zu ignorieren und
nicht auf eine Vorabversion des produktiven Webservers zu wechseln. **Twisted 26.10.0 (stabil, veröffentlicht am 30.10.2026)**
löst das ab:

- Die Produktion läuft auf 26.10.0 (geprüft am 17.11.2026 mit `pip list` im Container).
- `pip-audit` ohne jede Ausnahme meldet für Twisted 26.10.0 **nichts mehr**. Alle Ignores sind aus `.github/workflows/ci.yml` entfernt.
- `requirements.txt` verlangt `Twisted>=26.10.0`, damit ein Build nie eine ältere Version auflöst.
- Der Wächtertest `test_dependency_assumptions.py` verlangt außerdem, dass jedes künftige `--ignore-vuln` hier begründet steht.

Meldungen, die bis dahin ignoriert waren (zur Nachvollziehbarkeit, Stand 24.10.2026):

| Lücke | Betrifft | Nutzte Preceptly das? |
|---|---|---|
| CVE-2026-106454, CVE-2026-115774 | IMAP4-Server (`twisted.mail.imap4`) | Nein, kein IMAP-Server |
| CVE-2026-115778 | `twisted.conch` Telnet | Nein |
| CVE-2026-115775 | XML-Element-Stream | Nein |
| CVE-2026-115776 | `twisted.words` IRC-Server | Nein |
| CVE-2026-83813 | `twisted.names` DNS-Client | Nein: Twisted löst Namen über seinen Thread-Resolver auf |
| GHSA-vpp8-g58w-m8mp | HTTP/2-Server von `twisted.web` („Rapid Reset“) | Nein: `h2` nicht installiert, Server startet ohne TLS-Endpunkt |
| CVE-2026-115877 | `twisted.web.http.HTTPChannel`: bloßes CR oder LF im Header-Wert (Request-Smuggling) | **Ja**, Daphne nutzt `twisted.web.http`; war befristet bis zur stabilen 26.10.0 ignoriert |

- **HTTP/2 bleibt aus:** Die Tests in `test_dependency_assumptions.py` halten `h2` und den HTTP/2-Extra aus den Abhängigkeiten und den
  Server ohne TLS-Endpunkt (weniger Angriffsfläche), auch wenn die Meldung selbst behoben ist.
- **Weiter beachten:** Bei jedem Dependabot-Hinweis zu Twisted oder Daphne nachsehen.

- **Zusätzlich am 24.10.2026 behoben (kein Ignore nötig):** `pillow` 12.3.0 → 13.0.0 (37 Meldungen), `pypdf` 6.20.0 → 6.21.2
  (9 Meldungen), `certifi` 2026.7.22 → 2026.10.19 (CA-Bundle mit kompromittiertem emSign-Root).

## Acknowledgments

We appreciate the security research community's efforts to help keep Preceptly secure. Responsible disclosure helps protect all users of the application.

