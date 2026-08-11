# Security Policy

LLM Researcher is an open-source, self-hostable academic research assistant.
We take the security of the project — and of the self-hosted deployments our
users run — seriously. This policy explains how to report a vulnerability and
what you can expect from the maintainers.

- **License**: MIT — see [LICENSE](LICENSE)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Code of Conduct**: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- **Architecture**: [docs/PLAN.md](docs/PLAN.md)
- **Roadmap**: [docs/ROADMAP.md](docs/ROADMAP.md)

## Supported Versions

The project is in **beta** and has not tagged a release yet; security fixes
ship on `main` as soon as they are ready.

| Version | Supported |
|---|---|
| `main` (unreleased) | ✅ Security fixes land here first |
| Tagged releases (from `v2.0.0` onward) | ✅ The latest release line receives security fixes |

Once `v2.0.0` is tagged (tracked in [docs/ROADMAP.md](docs/ROADMAP.md),
Milestone 0), security fixes will be applied to the latest release and
backported to `main`.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for suspected security
vulnerabilities.** Report them privately so we can fix the problem before it
is widely known.

### How to report

- Email the maintainer at **leonardo.farroco@gmail.com** with `[SECURITY]` at
  the start of the subject line.
- If a private reporting channel (e.g. GitHub Security Advisories) is enabled
  on the repository, you may use that instead.

Include as much of the following as you can:

1. The affected version or commit (e.g. `git rev-parse HEAD`)
2. A description of the vulnerability and its impact
3. Steps to reproduce, including any configuration involved
4. (Optional) A suggested fix or proof-of-concept

### What happens next

- **Acknowledgment** — we will reply within **48 hours**.
- **Assessment** — we will triage the report and confirm whether it is
  accepted within **7 days**.
- **Fix** — accepted reports are fixed as soon as possible, usually within
  **30 days**, and shipped on `main` (and backported where applicable).
- **Disclosure** — we will coordinate public disclosure with you once a fix
  is available.

## Disclosure Policy

- We follow **coordinated disclosure**: reporters get advance notice of fixes
  and are credited (if they wish) in the release notes / CHANGELOG.
- Details of a vulnerability are not made public until a fix is available and
  deployed.
- Security-sensitive fixes may be released without a detailed public changelog
  entry until users have had time to update.

## Security Considerations for Self-Hosted Deployments

LLM Researcher is designed to be **self-hosted**. Keep the following in mind
when running your own instance:

- **Secrets live in `.env`** — API keys (`OPENAI_API_KEY`, `GROQ_API_KEY`,
  `DEEPSEEK_API_KEY`, `TAVILY_API_KEY`, `SPRINGER_API_KEY`,
  `ELSEVIER_API_KEY`, and others) are read from the environment, and `.env`
  is gitignored. Never commit these files or paste keys into issues, pull
  requests, or chat messages. See [`.env.example`](.env.example) for the
  full list of supported settings.
- **No authentication yet** — the app currently has no user authentication or
  per-user data isolation (planned in [docs/ROADMAP.md](docs/ROADMAP.md),
  Milestone 5). Do **not** expose an unauthenticated instance to the public
  internet or an untrusted network.
- **Database credentials** — the default `DATABASE_URL` in
  [`.env.example`](.env.example) uses development credentials; change the
  password and restrict network access in production.
- **TLS** — if you expose the app beyond localhost, terminate TLS at a
  reverse proxy (e.g. Nginx, Caddy, Traefik) and keep the `/ws/` WebSocket
  endpoints behind it.
- **Dependency hygiene** — keep Python, Node, and Docker image dependencies
  up to date. CI runs `ruff check app/` and the test suite (see
  [`.github/workflows/ci.yml`](.github/workflows/ci.yml)); consider enabling
  Dependabot or equivalent on your fork.

## Scope

In scope:

- Vulnerabilities in the application code under `app/` and `frontend/`
- Logic flaws that could leak data between research items or compromise a
  self-hosted instance
- Insecure defaults or configuration that could lead to credential exposure

Out of scope (please still tell us, but expect lower priority):

- Vulnerabilities in third-party dependencies (report those to the upstream
  project)
- Phishing or social engineering against the maintainers
- Issues in a deployment you have modified beyond the documented setup in
  [README.md](README.md)

## Thanks

We appreciate the community's help keeping LLM Researcher safe. Contributors
are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md) and
[Contributing Guide](CONTRIBUTING.md).
