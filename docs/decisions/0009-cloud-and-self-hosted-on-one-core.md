# 0009. Cloud and self-hosted edition on one core

**Date:** 2026-10-17 · **Question:** revision of question 8 of the product statement after M1
(`docs/product/vision.md`) · **Refines:** decisions 0003 and 0004

## Decision

- **Cloud first.** The first version is the author's cloud instance: the pilot runs on it. The
  self-hosted edition for deployment inside a company's network is built later, on the same
  core.
- **Three layers.**

  | Layer | What is in it | License |
  |---|---|---|
  | Core | Teams, Topics, Questions, conversation frame, secrets, event stream, plugin | AGPL-3.0; plugin — permissive |
  | Self-hosted edition modules | SSO (SAML, OIDC), LDAP, SCIM, audit export, plugin distribution from the server | commercial, a separate directory |
  | Cloud modules | self-service sign-up, plans and billing, quotas, email | the author's private repository |

- **Seams of the first version.**
  1. The account is separate from the login method: "user ↔ external identity (provider,
     identifier)". GitHub and Google (decision 0003) are the first providers of this mechanism;
     SSO is later added as a provider, without migrating accounts.
  2. Settings on two levels — instance and Team. Instance level: login methods, the source of
     SSH keys for verification (decision 0004: GitHub, later GitLab via `/<login>.keys`),
     storage limits (decision 0008). An "Organization" level above Teams is not introduced; the
     data owner is the Team, so it can be added later.
  3. External calls — behind interfaces: keys from GitHub, OAuth, email, file storage.
  4. Extension points for modules: login provider, check before an action (quota, license),
     audit log entry. In the first version there is one module — the cloud one; the directory of
     self-hosted edition modules is not created until needed.
- **Not in the first version:** SSO, LDAP, SCIM, offline installation, Helm chart, installation
  test on a clean machine.

## Why

- Right now it is most convenient for the author to deploy the service on hosting and try it out
  with the team's Assistants; the self-hosted solution differs in content and settings (SSO and
  more) and is built later (author, 2026-10-17).
- Per M1, the starting point for revenue is a solution for a company's network; without seams 1
  and 3 it would start with migrating accounts and ripping GitHub out of the core.
- This is how GitLab (one codebase, paid features in the `ee/` directory under their own
  license), Sentry (cloud features as a closed extension of open code) and Mattermost (feature
  set by license) are built.
- Closed cloud modules are possible while the author holds all rights to the code: AGPL binds
  those who received the code, not the rights holder. Outside contributions without a CLA close
  this off — question M4.
