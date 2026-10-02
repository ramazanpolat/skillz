# Add a skill

1. Create `plugins/skillz/skills/<new-skill>/SKILL.md` with frontmatter:

   ```markdown
   ---
   name: <new-skill>
   description: <when Claude should use this skill — be specific; this is the trigger>
   ---

   # <new-skill>

   Instructions for Claude on how to perform the task.
   ```

2. Put any helper scripts under that skill's own `scripts/` folder and `chmod +x`
   them.
3. Commit and push. Users pick it up on the next `/plugin` update — no edits to
   `marketplace.json` or `plugin.json` required.
