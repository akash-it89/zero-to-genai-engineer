# Tech Stack & Tools

## Languages
- **Python 3.10+** — primary language for all notebooks, backends, and scripts
- **JavaScript (JSX)** — React frontends for demo apps

## Core ML/AI Libraries
- PyTorch (transformers, GPT from scratch)
- scikit-learn (TF-IDF, cosine similarity)
- gensim (Word2Vec, FastText)
- sentence-transformers (embedding models)
- tiktoken (BPE tokenization)
- DSPy (prompt engineering, optimization)
- LangChain (unified LLM interface, LCEL chains)
- openai (API client)

## Backend Frameworks
- FastAPI + Uvicorn (REST APIs)
- Pydantic (data validation)
- pandas / numpy (data processing)

## Frontend Stack
- React 18 + Vite
- Tailwind CSS + PostCSS
- Recharts (data visualization)
- Axios (HTTP client)

## LLM Providers
- Ollama (local inference)
- LM Studio (local GUI)
- OpenRouter (multi-model gateway)
- Databricks (enterprise endpoints)
- Gemini API (free tier)
- OpenAI API

## Other Tools
- Streamlit (quick demo UIs)
- Jupyter Notebooks (primary teaching format)
- Jinja2 (prompt templates in Distill)
- OpenAI Whisper (speech-to-text)
- Makefile (task runner in Distill subproject)

## Common Commands

### Python backends
```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI server
uvicorn main:app --reload --port 8000
```

### React frontends
```bash
# Install dependencies
npm install

# Dev server
npm run dev

# Production build
npm run build
```

### Jupyter notebooks
```bash
jupyter notebook
# or
jupyter lab
```

### Testing (where available)
```bash
pytest
```

### Distill subproject (has Makefile)
```bash
cd 05_Local_LLMs_and_API_Providers/distill
make dev       # start dev environment
make test      # run tests
```
