# Session 01 — Text to Numbers

> **The big question:** How does a computer understand language? It doesn't read words — it reads numbers. This session shows you every method humans have invented to turn text into numbers, from counting words in 1954 to dense neural embeddings in 2016.

Every Generative AI system you build — RAG, agents, chatbots — depends on this foundation. You can't measure similarity between two pieces of text without it.

---

## 📋 Assignments

> [!IMPORTANT]
> Three assignments to complete after this session. Share your work in the WhatsApp group.

| # | Type | Assignment | Due |
|---|------|-----------|-----|
| A1 | ✍️ Article | How Different Embeddings Work | Next session |
| A2 | ✍️ Article | Cosine Similarity vs Euclidean Distance | Next session |
| A3 | 💻 Build | Product Recommender System | Next session |

---

### A1 — Medium Article: How Embeddings Work

Write a Medium article explaining **how each of the 5 text embedding methods works**, aimed at a complete beginner who just finished this session.

Your article must cover all five methods with at least one concrete example each:

- **Bag of Words** — what it counts, and why word order being lost is a problem
- **TF-IDF** — what the IDF weight fixes, and why rare words matter more
- **Word2Vec** — the core insight: predicting context words forces the model to learn meaning
- **GloVe** — how global co-occurrence statistics differ from Word2Vec's local window
- **FastText** — why character n-grams let it handle typos and unseen words

---

### A2 — Medium Article: Cosine Similarity vs Euclidean Distance

Write a Medium article answering: *why do we use cosine similarity for NLP instead of Euclidean distance?*

Your article must cover:
- What **cosine similarity** measures — the angle between two vectors (0% = opposite, 100% = identical direction)
- What **Euclidean distance** measures — the straight-line distance between two points
- A concrete example where they give **different answers** — e.g. the same document copy-pasted twice is longer but means the same thing; cosine similarity handles this correctly, Euclidean distance does not
- Why **magnitude does not matter for meaning** in NLP — a 10-word review and a 1,000-word review about the same movie should rank as similar

---

### A3 — Build: Product Recommender System

Adapt the [movie recommender](movie_recommender/) to work with **Amazon product descriptions** instead of movies. The embedding logic stays identical — only the data and field names change.

#### Dataset

Download the Amazon product descriptions dataset from HuggingFace:

> **Dataset page:** https://huggingface.co/datasets/philschmid/amazon-product-descriptions-vlm

**Option 1 — pandas direct download (no extra install):**
```python
import pandas as pd

URL = "https://huggingface.co/datasets/philschmid/amazon-product-descriptions-vlm/resolve/main/data/train-00000-of-00001.parquet"
df = pd.read_parquet(URL)
print(df.columns.tolist())  # explore the schema first
print(df.shape)             # how many products?
print(df.head(2))
```

**Option 2 — HuggingFace datasets library:**
```python
from datasets import load_dataset

ds = load_dataset("philschmid/amazon-product-descriptions-vlm", split="train")
df = ds.to_pandas()
print(df.columns.tolist())
```

#### What to change in the movie recommender

The core recommender logic (`recommender.py`) is untouched — only the data loading and field mapping changes:

| File | What to change |
|------|---------------|
| `backend/data/` | Save the product dataframe as `products.csv` here (replace `imdb_top_1000.csv`) |
| `backend/recommender.py` | Update `CSV_PATH` filename |
| `backend/recommender.py` | Update `_prepare_text()` — combine product description + category + brand instead of movie overview + genre + director |
| `backend/recommender.py` | Update `_movie_to_dict()` — return product fields (name, description, category, price, image) instead of movie fields |
| `backend/main.py` | Update the app title and description string |
| `frontend/src/App.jsx` | Update UI labels (movie → product) — optional |

The five embedding methods (BoW, TF-IDF, Word2Vec, GloVe, FastText) and cosine similarity comparison work exactly the same — you are just feeding them product text instead of movie text.

---

## What's MISSING after this session?

All five methods in this session treat each word as an isolated unit.

- BoW and TF-IDF: count words, no meaning
- Word2Vec, GloVe, FastText: capture meaning, but one fixed vector per word

`"bank"` (river) and `"bank"` (finance) get the same vector.

That gap — **context-dependence** — is exactly what the Transformer architecture solves. The attention mechanism assigns different vectors to the same word based on surrounding context. That is what the next session covers.

---

## Notebooks

Run these in order in **Google Colab** or locally with Jupyter.

| # | Notebook | What You Build | Time |
|---|---|---|---|
| 01 | [01_text_to_numbers.ipynb](notebooks/01_text_to_numbers.ipynb) | BoW → TF-IDF → Word2Vec → GloVe → FastText from scratch | 60 min |
| 02 | [02_cosine_similarity.ipynb](notebooks/02_cosine_similarity.ipynb) | Why cosine similarity works — geometric intuition + implementation | 30 min |

**No API key needed.** Everything runs on Python, numpy, and gensim.

---

## Project

| Project | What It Builds | Stack |
|---|---|---|
| [movie_recommender/](movie_recommender/) | Compare all 5 embedding methods side-by-side on 1,000 IMDB movies | FastAPI + React |

See [movie_recommender/README.md](movie_recommender/README.md) for full setup instructions.

---

## Slides

Session slides are in the [`slides/`](slides/) folder.

| File | Contents |
|---|---|
| [M00-S01.pdf](slides/M00-S01.pdf) | Text to Numbers — BoW, TF-IDF, Word2Vec, GloVe, FastText |

---

## Setup

```bash
# Notebooks — run in Colab or locally
pip install notebook gensim numpy scikit-learn matplotlib

# Movie recommender — see movie_recommender/README.md for full instructions
cd movie_recommender/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
