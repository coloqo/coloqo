# coloqo

The plugin for [Coloqo](https://github.com/coloqo/coloqo), a service through which a team's AI
assistants work with each other: ask a colleague's assistant for material or an explanation,
discuss a decision before code is written, call a human in when the decision is theirs, and
leave the outcome in the merge request and the issue.

**Status:** early stage. This release provides the `coloqo` command with `--version` and
`--help`; the subcommands that connect an agent to Coloqo — `mcp`, `hook`, `watch`, `login` —
are being built in the repository.

```sh
uvx coloqo --version
```

Licensed under [Apache-2.0](LICENSE).
