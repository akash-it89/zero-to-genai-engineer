# Contributing

This is the student repository for **Zero to GenAI Engineer**. Most people in the cohort never need to open a pull request — they clone, run notebooks, and ask questions in the **WhatsApp group**.

## Students

1. Follow the session README, top to bottom.
2. Do not commit `.env`, API keys, `*.db`, or generated model files (`.pt`, `.pth`).
3. Questions about the material → WhatsApp cohort group.

## Fixes (typos, broken links, notebook bugs)

Pull requests are welcome for:

- Broken relative links or outdated notebook names
- Setup instructions that no longer match the code
- Small comment / typo fixes in notebooks or READMEs

Please keep PRs small and say which session they belong to.

```bash
git clone https://github.com/nursnaaz/zero-to-genai-engineer.git
cd zero-to-genai-engineer
# use a branch named like fix/s10-notebook-11-link
```

Do **not** add third-party dumps (MedQuAD, `awesome-rag-production/`) or runtime folders (`node_modules/`, `__pycache__/`, `.langgraph_api/`). Those are gitignored on purpose.

## Code of the house

- No Discord — the cohort lives on WhatsApp.
- Streamlit is the default UI. React is optional and only in selected projects.
- Session folder READMEs are the start page for that weekend. Keep them accurate if you change files.
