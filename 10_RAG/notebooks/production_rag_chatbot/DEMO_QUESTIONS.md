# Naive vs. Production RAG — Live Demo Questions

Copy-paste these exactly (don't retype from memory) — small wording changes shift what
gets retrieved and can quietly erase the gap between the two answers.

Before each round: check the **"📄 Currently indexed:"** banner at the top of the app
matches the document listed below. If it doesn't, upload the right file and click
**🔨 Build / rebuild index** first.

---

## Round 1 — upload `data/demo_knowledge_base.txt`

### ⭐ Q1 — the best one
```
What is the capital of France?
```
- **Correct behavior:** the document has nothing about France. Production should refuse.
- **What naive does:** says *"The retrieved context does not contain information about the
  capital of France. However, the capital of France is Paris."* — admits it's ungrounded,
  answers anyway.

### ⭐ Q2
```
How do I reduce noisy per-request HTTP logs from our service?
```
- **Correct answer:** raise the HTTP client library's log level (e.g. set `httpx` /
  `urllib3` to WARNING) so per-request lines are suppressed but real warnings still show.
- **What naive does:** invents a 5-point plan — batch requests, add a caching layer, use a
  circuit breaker, semantic caching, log level management. None of this is the actual fix;
  it's stitched from other unrelated topics in the corpus.

### ⭐ Q3
```
How do I stop a single user from overwhelming the API with requests?
```
- **Correct answer:** per-user rate limiting — a token-bucket limit of N requests/minute,
  keyed by user or API key.
- **What naive does:** mentions "rate limiting" in passing, then pads the answer with the
  wrong mechanisms — "circuit breaker," "caching layer" — never stating the actual fix.

### Q4 — subtler, good for a second pass
```
What are the tax advantages of a Roth 401k?
```
- **Correct answer:** funded with after-tax dollars; qualified withdrawals (incl. gains)
  are completely tax-free.
- **What naive does:** gets that part right, then adds an extra, unsourced claim ("no
  required minimum distributions during the account holder's lifetime") that is nowhere
  in the document. True in the real world, not grounded in the source — the harder kind
  of hallucination to catch by eye.

---

## Round 2 — switch to `data/sample_report.pdf`, rebuild the index

### ⭐ Q5
```
What were West region's shipments and revenue, and which two regions is a route being reallocated between?
```
- **Correct answer:** West = 204,910 shipments / $23.9M revenue. Route reallocated from
  **Northwest** to West.
- **What naive does:** gets West's numbers right, then says the route is "between West and
  **Northeast**" — the wrong region.

### Q6
```
What were total shipments, and how does the Northeast warehouse migration relate to it?
```
- **Correct answer:** 601,710 total shipments; Northeast migration reduced throughput
  there (89.3% on-time), fix due by July 15.
- **What naive does:** never states the number at all — talks about "8.4% growth" instead
  and never gives the actual total.

### Q7 — control question (both should behave the same)
```
What's the population of Mars?
```
- Both refuse. Useful to show the guardrail is a deterministic, measurable check
  (rerank score), not naive just getting lucky — contrast this with Q1, same *kind* of
  question, very different outcome.

---

## If a question stops showing a gap live

1. Check the **"Currently indexed"** banner — wrong document loaded is the #1 cause.
2. Re-paste the question exactly as written above (don't retype).
3. Check the sidebar sliders haven't drifted from defaults: chunk size 500, overlap 80,
   top-k 8, top-n 4, groundedness threshold -9.5.
