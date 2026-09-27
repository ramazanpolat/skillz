---
name: remote-kill
title: Killing processes by pattern over ssh
mode: auto
fires_on: [bash]
covers: Killing processes by name pattern ON A REMOTE HOST: pkill -f or killall inside an ssh command.
excludes: pkill or killall run locally, without ssh; restarting a service.
---
1. `pkill -f <pattern>` over ssh also matches the ssh session's own command
   line, which contains the pattern, and kills it. Use a bracket pattern:
   `pkill -f "[k]p-gate.sh"` instead of `pkill -f "kp-gate.sh"`.
2. Check what matches first: `pgrep -fa "[p]attern"`.
