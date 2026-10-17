# 0014. Minimum personal data

**Date:** 2026-10-17 · **Question:** M5 of the product statement (`docs/product/vision.md`) ·
**Refines:** decisions 0003, 0004, 0013

## Decision

- **The server stores about a person only:** the identifier at the login provider (id on GitHub,
  `sub` at Google), the pseudonym chosen by the person, and the names of their Assistants. Plus
  the conversations — their content inevitably contains personal data.
- **It does not store:**
  - email: Google — without the `email` scope, GitHub — without scopes; there is no mailing in
    the first version (decision 0012);
  - the real name: the Team sees the pseudonym (`alice · billing-api`);
  - the GitHub login: before verifying a key (decision 0004) the sender's plugin gets the login
    by id through `api.github.com/user/<id>`, then takes `github.com/<login>.keys`;
  - IP addresses in logs: disabled or truncated in Caddy (decision 0013).
- **An invitation to a Team is a one-time link** that the inviter passes on personally, not an
  email.
- **End-to-end encryption of all conversations is not done.**

## Why

- Minimization reduces the damage of a leak. Most likely it does not remove the status of a
  personal data operator: the provider identifier and the pseudonym point to a person
  indirectly, and in conversations personal data is in the text. A question for a lawyer: is a
  service that stores only the provider identifier, the pseudonym and users' conversations an
  operator.
- End-to-end encryption of all conversations means revising question 8 and decision 0012 (the web
  without keys cannot show Topics, Question reminders need titles), that is, reworking half of
  the architecture; whether storing ciphertext removes personal data processing is also unclear.
- In the self-hosted edition the operator is the company that deployed Coloqo, not the author
  (an argument for M1).
