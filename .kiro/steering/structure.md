# Project Structure

## Top-Level Organization

The repo is organized as numbered session folders, each corresponding to a module in the curriculum. Numbering reflects teaching order.

```
zero-to-genai-engineer/
├── prereq/                          # Pre-work: Python, math, neural net basics
│   ├── notebooks/                   # 3 foundational notebooks
│   └── cheatsheet.md
├── 00_How_Search_Engine_Works/      # M00 Part 1a — TF-IDF
├── 01_Text_to_Numbers/              # M00 Part 1b — Embeddings + Movie Recommender
├── 02_Transformer_Architecture/     # M00 Part 2 — Encoder-Decoder from scratch
├── 03_GPT_Evolution_and_Alignment/  # M00 Part 3 — GPT papers + code
├── 03_GPT_1_2_3/                    # Legacy GPT notebook (kept for reference)
├── 04_BPE_Temperature_Top_K_Top_P/  # M01 — Tokenization + Sampling
├── 05_Local_LLMs_and_API_Providers/ # M02 — Ollama, OpenRouter, Distill project
├── 06_Prompt_Engineering_DSPY_GEPA_COT/ # M03/M04 — DSPy, CoT, MIPROv2, GEPA
├── 07_LangChain_Notebooks/          # M03 Part 3 — LangChain fundamentals
├── 08_Recap/                        # Visual recap slides (HTML)
├── 09_AgenticCoding_LoopEngineering/ # M05 — Agentic coding + loop patterns
├── docs/                            # Misc notes
└── .kiro/steering/                  # AI assistant steering rules
```

## Session Folder Convention

Each numbered session folder typically contains:
- `README.md` — session overview, learning objectives, instructions
- `notebooks/` — Jupyter notebooks (numbered: `01_*.ipynb`, `02_*.ipynb`, …)
- `slides/` — PDF or HTML slide decks
- `papers/` — referenced research papers (where applicable)
- `assets/` — images and diagrams

## Full-Stack Demo Apps

Some sessions include standalone apps with this structure:
```
session_folder/app_name/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── requirements.txt     # Python dependencies
│   ├── data/                # CSV datasets (gitignored, download separately)
│   └── models/              # Trained model files (gitignored, regenerate locally)
└── frontend/
    ├── package.json         # Node dependencies
    ├── src/
    │   ├── App.jsx
    │   └── components/
    └── index.html
```

## Naming Conventions
- Session folders: `NN_Topic_Name` (zero-padded number + underscored topic)
- Notebooks: `NB{N}_descriptive_name.ipynb` or `0N_descriptive_name.ipynb`
- Python files: `snake_case.py`
- React components: `PascalCase.jsx`
- Data/model files: gitignored — users download or generate locally

## Key Files
- `/README.md` — master curriculum table, changelog, project list
- `/.gitignore` — excludes data CSVs, model binaries, node_modules, .env, __pycache__
- Each session's `README.md` is the entry point for that module
