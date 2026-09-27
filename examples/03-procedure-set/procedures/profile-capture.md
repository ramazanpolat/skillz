---
name: profile-capture
title: Saving a fact to the pilot profile
mode: ask
fires_on: [bash, write, edit, user_prompt]
covers: Writing a durable fact into the pilot's profile (~/.pilot-profile), or the user asks to remember or save a fact about themselves or their environment.
excludes: Reading the profile.
---
1. Check the capture mode in preferences.md (ask, auto or off).
2. Route it: the pilot -> identity.md or preferences.md; their machines ->
   machines/; other hosts -> peripherals/; accounts -> online/; people ->
   datasets/. Update an existing entry in place rather than adding a duplicate.
3. Never write a secret value; write its reference (`keychain:pilot/<name>`).
4. Set `updated:` to today, and add the file's line to PROFILE.md if it is new.
