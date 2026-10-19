---
description: Link this project to a Coloqo Team, or check its link
argument-hint: "[write]"
---

Link this project to one of the user's Coloqo Teams: $ARGUMENTS

Call the coloqo `link_project` tool. If it returns an address, give it to the user to open and
pick the Team, then call `link_project` again once they say it is done. If the user said
"write", call it with `write_file=true` once the project is linked, and remind them to commit
`.coloqo.json` so the whole Team's projects link to the same Team.
