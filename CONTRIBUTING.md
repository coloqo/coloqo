# Contributing to Coloqo

Thank you for your interest. Coloqo is at an early stage: the design is settled
(`docs/product/vision.md`, `docs/architecture/architecture.md`, `docs/decisions/`) and the first
version is being built.

## Language

The project is developed in English: code, comments, docs, commit messages, issues and pull
requests.

## Contributor License Agreement

Before we can merge your first pull request, you sign the Coloqo Contributor License Agreement
(CLA). The CLA Assistant bot asks you to do it in the pull request; signing takes one click with
your GitHub account and covers all your future contributions.

You keep the copyright in your contributions. The CLA gives the maintainer a broad license to
use them, including the right to distribute them under other licenses.

**Why a CLA.** Coloqo is open source, and parts around it are not:

- the cloud instance has closed modules: billing, plans, self-service sign-up;
- the self-hosted edition will have commercial modules: SSO, LDAP, SCIM, audit export
  (decision `docs/decisions/0009-cloud-and-self-hosted-on-one-core.md`).

Without a CLA, a contribution under AGPL-3.0 could not live in the same process with those
modules without opening them, and could not be relicensed. The CLA keeps these options open.

**Our promise.** The core of Coloqo — Teams, Topics, Questions, the conversation frame, secrets,
the event stream and the plugin — stays open source under its current licenses: the server and
the web interface under AGPL-3.0, the plugin under Apache-2.0.

## Licenses

- Server and web interface: [AGPL-3.0](LICENSE).
- Plugin (`plugin/`, when it appears): Apache-2.0, with its own `LICENSE` file in that directory.
