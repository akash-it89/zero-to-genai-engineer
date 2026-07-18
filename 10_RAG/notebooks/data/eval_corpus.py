"""Shared gold-labeled evaluation corpus for Notebooks 07 (hybrid) and 08 (reranking).

Design principle: every topic has ONE gold passage that truly answers its query, plus
several HARD near-miss distractors — same domain, overlapping keywords, semantically close,
but subtly wrong (wrong error code, wrong version, related-but-different fix). That near-miss
structure is what makes first-stage retrieval imperfect and lets fusion + reranking show
measurable gains (Recall@k, MRR, nDCG@10).

query "type" hints which retriever it favors:
  - "exact"    : hinges on an exact token/code/version  (BM25-friendly)
  - "semantic" : paraphrase / vocabulary gap            (dense-friendly)
  - "mixed"    : both an exact term and paraphrasing
"""
from __future__ import annotations
import random

TOPICS = [
    # ── web / API errors (near-miss = wrong status code) ─────────────────────
    {"query": "How do I fix a 502 Bad Gateway error from our API?", "type": "mixed",
     "gold": "A 502 Bad Gateway from the API gateway means the upstream service returned an invalid response or is down. Restart the upstream service and verify its health checks are passing.",
     "distractors": [
        "A 504 Gateway Timeout means the upstream service took too long to respond; increase the gateway's read timeout.",
        "A 503 Service Unavailable indicates the server is overloaded or in maintenance mode; enable autoscaling or a maintenance page.",
        "A 500 Internal Server Error is an unhandled exception in application code; check the stack trace in your logs.",
        "A 400 Bad Request means the client sent malformed input; validate the request body against the schema.",
        "Browser 'Bad Gateway' pages can sometimes be cleared by flushing local DNS and refreshing the cache."]},

    # ── python versions (near-miss = wrong version) ──────────────────────────
    {"query": "What did Python 3.11 add for error messages?", "type": "exact",
     "gold": "Python 3.11 introduced fine-grained error locations in tracebacks, pointing to the exact expression that caused an error, plus significantly faster startup.",
     "distractors": [
        "Python 3.10 introduced structural pattern matching with the match statement and better error messages for syntax errors.",
        "Python 3.12 improved f-strings, added a per-interpreter GIL, and refined type-parameter syntax.",
        "Python 3.9 added dictionary merge operators and relaxed decorator grammar.",
        "Python 3.8 introduced the walrus operator := for assignment expressions.",
        "Python 2.7 reached end of life in 2020 and no longer receives security updates."]},

    # ── databases (near-miss = related but different) ────────────────────────
    {"query": "Why is my Postgres query slow even though the column has an index?", "type": "semantic",
     "gold": "Postgres may ignore an index when a query's WHERE clause wraps the column in a function or casts its type, making the index non-sargable; rewrite the predicate or add a matching expression index.",
     "distractors": [
        "Adding an index speeds up reads but slows down writes because every INSERT must update the index structure.",
        "A sequential scan is chosen by the planner when a table is small or when most rows match the filter.",
        "VACUUM reclaims storage from dead tuples and updates the visibility map for index-only scans.",
        "Connection pooling with PgBouncer reduces the overhead of establishing new database connections.",
        "Postgres replication lag can make read replicas return slightly stale data under heavy load."]},

    # ── auth / security (near-miss = adjacent concept) ───────────────────────
    {"query": "How should we store user passwords securely?", "type": "semantic",
     "gold": "Store passwords as salted hashes using a slow, memory-hard algorithm such as bcrypt, scrypt, or Argon2 — never plaintext or fast hashes like MD5 or SHA-256.",
     "distractors": [
        "Encrypt data in transit with TLS 1.3 so credentials are never sent in cleartext over the network.",
        "Rotate API keys regularly and scope them to the minimum permissions required.",
        "Enforce multi-factor authentication to reduce the impact of stolen credentials.",
        "Store session tokens in httpOnly, Secure cookies to mitigate XSS token theft.",
        "Use a secrets manager like Vault to keep database credentials out of source code."]},

    # ── kubernetes (near-miss = different failure) ───────────────────────────
    {"query": "My pod is stuck in CrashLoopBackOff — what does that mean?", "type": "exact",
     "gold": "CrashLoopBackOff means the container starts, exits with an error, and Kubernetes keeps restarting it with increasing back-off delays; inspect 'kubectl logs' and the exit code to find why it exits.",
     "distractors": [
        "ImagePullBackOff means Kubernetes cannot pull the container image; check the image name, tag, and registry credentials.",
        "Pending means the pod cannot be scheduled, often due to insufficient CPU or memory on any node.",
        "OOMKilled indicates the container exceeded its memory limit and was terminated by the kernel.",
        "Evicted pods were removed because the node ran out of disk or memory resources.",
        "A readiness probe failure keeps a pod out of the Service endpoints until it reports healthy."]},

    # ── finance (near-miss = different retirement vehicle) ───────────────────
    {"query": "What are the tax advantages of a Roth 401k?", "type": "mixed",
     "gold": "A Roth 401k is funded with after-tax dollars, so qualified withdrawals in retirement — including investment gains — are completely tax-free.",
     "distractors": [
        "A traditional 401k is funded with pre-tax dollars, lowering taxable income now, but withdrawals in retirement are taxed as ordinary income.",
        "A traditional IRA may offer a tax deduction on contributions depending on income and workplace coverage.",
        "A Roth IRA has income eligibility limits and, unlike a 401k, no employer match.",
        "A health savings account offers triple tax advantages for qualified medical expenses.",
        "A 529 plan provides tax-free growth when funds are used for qualified education expenses."]},

    # ── legal / contract (near-miss = different clause) ──────────────────────
    {"query": "How much notice is required to end the agreement early?", "type": "semantic",
     "gold": "Either party may terminate this agreement for convenience by providing sixty days prior written notice to the other party.",
     "distractors": [
        "Either party may terminate for material breach if the breach remains uncured thirty days after written notice.",
        "This agreement renews automatically for successive one-year terms unless cancelled before the renewal date.",
        "The confidentiality obligations survive for three years following termination of this agreement.",
        "Late payments accrue interest at 1.5 percent per month until the outstanding balance is settled.",
        "Neither party's liability shall exceed the total fees paid in the preceding twelve months."]},

    # ── medical (near-miss = different condition) ────────────────────────────
    {"query": "What causes a heart attack?", "type": "semantic",
     "gold": "A myocardial infarction, or heart attack, is caused by occlusion of a coronary artery — usually a ruptured atherosclerotic plaque — that cuts off blood flow and causes ischemic damage to cardiac muscle.",
     "distractors": [
        "A stroke occurs when blood supply to part of the brain is interrupted, either by a clot or a bleed.",
        "Angina is chest pain from reduced blood flow to the heart that does not cause permanent muscle damage.",
        "Heart failure is the heart's inability to pump enough blood to meet the body's needs.",
        "An arrhythmia is an abnormal heart rhythm that can be too fast, too slow, or irregular.",
        "Hypertension is chronically elevated blood pressure that raises the risk of many cardiac events."]},

    # ── e-commerce (near-miss = same product family) ─────────────────────────
    {"query": "What is the price and size of product SKU7788XL?", "type": "exact",
     "gold": "Product SKU7788XL is the extra-large blue hoodie and is priced at 49 dollars.",
     "distractors": [
        "Product SKU7788LG is the large blue hoodie and is priced at 45 dollars.",
        "Product SKU7788XL2 is the double-extra-large blue hoodie priced at 52 dollars.",
        "Product SKU9921XL is the extra-large red jacket priced at 89 dollars.",
        "The extra-large hoodie is available in blue, black, and grey while stocks last.",
        "Free shipping applies to all hoodie orders over 75 dollars within the domestic region."]},

    # ── networking (near-miss = adjacent protocol detail) ────────────────────
    {"query": "What port does HTTPS use by default?", "type": "exact",
     "gold": "HTTPS uses TCP port 443 by default for encrypted web traffic.",
     "distractors": [
        "HTTP uses TCP port 80 by default for unencrypted web traffic.",
        "SSH uses TCP port 22 by default for encrypted remote shell access.",
        "DNS uses port 53, over UDP for most queries and TCP for zone transfers.",
        "SMTP uses port 25 for mail relay, with 587 for authenticated submission.",
        "PostgreSQL listens on TCP port 5432 by default."]},

    # ── ML / embeddings (near-miss = related ML concept) ─────────────────────
    {"query": "Why must I use the same embedding model for indexing and querying?", "type": "semantic",
     "gold": "Embeddings from different models live in different vector spaces, so a query embedded with one model is not comparable to a corpus embedded with another; you must use the identical model for both index and query.",
     "distractors": [
        "Larger embedding dimensions capture more nuance but increase vector-database memory and storage cost.",
        "Cosine similarity measures the angle between vectors and is the standard metric for comparing embeddings.",
        "Fine-tuning an embedding model on in-domain pairs improves retrieval over generic off-the-shelf models.",
        "Approximate nearest neighbor search trades a little recall for large speed gains over brute force.",
        "Reranking with a cross-encoder rescoring the top-k results improves precision at the top."]},

    # ── devops / logging (near-miss = different signal) ──────────────────────
    {"query": "How do I reduce noisy per-request HTTP logs from our service?", "type": "semantic",
     "gold": "Raise the log level of the HTTP client library (for example set the 'httpx' or 'urllib3' logger to WARNING) so individual request/response lines are suppressed while real warnings still surface.",
     "distractors": [
        "Increase the application's overall log level to ERROR to hide informational messages everywhere.",
        "Ship logs to a centralized aggregator like Loki or Elasticsearch for searching and retention.",
        "Add structured JSON logging so downstream tools can parse fields reliably.",
        "Sample high-volume traces at 10 percent to control observability costs.",
        "Rotate log files daily and compress old ones to save disk space."]},

    # ── caching (near-miss = different cache layer) ──────────────────────────
    {"query": "How can I cut LLM cost when the same long prompt prefix repeats?", "type": "semantic",
     "gold": "Enable provider prompt-prefix caching (Anthropic or OpenAI) so the shared system-prompt/context prefix is cached and billed at a large discount on cache hits, with no code changes beyond marking the prefix.",
     "distractors": [
        "Use a semantic cache that returns a stored answer when a new query is similar to a previous one.",
        "Route simple queries to a smaller, cheaper model and reserve the frontier model for hard ones.",
        "Batch multiple requests together to amortize fixed per-call overhead.",
        "Shorten retrieved context by reranking and keeping only the top few chunks.",
        "Quantize a self-hosted model to reduce GPU memory and increase throughput."]},

    # ── git (near-miss = different command) ──────────────────────────────────
    {"query": "How do I undo the last commit but keep my changes staged?", "type": "exact",
     "gold": "Run 'git reset --soft HEAD~1' to undo the last commit while keeping all its changes staged in the index.",
     "distractors": [
        "Run 'git reset --hard HEAD~1' to undo the last commit and discard all its changes permanently.",
        "Run 'git revert HEAD' to create a new commit that undoes the previous commit without rewriting history.",
        "Run 'git commit --amend' to modify the most recent commit's message or contents.",
        "Run 'git restore --staged <file>' to unstage a file while keeping its working-tree changes.",
        "Run 'git stash' to shelve uncommitted changes and return to a clean working tree."]},

    # ── cloud / storage (near-miss = different service) ──────────────────────
    {"query": "Which AWS service should I use to store large files cheaply?", "type": "mixed",
     "gold": "Amazon S3 is object storage designed for cheaply storing and retrieving large files (objects) at scale, with tiers like S3 Standard and lower-cost S3 Glacier for archives.",
     "distractors": [
        "Amazon EBS provides block storage volumes attached to a single EC2 instance, not shared object storage.",
        "Amazon EFS is a managed elastic file system for POSIX file sharing across many instances.",
        "Amazon RDS is a managed relational database service, not general file storage.",
        "Amazon DynamoDB is a managed key-value and document NoSQL database.",
        "Amazon CloudFront is a CDN that caches content at edge locations closer to users."]},

    # ── rate limiting (near-miss = different mechanism) ──────────────────────
    {"query": "How do I stop a single user from overwhelming the API with requests?", "type": "semantic",
     "gold": "Apply per-user rate limiting (for example a token-bucket limit of N requests per minute keyed by user or API key) so one client cannot exhaust capacity for others.",
     "distractors": [
        "Add a caching layer so repeated identical requests are served without hitting the backend.",
        "Horizontally scale the service behind a load balancer to add more capacity.",
        "Use a circuit breaker to stop calling a downstream dependency that is failing.",
        "Validate and sanitize all input to prevent injection attacks.",
        "Enable gzip compression to reduce response payload sizes."]},
]


