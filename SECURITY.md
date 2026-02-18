# Security Policy

## Reporting a Vulnerability

Please **do not** report security vulnerabilities through public GitHub issues.

Preferred: use **GitHub Security Advisories** for this repository (private disclosure).

If that is not possible, open a GitHub issue with:
- the title: `SECURITY: request private channel`
- **no sensitive details**

The maintainer will respond with a private follow-up method.

## What Not to Share Publicly

- Any credentials: `OPENAI_API_KEY`, cookies, session storage state, access tokens.
- Private keys/certificates, or `.env` files.
- User data from pages you translated if it is not yours to share.

## Scope Notes

Web2RU is a CLI tool that renders pages with Playwright and produces offline snapshots.
Please report issues that could lead to:
- unintended external network requests in offline output,
- leaking secrets into artifacts/logs,
- unsafe script execution in offline output despite `freeze-js` protections.

