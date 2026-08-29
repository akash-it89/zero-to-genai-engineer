# Production RAG chatbot

Streamlit app built in **Notebook 13**. Uses `rag_pipeline.py` (`HybridIndex` + `Reranker` + grounded generation).

<p align="center">
  <img src="docs/screenshots/app.png" alt="Production RAG Chatbot — upload, chunking sliders, and build index" width="920">
</p>
<p align="center"><em>Drop in a PDF, tune chunk size / hybrid top-k / rerank, then ask for cited answers.</em></p>

Session 11's self-correcting RAG **imports this package unmodified** — do not rename or move this folder.

```bash
cd 10_RAG/notebooks/production_rag_chatbot
pip install -r requirements.txt
# needs OPENAI_API_KEY in 10_RAG/.env (or the repo root)
streamlit run app.py
```

Demo prompts: [`DEMO_QUESTIONS.md`](DEMO_QUESTIONS.md). Browser first: [Production challenges](https://nursnaaz.github.io/tutorial/production-challenges) · [Citations](https://nursnaaz.github.io/tutorial/citations-and-refusals).

← [Notebooks](../README.md) · [Session 10](../../README.md)