def get_eval_data(seed: int = 7):
    """Return (corpus, queries). corpus is a list[str]; queries is a list of dicts
    {query, gold_id, type}. The corpus is deterministically shuffled so gold documents
    are not positionally adjacent to their distractors."""
    corpus, gold_texts = [], []
    for t in TOPICS:
        gold_texts.append(t["gold"])
        corpus.append(t["gold"])
        corpus.extend(t["distractors"])
    rng = random.Random(seed)
    order = list(range(len(corpus)))
    rng.shuffle(order)
    shuffled = [corpus[i] for i in order]
    pos = {old: new for new, old in enumerate(order)}  # old index -> new index
    queries = []
    idx = 0
    running = 0
    for t in TOPICS:
        gold_old = running
        running += 1 + len(t["distractors"])
        queries.append({"query": t["query"], "gold_id": pos[gold_old], "type": t["type"]})
    return shuffled, queries


if __name__ == "__main__":
    c, q = get_eval_data()
    print(f"{len(c)} passages, {len(q)} queries")
    print("types:", {t: sum(1 for x in q if x['type'] == t) for t in {'exact','semantic','mixed'}})
    assert all(c[x["gold_id"]] for x in q)
    print("sample query:", q[0])
    print("its gold    :", c[q[0]["gold_id"]][:80])
