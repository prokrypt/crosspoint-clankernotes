# Contributing

For humans and AI agents alike. A wrong note is worse than a missing one.

## A note must

1. **Be verified** against current upstream code. Cite the repo tag, commit and
   `file:line`, as in `cp src/main.cpp:445`. If upstream has moved past the
   commits in the README table, re-check the note and update the table.
2. **Be important.** It should prevent a real bug, panel damage, data loss, or a
   wasted day. Skip style tips and trivia.
3. **Be terse**, and live in the right topic file (`display`, `network`,
   `memory`, `app`, `features`). Add a new file only when no existing one fits.
4. **Carry `[fork]`** when it only holds in a downstream fork, or when the
   number was measured on one unit. Say which device when it matters.
5. **Name its source.** Hardware claims need a controller datasheet (with page
   number), the code, or your own measurement. Vendor demo code, blogs and
   wikis don't count.

## Never include

Credentials, tokens, test accounts, IPs, hostnames, SSIDs, emails, personal or
account names, internal session/thread ids, private URLs, or local paths.
Before pushing, grep for them:

```sh
grep -rniE 'token|passw|secret|[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+|@[a-z0-9-]+\.[a-z]|/home/|/mnt/|/tmp/' .
```

Security holes in upstream go to upstream privately first, not here.

## Keeping it current

When upstream fixes something, delete the note or move it into `features.md`
as done. Don't leave stale notes behind.

## LUT tool

```sh
python3 tools/lut_balance.py path/to/freeink-sdk
```

Output is `row=net/frames`. Balanced transition sets have `WW=KK=0` and
`KW+WK=0`; absolute sets have every row at 0. If the SDK renames a table, update
the names in the script in the same PR.

## Submitting

Open a PR with one topic per PR. The description lists the upstream commits you
verified against.
