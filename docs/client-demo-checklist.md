# PaperLab client walkthrough

Verified 2 November 2026. This is the local research workspace demonstration, with generated
code and static review. It does not demonstrate hosted training or independently verified results.

## Before presenting

- Start with `npm run dev` and open http://127.0.0.1:4200.
- Confirm the workspace reports Groq configured. Keep `.env` and API keys off screen.
- Choose a readable, short PDF or a supported arXiv, CVF or OpenReview link. Scanned PDFs need
  OCR outside PaperLab; extraction limits are 10 MB / 80 pages.
- Use Guided mode and a narrow reproduction target. Set an assistant budget suitable for the
  demonstration; zero blocks AI calls. Provider quotas and latency still apply.

## Walkthrough and expected behavior

| Action | Expected result |
| --- | --- |
| Create a project with a PDF and leave the URL blank | Research workspace opens with the paper already extracted |
| Alternatively, save a supported link and open the workspace | The paper imports automatically; no text-pasting step |
| Refresh an attached-paper project | The saved source remains; no repeat upload/import |
| Run analysis, then planning | Agent actions show evidence tools and saved output |
| Open code generation before approving the Guided plan | The UI explains that approval is required |
| Approve the plan and generate code | Virtual files are drafted and statically checked; download becomes a handoff for external execution |
| Request a smaller CPU-only plan through feedback | The affected plan and downstream work are invalidated; the new plan needs approval |
| Revise only the evaluation metric | Outputs are invalidated but the attached paper is retained |
| Change the paper URL | Old source is detached; opening the workspace imports the new supported link |
| Upload an invalid PDF during creation | The project stays saved; the workspace explains the failure and accepts a replacement |
| Save metrics from an actual external run, refresh, reopen metrics | Saved values return, explicitly labeled self-reported |
| Review activity history | Agent actions, failures and correctly localized timestamps remain visible |

If a link cannot be imported, use **Upload PDF**. The optional excerpt form is a fallback for
partial source material. If Groq reaches a rate limit, the trace shows bounded waiting; after a
terminal failure, retry explicitly. Avoid promising a fixed generation time or scientific accuracy.

## Checks completed

- 69 backend tests and Ruff passed.
- All 17 Playwright scenarios passed using an isolated test database. Project/PDF scenarios use
  the real local API; AI-stage UI scenarios use controlled provider responses.
- Angular production build passed. Its existing landing stylesheet size warning remains.
- The public sample at https://arxiv.org/abs/1512.03385 imported live: 12 pages, 59,411 extracted
  characters, with CFF font support installed. No AI call was needed for that import.
- PDF-ready desktop layout was visually inspected; browser scenarios check mobile overflow
  and keyboard navigation as well.

## Present the current scope accurately

PaperLab drafts and statically checks code; it does not run training, certify paper reproduction,
or directly launch VS Code, Colab or Kaggle jobs. The ZIP and notebook are export handoffs.
This is a local single-user app without hosted multi-user authentication. Figure interpretation,
OCR, arbitrary publisher access, sandboxed execution and automatic checkpoint resume remain future work.
