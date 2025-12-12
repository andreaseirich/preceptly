# Security Policy

## Supported Versions

TutorFlow is currently in an early development stage (hackathon/early-stage project). At this time, only the `main` branch is actively maintained and supported.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue in TutorFlow, please report it responsibly.

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
- **Hackathon Demos**: During hackathon demos (e.g., CodeCraze Hackathon), TutorFlow runs in `MOCK_LLM` mode with synthetic data only; no real student data or real LLM calls are used.

## Content Security Policy (CSP)

TutorFlow implements a strict Content Security Policy to prevent XSS attacks and other injection vulnerabilities.

### Policy Details

- **Default Policy**: `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'self';`
- **No Inline Scripts/Styles**: The policy explicitly disallows `'unsafe-inline'` for scripts and styles
- **Static Assets Only**: All JavaScript and CSS must be loaded from static files (`static/js/`, `static/css/`)
- **Event Handlers**: Inline event handlers (`onclick`, `onchange`, etc.) are not used; JavaScript event listeners are used instead

### Configuration

- **Enable/Disable**: CSP can be controlled via the `ENABLE_CSP` environment variable (default: `true`)
- **Customization**: To modify the CSP policy, edit `apps/core/middleware.py` (ContentSecurityPolicyMiddleware)
- **External Resources**: If you need to load resources from external domains (CDNs, fonts, etc.), update the CSP policy accordingly

### Enforcement

- **Template Linting**: The `scripts/lint.sh` script checks for inline scripts, styles, and event handlers in templates
- **CI Integration**: Template checks are run as part of the CI pipeline
- **Manual Verification**: Use browser developer tools to verify CSP headers are present and working correctly

## Security Best Practices

When using TutorFlow:

- **Never commit sensitive data** (API keys, passwords, real student data) to the repository
- **Use environment variables** for configuration (see `docs/DEPLOYMENT.md`)
- **Keep dependencies updated** (Dependabot is configured to help with this)
- **Follow deployment guidelines** in `docs/DEPLOYMENT.md` for production environments
- **Use strong passwords** and enable authentication features as appropriate
- **No hardcoded secrets**: `SECRET_KEY`, database credentials, and LLM keys are expected from environment variables; defaults in the repo are demo-only
- **Secure defaults**: In Produktion niemals mit `DEBUG=True` oder leeren `ALLOWED_HOSTS` betreiben; aktivieren Sie bei Bedarf `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` via ENV.
- **CSP Enabled**: Keep CSP enabled in production (`ENABLE_CSP=true`) to prevent XSS attacks

## Acknowledgments

We appreciate the security research community's efforts to help keep TutorFlow secure. Responsible disclosure helps protect all users of the application.

