# Security Policy

## Supported Versions

We actively maintain the following versions with security patches:

| Version | Supported | Notes |
| ------- | --------- | ----- |
| 0.1.x (current pre-alpha) | ✅ | Milestone 0–3 — expect frequent breaking changes |
| < 0.1 | ❌ | Not yet released |

Once Noesis reaches 1.0.0, the current minor release + the prior minor release
will receive security fixes (rolling 2-minor support window).

## Reporting a Vulnerability

**DO NOT open a public GitHub issue for security bugs.** Public disclosure puts
every self-hosted Noesis deployment at risk.

Instead:

1.  Email **security@noesis.dev** with the vulnerability details.
2.  Include the following information where possible:
    -   Type of issue (e.g. injection, privilege escalation, prompt-injection bypass, tool sandbox escape, RCE, credential leak, dependency CVE)
    -   Noesis version / commit SHA
    -   Step-by-step reproduction
    -   Proof-of-concept code (if safe to share)
    -   Impact assessment (who is affected? what is the worst case?)
3.  You will receive an acknowledgement within **48 hours**.
4.  We follow a **90-day public disclosure window**:
    -   Days 0–30: triage + root cause analysis
    -   Days 30–60: fix developed + reviewed + backported to supported versions
    -   Day 60: patch released, private email to reporter with draft advisory
    -   Day 90: public GitHub Security Advisory + CVE (if assigned) + disclosure
5.  If the bug is **actively being exploited in the wild**, we may accelerate
    this timeline to 14 days and notify major downstream packagers privately
    before public release.

## Safe Harbor

We consider **responsible security research** conducted under this policy to be
authorised, and we will not initiate or recommend legal action against you for
research conducted in compliance with this policy. Specifically, you must:

-   Stop testing and notify us immediately if you access user data beyond what
    is necessary to demonstrate the vulnerability.
-   Not disclose the bug to anyone else before our coordinated disclosure date.
-   Not exploit the bug for your own commercial or personal gain.

## Security Hotspots (for contributors)

When reviewing code, pay extra attention to these high-risk areas:

| Area | Risk | Example |
|------|------|---------|
| Tool Agent `code` parameter | RCE if not sandboxed | `os.system(user_provided_string)` |
| RAG document ingestion | Prompt injection | Hidden instructions inside PDFs |
| `redis/` cache keys | Cache poisoning / SSRF | User-controlled key prefixes |
| JWT signing key | Auth bypass | Hardcoded keys, `alg=none` attacks |
| CORS `cors_origins` config | Credential theft | Wildcard + credentials |
| Pydantic `extra="allow"` fields | Mass assignment | ORM writes via unsanitised user dicts |
| Dependency updates | Supply chain | Untrusted GitHub Actions workflows |
