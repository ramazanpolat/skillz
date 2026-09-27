---
name: gui-step
title: A step needs the pilot at a screen
mode: auto
fires_on: [bash, user_prompt]
covers: A step that needs the pilot at a screen: opening a URL in a browser for them, a browser login, 2FA, OAuth consent.
excludes: Fetching a URL with curl or an API call.
---
1. Run `pilot here` first. If the pilot is at another machine, or it says
   unknown, do not open anything on this screen.
2. Prefer a flow they can approve from their phone; else open it on the
   machine they are at (`ssh <machine> open '<url>'`); else send one push
   notification saying what is waiting and where.
