# 0004. Keys and their verification

**Date:** 2026-10-16 · **Question:** A4, `docs/architecture/architecture.md`

## Four different things

| What | Where it is created | Where it lives | What for | Who revokes |
|---|---|---|---|---|
| Installation token (A3) | on the server, at device code login | on the computer, in the OS keychain | the server recognizes the User and the computer: Topics, messages, events | the human, in the web interface or from the plugin |
| Installation key | on the computer, in the plugin | the private part — only on this computer, the public part — on the server | to sign the Diffie — Hellman public parts when transferring a secret | the human, from the plugin |
| User master key | on the User's first computer, in the plugin | there; the public part — on the server | to sign the keys of the User's installations | — |
| Agreement key | on two computers when transferring a secret | nowhere, it disappears after the transfer | to encrypt one secret | — |

The token answers the server's "who are you"; ordinary conversation runs on it alone. The
three keys are needed only for secrets, and the server cannot forge them.

## Decision

- **Each installation has its own key.** The private part is created on the computer and never
  leaves it.
- **The user master key** is created on the first installation and signs the keys of the
  others. A new computer is confirmed by the human from an already trusted one: the Assistant
  shows the fingerprint of the new installation, the human compares it with the screen of the
  new computer and confirms. The master key is never moved; colleagues need to do nothing when
  someone gets a new computer.
- **Verification is done by plugins, without a human.** When the first computer is connected,
  the plugin signs the Coloqo master key with the User's SSH key that is already on their
  computer (`ssh-keygen -Y sign`). Before the first secret transfer, the sender's plugin fetches
  the recipient's public SSH keys directly from GitHub (`github.com/<login>.keys`), bypassing
  Coloqo, and verifies the signature. Substituting a key requires breaking into both Coloqo and
  the recipient's GitHub account.
- **Without an SSH key on GitHub** (or with Google login) — trust on first use: the plugin
  remembers the recipient's key at the first transfer; when the key changes, the Assistant does
  not send the secret silently but tells the human that the key has changed.
- **Manual fingerprint verification** is an option, not an obligation.
- **Revocation.** With one plugin command from a trusted computer: the server revokes the
  installation token (access to the conversation), the master key removes its signature from
  the installation's key (secrets are no longer encrypted for it). The web interface revokes
  only the token.
- **Loss of the master key** (all computers holding it are dead) — a new master key;
  recipients see the key change under the rules above.

## Why

- Users will not do mandatory manual verification, and they will leave a service that requires
  it (author, 2026-10-16). "Outside the service" is preserved: the external source is GitHub,
  which the Coloqo operator does not control. This is how Keybase confirmed keys.
- A key per installation does not require moving a private key; the master key spares
  colleagues repeated checks for every new computer (this is how Matrix and Signal work).
- Confirming a new device from an already trusted one is a familiar step (messengers, banks).

## Cost

The hardest part of the plugin. Without it, the promise "the server does not see secrets"
rests only on the operator's honesty.
