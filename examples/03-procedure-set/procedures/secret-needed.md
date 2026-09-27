---
name: secret-needed
title: A step needs a credential
mode: auto
fires_on: [bash, user_prompt]
covers: A command or step that needs a password, token or API key and does not get it through with-secret or a keychain reference, e.g. reading a password file into argv or pasting a token into an export.
excludes: Commands already wrapped in with-secret VAR=REF --.
---
1. Never put the value on argv, in a file, a log or the chat.
2. Use a reference, resolved at the moment of use:
   `with-secret VAR=keychain:pilot/<name> -- <command>`.
3. If it is not stored yet, ask the pilot to run
   `with-secret --store <name>` themselves. Never ask for the value.
