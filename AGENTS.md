# PaperLab working instructions

- Keep changes small and reviewable. After each completed change, commit it and push it to the connected `origin` repository before starting the next change, unless the user asks for a different workflow.
- Check the working tree before committing. Stage only files belonging to the completed change; preserve unrelated user edits.
- If a commit or push fails, report the exact blocker and retain the local work. Do not claim a change is on GitHub until the push succeeds.
- The implementation plan is maintained in `PaperLab_Implementation_Plan.md`. Regenerate `PaperLab_Implementation_Plan.html` with `node build_plan.cjs` after editing the Markdown, and commit the source and regenerated document together.
- After each important feature is complete, remind the user to test it and give concrete steps and expected results. Run the appropriate automated checks before that reminder.
