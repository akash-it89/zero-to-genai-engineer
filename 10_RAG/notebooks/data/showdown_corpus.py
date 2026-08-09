"""
Corpus + ground truth for the retrieval showdown notebook.

Structure:
  - HAND-CRAFTED docs (indices 0..N) are written and verified individually.
    These are the ones the 10 ground-truth queries point at, plus their
    deliberate "trap" distractors (lexical lures, hard negatives, near-dupes).
  - FILLER docs (appended after) exist purely to give the corpus real scale
    (500+) and real competition, generated from templates across many
    domains so retrieval has to do real work, not win by default.

Returns:
  corpus: List[str]            -- passage texts, index = doc_id
  queries: List[dict]           -- the 10 ground-truth queries
"""

import itertools

# ============================================================================
# HAND-CRAFTED, GOLD-CRITICAL DOCUMENTS
# ============================================================================
# Each block below is deliberately built for ONE lesson. Comments mark the
# doc_id each query will reference (indices are stable because these are
# added to the corpus list first, before any filler).

hand_crafted = []

def add(text):
    hand_crafted.append(text)
    return len(hand_crafted) - 1  # doc_id within hand_crafted, offset later

# --- Q1: exact rare token, BM25's home turf -------------------------------
Q1_GOLD = add(
    "Error ERR_DB_CONN_9042 occurs when the connection pool to the primary "
    "database exhausts its available slots. Fix: raise max_connections in "
    "postgresql.conf and restart the pooler."
)
Q1_DECOY = add(
    "Database connection errors are commonly caused by network timeouts, "
    "expired credentials, or a full connection pool. Check the pooler logs "
    "for the specific failure reason before escalating."
)

# --- Q2: pure vocabulary gap, dense's home turf ----------------------------
Q2_GOLD = add(
    "Myocardial infarction results from acute occlusion of a coronary "
    "artery, causing ischemic necrosis of the affected cardiac muscle "
    "tissue."
)
# competing clinical passages so dense has to discriminate topic, not just
# win by being the only medical document in the corpus
Q2_DECOY_A = add(
    "A cerebrovascular accident occurs when blood supply to a region of the "
    "brain is interrupted or severely reduced, depriving tissue of oxygen."
)
Q2_DECOY_B = add(
    "Cardiac arrhythmia refers to any irregularity in the heart's electrical "
    "conduction system, ranging from harmless to life-threatening."
)
Q2_DECOY_C = add(
    "Type 2 diabetes develops when the body becomes resistant to insulin or "
    "does not produce enough of it, leading to elevated blood glucose."
)

# --- Q3: lexical lure, BM25 gets fooled by shared surface words -----------
Q3_GOLD = add(
    "Photosynthesis converts sunlight, water, and carbon dioxide into "
    "glucose and oxygen within the chloroplasts of plant leaf cells."
)
Q3_LURE = add(
    "Our food processing plant installed rooftop solar panels last year to "
    "offset its sunlight-powered energy costs, and now produces packaged "
    "snacks and ready meals across two production lines."
)

# --- Q4: version-number token fragmentation, BM25's tokenizer weak spot --
Q4_GOLD = add(
    "Python 3.11 introduced fine-grained error locations in tracebacks and "
    "exception groups, letting a single except* clause handle multiple "
    "concurrent exceptions."
)
Q4_DECOY_A = add(
    "Python 3.10 introduced structural pattern matching with the new match "
    "statement, allowing destructuring of sequences, mappings, and classes."
)
Q4_DECOY_B = add(
    "Python 3.9 added dictionary merge and update operators, plus relaxed "
    "grammar restrictions for decorator expressions."
)
Q4_DECOY_C = add(
    "Python 3.12 improved f-string parsing flexibility and introduced a "
    "per-interpreter GIL for better multi-interpreter isolation."
)

# --- Q5: hybrid rescue -- BM25 and dense each prefer a DIFFERENT wrong doc,
# so RRF's consensus (gold is decent in both lists) should recover gold at #1
Q5_GOLD = add(
    "After updating a record, a stale read usually means a cache layer in "
    "front of the database has not yet been invalidated. Fix: explicitly "
    "invalidate or set a short TTL on the cache key for that record."
)
Q5_BM25_LURE = add(
    "Stale reads after a write can be explained by several different "
    "causes across a distributed system, including cache invalidation "
    "delays, replication lag, and client-side response caching, each with "
    "its own separate troubleshooting path."
)
Q5_DENSE_LURE = add(
    "Caching frequently accessed responses reduces load on the database, "
    "but every cache introduces a tradeoff between freshness and "
    "performance that a team must explicitly manage over time."
)

# --- Q6: naive score addition breaks, normalization fixes it --------------
# reuse the same structural setup as Q1 (rare exact token vs a topically
# close, high-BM25-score decoy) so the raw-score-scale mismatch is visible
Q6_GOLD = add(
    "HTTP 429 Too Many Requests means the client has exceeded the API's "
    "rate limit. Read the Retry-After header and back off before retrying "
    "the request."
)
Q6_DECOY = add(
    "Rate limiting protects an API from being overwhelmed by too many "
    "requests too many requests too many requests in a short window, "
    "returning HTTP 429 responses once the quota for the current period is "
    "exhausted."
)

# --- Q7: SPLADE's learned expansion -----------------------------------------
Q7_GOLD = add(
    "Increase the statement_timeout setting to prevent a single long-running "
    "query from holding locks and blocking other transactions indefinitely."
)
Q7_NEAR = add(
    "Use connection pooling to limit the number of concurrent open "
    "connections a service can hold against the database at any one time."
)

# --- Q8: hybrid still imperfect, cross-encoder rerank fixes final order ---
Q8_GOLD = add(
    "Raise the log level of the HTTP client library, for example to WARNING, "
    "to stop it from emitting a debug line for every single outbound "
    "request and response."
)
Q8_HARD_NEGATIVE = add(
    "Batch multiple outbound requests together to amortize fixed per-call "
    "overhead when calling a downstream service."
)

# --- Q9: hard negative, a negation flip that bag-of-words methods struggle
# with -- every content word is identical in both documents, the only
# difference is "supports" vs "does not support"
Q9_GOLD = add(
    "The TW-500 headphone supports multipoint Bluetooth pairing with two "
    "devices at once."
)
Q9_HARD_NEGATIVE = add(
    "The TW-400 headphone does not support multipoint Bluetooth pairing "
    "with two devices at once."
)

# --- Q10: full pipeline finale, exact token + natural language together --
Q10_GOLD = add(
    "CVE-2024-51902 affects the internal auth-gateway service prior to "
    "version 4.3.2 due to improper JWT signature verification, allowing "
    "token forgery. Upgrade to 4.3.2 or later to remediate."
)
Q10_DECOY_A = add(
    "Improper input validation in the legacy reporting module could allow "
    "a crafted filename to escape the export directory. Tracked as an "
    "internal hardening item, not yet assigned a CVE."
)
Q10_DECOY_B = add(
    "JWT signature verification should always use a constant-time "
    "comparison to avoid timing attacks that leak information about the "
    "expected signature byte by byte."
)
Q10_DECOY_C = add(
    "CVE-2024-51899 affects the internal auth-gateway service prior to "
    "version 4.1.0 due to a missing rate limit on the login endpoint, "
    "allowing credential-stuffing attacks. Upgrade to 4.1.0 or later to "
    "remediate."
)

# --- Q1 extra: a whole FAMILY of near-duplicate error codes, same domain,
# same phrasing style, only the digits and the specific cause/fix differ.
# This is the real stress test for dense: an arbitrary numeric suffix isn't
# something an embedding model has any reason to preserve exactly, so as
# more near-identical codes crowd the same semantic neighborhood, dense's
# confidence in the ONE exact match should degrade. BM25's exact-token
# match is completely unaffected by how many similar-looking codes exist
# elsewhere, because none of them literally contains the string "9042".
Q1_CLOSE_DECOY = add(
    "Error ERR_DB_CONN_9043 occurs when a read replica falls too far behind "
    "the primary due to replication lag. Fix: monitor replica lag and add "
    "read replicas or reduce write load."
)
Q1_FAMILY_2 = add(
    "Error ERR_DB_CONN_9044 occurs when the connection pool to the primary "
    "database rejects new connections because the maximum client limit has "
    "been reached. Fix: raise max_connections or add a connection pooler in "
    "front of the database."
)
Q1_FAMILY_3 = add(
    "Error ERR_DB_CONN_9045 occurs when the connection pool to the primary "
    "database times out waiting for an idle connection to become available. "
    "Fix: increase the pool's wait timeout or shrink the checkout duration "
    "per request."
)
Q1_FAMILY_4 = add(
    "Error ERR_DB_CONN_9046 occurs when the connection pool to the primary "
    "database drops connections that have been idle longer than the "
    "server's configured idle timeout. Fix: lower the pool's idle timeout "
    "below the server's limit."
)
Q1_FAMILY_5 = add(
    "Error ERR_DB_CONN_9047 occurs when the connection pool to the primary "
    "database exhausts its available slots under a sudden traffic spike. "
    "Fix: add autoscaling to the pool size or queue excess requests instead "
    "of failing them."
)
Q1_FAMILY_6 = add(
    "Error ERR_DB_CONN_9048 occurs when the connection pool to the primary "
    "database cannot open new connections because the underlying TCP port "
    "range on the host has been exhausted. Fix: widen the ephemeral port "
    "range or reuse existing connections."
)
Q1_FAMILY_7 = add(
    "Error ERR_DB_CONN_9049 occurs when the connection pool to the primary "
    "database rejects connections during a failover, before the new primary "
    "has finished promotion. Fix: add retry with backoff around the initial "
    "connection attempt."
)
Q1_FAMILY_8 = add(
    "Error ERR_DB_CONN_9050 occurs when the connection pool to the primary "
    "database exhausts its available slots because a long-running "
    "background job never returns its connections. Fix: add a connection "
    "checkout timeout so idle jobs are forcibly reclaimed."
)

# --- Q4 (revised): saturation resistance, a keyword-stuffed decoy shouldn't
# beat a concise, genuinely correct answer, testing whether BM25's TF
# saturation (learned in notebook 06) actually holds up in a bigger corpus
Q4_GOLD = add(
    "Increase the read timeout on the HTTP client to avoid premature "
    "connection resets during slow upstream responses."
)
Q4_STUFFED_DECOY = add(
    "Timeout configuration requires careful timeout tuning. Set the "
    "timeout value, check the timeout default, and confirm every timeout "
    "parameter in the timeout section of the timeout configuration file "
    "before assuming a timeout is the cause of any given timeout."
)

N_HAND_CRAFTED = len(hand_crafted)

# ============================================================================
# THE 10 GROUND-TRUTH QUERIES
# ============================================================================
# gold_id is filled in after filler is appended (hand-crafted indices are
# stable since filler is appended AFTER, so no offset is needed here).

QUERIES = [
    {
        "name": "exact_token",
        "query": "ERR_DB_CONN_9042 fix",
        "gold_id": Q1_GOLD,
        "lesson": "BM25 should win decisively: the code is rare (appears once), "
                  "giving it a huge IDF weight. This proves BM25's value on "
                  "exact identifiers.",
    },
    {
        "name": "vocabulary_gap",
        "query": "what is a heart attack",
        "gold_id": Q2_GOLD,
        "lesson": "BM25 should score this exactly 0.000, zero shared words "
                  "with the clinical phrasing. Dense should win by understanding "
                  "meaning across a vocabulary gap.",
    },
    {
        "name": "lexical_lure",
        "query": "how do plants make food using sunlight",
        "gold_id": Q3_GOLD,
        "lesson": "BM25 should get fooled by the 'food processing plant' "
                  "distractor sharing surface words. Dense should correctly "
                  "identify this is about photosynthesis.",
    },
    {
        "name": "saturation_resistance",
        "query": "what timeout setting fixes premature connection resets",
        "gold_id": Q4_GOLD,
        "lesson": "A decoy repeats 'timeout' many times, hoping to win on raw "
                  "term frequency. BM25's saturation (k1), taught in notebook "
                  "06, should cap how much that repetition can pay off, so the "
                  "concise, genuinely correct document still wins.",
    },
    {
        "name": "hybrid_rescue",
        "query": "why am I getting stale data right after updating a record",
        "gold_id": Q5_GOLD,
        "lesson": "BM25 and dense should each be individually imperfect here, "
                  "distracted by a different decoy. RRF fusion should recover "
                  "the gold document at #1 because it's the one both retrievers "
                  "actually agree is good.",
    },
    {
        "name": "naive_sum_breaks",
        "query": "getting HTTP 429 too many requests from the API",
        "gold_id": Q6_GOLD,
        "lesson": "Adding raw BM25 + raw cosine directly should let the decoy "
                  "(which repeats 'too many requests' for a large BM25 score) "
                  "beat the gold document. Min-max normalizing first should fix "
                  "it.",
    },
    {
        "name": "splade_bridge",
        "query": "how to stop one query from blocking other transactions",
        "gold_id": Q7_GOLD,
        "lesson": "Tests whether SPLADE's learned term expansion finds the "
                  "statement_timeout fix even without an exact keyword match, "
                  "and how it compares honestly to BM25 and dense here.",
    },
    {
        "name": "rerank_fixes_hybrid",
        "query": "how do I reduce noisy per-request HTTP logs from our service",
        "gold_id": Q8_GOLD,
        "lesson": "Hybrid fusion may still leave the gold document at #2 behind "
                  "a plausible-sounding hard negative. A cross-encoder, judging "
                  "the exact pair directly, should promote gold to #1.",
    },
    {
        "name": "hard_negative",
        "query": "which headphone supports multipoint pairing with two devices at once",
        "gold_id": Q9_GOLD,
        "lesson": "Gold and hard-negative are word-for-word identical except "
                  "'supports' vs 'does not support'. Tests whether shallow "
                  "bag-of-words and embedding methods can actually tell a "
                  "negation apart, or whether only a cross-encoder reading "
                  "both sentences fully gets it right.",
    },
    {
        "name": "full_pipeline_finale",
        "query": "CVE-2024-51902 auth gateway JWT vulnerability fix",
        "gold_id": Q10_GOLD,
        "lesson": "Combines an exact rare identifier with natural-language "
                  "phrasing. Tests whether the full pipeline, fusion plus "
                  "reranking, is what reliably nails both parts at once.",
    },
]


# ============================================================================
# TEMPLATED FILLER -- gives the corpus real scale and real competition
# ============================================================================

def _http_status_docs():
    codes = [
        ("400 Bad Request", "the request body or parameters failed validation on the server"),
        ("401 Unauthorized", "the request is missing valid authentication credentials"),
        ("403 Forbidden", "the caller is authenticated but lacks permission for this resource"),
        ("404 Not Found", "the requested resource does not exist at this URL"),
        ("405 Method Not Allowed", "the HTTP method used is not supported on this endpoint"),
        ("409 Conflict", "the request conflicts with the current state of the resource"),
        ("413 Payload Too Large", "the request body exceeds the server's configured size limit"),
        ("422 Unprocessable Entity", "the request is well-formed but semantically invalid"),
        ("500 Internal Server Error", "an unexpected condition was encountered on the server"),
        ("502 Bad Gateway", "the upstream server returned an invalid response to the gateway"),
        ("503 Service Unavailable", "the server is temporarily overloaded or down for maintenance"),
        ("504 Gateway Timeout", "the upstream server did not respond within the gateway's timeout"),
    ]
    return [f"HTTP {code} means {meaning}." for code, meaning in codes]


def _k8s_error_docs():
    errors = [
        ("ImagePullBackOff", "Kubernetes cannot pull the container image, often due to a wrong tag or missing registry credentials"),
        ("OOMKilled", "the container exceeded its memory limit and was killed by the kernel's out-of-memory handler"),
        ("ErrImageNeverPull", "the image pull policy is set to Never but the image is not present locally on the node"),
        ("Evicted", "the node ran low on a resource such as memory or disk and the scheduler evicted the pod"),
        ("CreateContainerConfigError", "the container spec references a ConfigMap or Secret key that does not exist"),
        ("NodeNotReady", "the kubelet on the node has stopped reporting a healthy status to the control plane"),
        ("FailedScheduling", "no node currently satisfies the pod's resource requests, taints, or affinity rules"),
        ("Terminating stuck", "a pod is stuck terminating because a finalizer has not been removed"),
        ("BackOff pulling image", "repeated failed image pulls trigger an exponential backoff before the next retry"),
        ("ContainerCreating stuck", "the pod is stuck creating containers because a volume mount cannot be attached"),
    ]
    return [f"Kubernetes {name} occurs when {meaning}." for name, meaning in errors]


def _ecommerce_docs():
    items = ["hoodie", "t-shirt", "jacket", "backpack", "sneaker", "cap", "water bottle", "wireless mouse", "keyboard", "desk lamp"]
    sizes = ["small", "medium", "large", "extra-large"]
    colors = ["black", "navy", "grey", "olive", "white", "red"]
    docs = []
    for item, size, color in itertools.product(items, sizes, colors):
        price = 19 + (hash((item, size, color)) % 60)
        docs.append(
            f"Product {item.upper().replace(' ', '')}-{size[:2].upper()}-{color[:3].upper()} "
            f"is the {size} {color} {item}, priced at {price} dollars, available while stocks last."
        )
    return docs  # 10 x 4 x 6 = 240 unique combinations


def _cloud_error_docs():
    errors = [
        ("AWS S3 AccessDenied", "the IAM policy attached to the caller does not grant s3:GetObject on that bucket path"),
        ("AWS Lambda task timed out", "the function ran longer than its configured timeout and was forcibly stopped"),
        ("AWS RDS connection refused", "the security group does not allow inbound traffic from the caller's subnet"),
        ("GCP 403 PERMISSION_DENIED", "the service account lacks the IAM role required for that API call"),
        ("GCP quota exceeded", "the project has hit its per-minute quota for that API and must request a limit increase"),
        ("Azure 401 InvalidAuthenticationToken", "the bearer token has expired or was issued for a different resource audience"),
        ("Azure throttling 429", "too many requests were sent to the resource within the configured rate window"),
        ("S3 SlowDown error", "the bucket is receiving requests faster than S3 can currently process them for that prefix"),
        ("Terraform state lock error", "another process is already holding a lock on the remote state file"),
        ("Docker no space left on device", "the host's disk is full, often from unpruned images, layers, or build cache"),
        ("CloudFront 502 from origin", "the origin server closed the connection or returned malformed headers to CloudFront"),
        ("IAM AssumeRole denied", "the trust policy on the target role does not list the calling principal as trusted"),
    ]
    return [f"{name} happens when {meaning}." for name, meaning in errors]


def _general_tech_docs():
    return [
        "A load balancer distributes incoming traffic across multiple backend servers to improve availability.",
        "A content delivery network caches static assets at edge locations closer to end users.",
        "Idempotent APIs can be safely retried because repeating the same request produces the same result.",
        "A circuit breaker stops calling a failing downstream service temporarily to let it recover.",
        "Blue-green deployment runs two identical environments and switches traffic once the new one is verified.",
        "A canary release exposes a new version to a small percentage of traffic before a full rollout.",
        "Feature flags let a team enable or disable functionality without deploying new code.",
        "Horizontal scaling adds more machines to handle load; vertical scaling adds more power to one machine.",
        "A message queue decouples producers and consumers, letting them operate at different speeds.",
        "Eventual consistency means replicas may briefly disagree before converging to the same value.",
        "A webhook is an HTTP callback triggered automatically when a specific event occurs in another system.",
        "Rate limiting protects a service from being overwhelmed by capping requests per client per time window.",
        "A reverse proxy sits in front of backend servers, handling TLS termination and request routing.",
        "Distributed tracing links log spans across services so a single request can be followed end to end.",
        "A cron job runs a script on a fixed schedule, independent of any user-triggered request.",
        "Infrastructure as code defines cloud resources in version-controlled files instead of manual clicks.",
        "A service mesh manages service-to-service traffic, retries, and observability without app code changes.",
        "Graceful shutdown lets a process finish in-flight requests before terminating on a deploy or scale-down.",
        "A dead-letter queue captures messages that repeatedly fail processing so they can be inspected later.",
        "Backpressure signals to a producer that a consumer cannot keep up, so it should slow down.",
        "A read-through cache fetches from the database on a miss and stores the result for the next request.",
        "Optimistic locking checks a version number before writing, failing the write if it has changed.",
        "A sidecar container runs alongside the main application container, sharing its network namespace.",
        "Chaos engineering deliberately injects failures into a system to verify it degrades gracefully.",
        "A monorepo keeps multiple related projects in a single version-controlled repository.",
    ]


def _general_knowledge_docs():
    return [
        "The Pacific Ocean is the largest and deepest of Earth's five oceanic divisions.",
        "Mount Everest, on the border of Nepal and Tibet, is the highest mountain above sea level.",
        "The Amazon rainforest produces a significant share of the world's oxygen and biodiversity.",
        "The Sahara is the largest hot desert in the world, spanning much of North Africa.",
        "The Great Barrier Reef off Australia is the largest living structure visible from space.",
        "The printing press, credited to Gutenberg, dramatically increased the spread of written knowledge.",
        "The Industrial Revolution began in Britain in the late eighteenth century, transforming manufacturing.",
        "The Roman Empire at its height controlled territory spanning three continents.",
        "The Renaissance was a period of renewed interest in classical art, science, and philosophy in Europe.",
        "The moon landing in 1969 was the first time humans set foot on another celestial body.",
        "A light-year is the distance light travels in one year, used to measure astronomical distances.",
        "The speed of light in a vacuum is approximately 300,000 kilometers per second.",
        "Jupiter is the largest planet in the solar system, more than twice as massive as all other planets combined.",
        "A solar eclipse occurs when the moon passes between the Earth and the Sun, blocking its light.",
        "Photosynthesis and cellular respiration are, in a simplified sense, chemical opposites of each other.",
        "DNA carries genetic instructions in a double helix structure discovered by Watson and Crick in 1953.",
        "The human heart beats roughly one hundred thousand times per day at rest.",
        "Antibiotics treat bacterial infections but have no effect on viral infections like the common cold.",
        "Vaccines train the immune system to recognize a pathogen without causing the disease itself.",
        "The stock market's daily closing price reflects the last trade executed before the exchange closes.",
        "Inflation measures the rate at which the general price level of goods and services rises over time.",
        "A recession is commonly defined as two consecutive quarters of declining economic output.",
        "Compound interest grows a balance faster over time than simple interest on the same principal.",
        "A currency's exchange rate reflects its relative value against another currency in the market.",
        "The World Wide Web was proposed by Tim Berners-Lee in 1989 as a way to share documents over the internet.",
    ]


def _medical_pairs_docs():
    pairs = [
        ("hypertension", "chronically elevated blood pressure in the arterial system"),
        ("osteoarthritis", "degeneration of joint cartilage causing pain and stiffness"),
        ("gastroesophageal reflux disease", "backward flow of stomach acid into the esophagus"),
        ("chronic obstructive pulmonary disease", "long-term airflow obstruction commonly caused by smoking"),
        ("anemia", "a deficiency of healthy red blood cells or hemoglobin"),
        ("hyperthyroidism", "excessive production of thyroid hormone by the thyroid gland"),
        ("nephrolithiasis", "the formation of hard mineral deposits within the kidney"),
        ("appendicitis", "inflammation of the appendix, often requiring surgical removal"),
        ("dermatitis", "inflammation of the skin causing redness, itching, or swelling"),
        ("tachycardia", "an abnormally fast resting heart rate"),
        ("hepatic steatosis", "an abnormal accumulation of fat within liver cells"),
        ("otitis media", "an infection of the middle ear, common in young children"),
        ("pharyngitis", "inflammation of the throat, often causing pain when swallowing"),
        ("conjunctivitis", "inflammation of the membrane covering the white of the eye"),
        ("osteoporosis", "a loss of bone density that increases fracture risk"),
    ]
    lay = {
        "hypertension": "high blood pressure",
        "osteoarthritis": "worn-out, achy joints from age",
        "gastroesophageal reflux disease": "acid reflux, or heartburn",
        "chronic obstructive pulmonary disease": "COPD, a smoker's lung disease",
        "anemia": "low iron or low red blood cell count",
        "hyperthyroidism": "an overactive thyroid",
        "nephrolithiasis": "a kidney stone",
        "appendicitis": "a burst or inflamed appendix",
        "dermatitis": "a skin rash",
        "tachycardia": "a racing heartbeat",
        "hepatic steatosis": "a fatty liver",
        "otitis media": "a middle ear infection",
        "pharyngitis": "a sore throat",
        "conjunctivitis": "pink eye",
        "osteoporosis": "brittle, weakening bones",
    }
    docs = []
    for clinical, definition in pairs:
        docs.append(f"{clinical.capitalize()} refers to {definition}.")
        docs.append(f"Most people would just call it {lay[clinical]}, without ever using the clinical term.")
    return docs


def _legal_hr_docs():
    clauses = [
        "Either party may terminate this agreement with sixty days written notice to the other party.",
        "Confidential information disclosed under this agreement may not be shared with third parties without written consent.",
        "This agreement is governed by the laws of the jurisdiction in which the provider is incorporated.",
        "Neither party's aggregate liability shall exceed the fees paid in the twelve months preceding the claim.",
        "Employees working remotely at least three days per week are eligible for a monthly home-internet stipend.",
        "New engineers receive laptop provisioning within two business days and VPN access on their first day.",
        "Unused vacation days may be carried over into the next calendar year up to a maximum of five days.",
        "Expense reports submitted more than ninety days after the purchase date will not be reimbursed.",
        "A performance improvement plan must be documented and reviewed with the employee before any termination for performance.",
        "Overtime for non-exempt employees is calculated at one and a half times the regular hourly rate.",
        "Intellectual property created during the course of employment belongs to the employer by default.",
        "A signing bonus is repayable in full if the employee resigns within the first twelve months.",
        "The probationary period for new hires is ninety calendar days from the start date.",
        "Parental leave provides twelve weeks of paid leave for the primary caregiver following a birth or adoption.",
        "Non-compete clauses in this contract are limited to a twelve month period within the same industry segment.",
    ]
    return clauses


def _finance_docs():
    return [
        "A 401k is a tax-advantaged retirement savings plan sponsored by an employer, often with a matching contribution.",
        "An IRA is an individual retirement account with annual contribution limits set by tax authorities each year.",
        "A Roth IRA is funded with after-tax dollars, so qualified withdrawals in retirement are tax-free.",
        "A Health Savings Account lets eligible individuals set aside pre-tax money for qualified medical expenses.",
        "A 529 plan is a tax-advantaged account designed to encourage saving for future education costs.",
        "A defined-benefit pension pays a fixed retirement income based on salary history and years of service.",
        "A brokerage account has no contribution limits but offers no special tax advantages on capital gains.",
        "Dollar-cost averaging invests a fixed amount at regular intervals, reducing the impact of market timing.",
        "A traditional IRA allows pre-tax contributions but taxes withdrawals as ordinary income in retirement.",
        "An emergency fund should typically cover three to six months of essential living expenses.",
    ]


def _database_docs():
    return [
        "Postgres may ignore an index when a query's WHERE clause wraps the indexed column in a function call.",
        "MySQL's query cache was removed in version 8.0 in favor of application-level or proxy-level caching.",
        "A missing index on a foreign key column is one of the most common causes of slow join performance.",
        "Vacuuming in Postgres reclaims storage occupied by dead tuples left behind by updates and deletes.",
        "A composite index only helps a query if the leading column of the index appears in the WHERE clause.",
        "Read replicas offload read-heavy traffic from the primary database but introduce replication lag.",
        "An N+1 query problem happens when an application issues one query per row instead of a single join.",
        "Connection pooling reduces the overhead of repeatedly opening and closing database connections per request.",
        "A full table scan happens when no usable index exists, forcing the database to read every row.",
        "Partitioning a large table by date range can significantly speed up queries that filter on recent data.",
    ]


def _science_lure_docs():
    return [
        "A river bank is the land alongside a river channel, shaped over time by erosion and sediment deposit.",
        "A financial bank accepts deposits and extends credit, regulated separately from riverine geography.",
        "A coil spring stores mechanical energy and releases it to absorb shock in vehicle suspensions.",
        "Spring is the season between winter and summer, marked by warming temperatures and new plant growth.",
        "A natural spring is a point where groundwater emerges naturally at the surface of the earth.",
        "The Python programming language emphasizes readability and was first released in 1991.",
        "A python is a large non-venomous constrictor snake found across Africa, Asia, and Australia.",
        "A server rack cools its equipment using fans, while a coat rack simply holds hanging garments.",
        "A byte is a unit of digital information, while bite refers to the act of biting with teeth.",
        "The mole in chemistry is a unit for counting particles, unrelated to the small burrowing mammal.",
    ]


def _networking_docs():
    return [
        "A DNS record maps a human-readable domain name to a machine-usable IP address.",
        "TCP guarantees ordered, reliable delivery of data, at the cost of more overhead than UDP.",
        "UDP sends packets without establishing a connection first, favoring speed over reliability.",
        "A subnet mask determines which portion of an IP address identifies the network versus the host.",
        "TLS encrypts traffic between a client and server and verifies the server's identity via a certificate.",
        "A firewall filters network traffic based on rules defined by source, destination, and port.",
        "NAT translates private internal IP addresses to a single public IP address for outbound traffic.",
        "A VPN creates an encrypted tunnel over the public internet between two private networks.",
        "An MTU defines the largest packet size that can be transmitted without fragmentation on a link.",
        "BGP is the routing protocol that exchanges reachability information between autonomous systems on the internet.",
        "A load balancer health check periodically probes backend servers to remove unhealthy ones from rotation.",
        "An ARP request resolves a known IP address to the corresponding hardware MAC address on a local network.",
        "A CDN's edge cache reduces latency by serving content from a location near the requesting user.",
        "Packet loss on a network link often shows up first as increased latency and retransmissions.",
        "A default gateway is the router a device sends traffic to when the destination is outside its local subnet.",
        "An SSL certificate's chain of trust is validated up to a root certificate authority.",
        "A proxy server relays requests on behalf of a client, optionally caching or filtering responses.",
        "Jitter measures the variation in packet arrival time, which matters most for real-time voice or video.",
        "A VLAN logically separates traffic on a shared physical network without needing separate hardware.",
        "Round-trip time measures how long a packet takes to reach a destination and return a response.",
    ]


def _testing_cicd_docs():
    return [
        "A unit test verifies a single function or method in isolation from the rest of the system.",
        "An integration test verifies that multiple components work correctly together.",
        "End-to-end tests exercise a full user flow through the real application, often the slowest test type.",
        "A flaky test passes and fails intermittently without any code change, undermining trust in the suite.",
        "Code coverage measures the percentage of code executed by the test suite, not the quality of the tests.",
        "A mock replaces a real dependency with a controllable stand-in during a test.",
        "Continuous integration automatically builds and tests every code change pushed to the repository.",
        "Continuous deployment automatically ships every change that passes its pipeline straight to production.",
        "A build pipeline typically runs linting, unit tests, and a build step before an artifact is published.",
        "Test-driven development writes a failing test before writing the code that makes it pass.",
        "A regression test suite guards against previously fixed bugs reappearing in future changes.",
        "Snapshot testing compares a component's rendered output against a previously saved reference.",
        "A staging environment mirrors production closely enough to catch issues before a real release.",
        "Rolling back a deployment reverts to the previous known-good version when a release causes problems.",
        "Static analysis inspects source code without running it, catching certain bugs before tests even run.",
        "A pre-commit hook runs quick checks locally before a commit is allowed to be created.",
        "Load testing measures how a system behaves under expected or peak traffic before it ships.",
        "A smoke test runs a minimal set of checks right after deployment to confirm the basics still work.",
        "Mutation testing intentionally introduces small bugs to check whether the test suite catches them.",
        "A code review gate requires at least one approval before a pull request can be merged.",
        "Semantic versioning encodes breaking, additive, and patch changes into the major, minor, and patch numbers.",
        "A changelog documents what changed between releases so users can assess the impact of upgrading.",
        "Trunk-based development keeps changes small and merges to the main branch frequently.",
        "A feature branch isolates in-progress work until it's ready to be reviewed and merged.",
        "An artifact repository stores built packages so a pipeline doesn't need to rebuild them for every deploy.",
    ]


def _more_legal_docs():
    return [
        "A force majeure clause excuses performance when an extraordinary event beyond either party's control occurs.",
        "An indemnification clause requires one party to compensate the other for certain losses or claims.",
        "A most-favored-nation clause guarantees a customer terms at least as good as those given to any other customer.",
        "An assignment clause restricts whether a party may transfer its rights under the contract to a third party.",
        "A severability clause keeps the rest of a contract valid even if one clause is found unenforceable.",
        "An arbitration clause requires disputes to be resolved outside of court, typically through a neutral arbitrator.",
        "A right of first refusal gives a party the option to match any offer before the other party sells to someone else.",
        "An entire agreement clause states that the written contract supersedes all prior discussions or promises.",
        "A notice clause specifies the required method and address for formally notifying the other party.",
        "A most-recent amendment supersedes any conflicting term in the earlier version of the same agreement.",
    ]


def _more_database_docs():
    return [
        "A deadlock occurs when two transactions each hold a lock the other one needs, and neither can proceed.",
        "Row-level locking allows other transactions to modify different rows in the same table concurrently.",
        "A covering index contains every column a query needs, letting the database avoid a lookup of the full row.",
        "Database sharding splits a large dataset across multiple independent database instances by a shard key.",
        "A write-ahead log records changes before they are applied, enabling crash recovery to a consistent state.",
        "An ORM maps application objects to database rows, trading some query control for developer convenience.",
        "A materialized view stores a query's result physically, refreshed periodically instead of recomputed live.",
        "Optimizer statistics tell the query planner how many rows to expect, directly affecting the chosen query plan.",
        "A B-tree index keeps data sorted, making range queries and equality lookups both efficient.",
        "Isolation levels trade consistency guarantees for concurrency, from read uncommitted up to serializable.",
    ]


def _more_finance_docs():
    return [
        "A high-yield savings account typically pays a variable interest rate higher than a standard checking account.",
        "A certificate of deposit locks funds for a fixed term in exchange for a fixed, usually higher, interest rate.",
        "Diversification spreads investment risk across assets so no single holding can sink an entire portfolio.",
        "A credit score summarizes borrowing history into a number lenders use to assess repayment risk.",
        "An index fund passively tracks a market index rather than trying to beat it through active stock picking.",
    ]


def _language_comparison_docs():
    return [
        "JavaScript runs natively in every major web browser without any separate compilation step.",
        "Rust enforces memory safety at compile time through its ownership and borrowing system, without a garbage collector.",
        "Go compiles to a single static binary and includes goroutines for lightweight concurrent execution.",
        "Java runs on the JVM, giving it portability across operating systems at the cost of some startup overhead.",
        "TypeScript adds static typing on top of JavaScript, catching many errors before the code ever runs.",
        "C is a low-level language that gives direct control over memory, with no automatic garbage collection.",
        "Ruby favors developer happiness and readable syntax, historically popular for fast-moving web startups.",
        "Swift is Apple's language for iOS and macOS development, replacing Objective-C as the modern default.",
        "Kotlin is fully interoperable with Java and is Google's recommended language for Android development.",
        "SQL is a declarative language for querying and manipulating data in a relational database.",
        "Bash scripting automates command-line tasks and is the default shell scripting language on most Linux systems.",
        "R is widely used in statistics and data analysis, with a large ecosystem of packages for that purpose.",
        "PHP still powers a large share of the web through content management systems built on top of it.",
        "Scala combines object-oriented and functional programming and runs on the JVM alongside Java.",
        "Haskell is a purely functional language where functions have no side effects by default.",
    ]


def build_corpus():
    corpus = list(hand_crafted)
    corpus += _http_status_docs()
    corpus += _k8s_error_docs()
    corpus += _ecommerce_docs()
    corpus += _legal_hr_docs()
    corpus += _database_docs()
    corpus += _finance_docs()
    corpus += _science_lure_docs()
    corpus += _cloud_error_docs()
    corpus += _general_tech_docs()
    corpus += _general_knowledge_docs()
    corpus += _medical_pairs_docs()
    corpus += _networking_docs()
    corpus += _testing_cicd_docs()
    corpus += _more_legal_docs()
    corpus += _more_database_docs()
    corpus += _more_finance_docs()
    corpus += _language_comparison_docs()
    return corpus


def get_showdown_data():
    corpus = build_corpus()
    return corpus, QUERIES


if __name__ == "__main__":
    c, q = get_showdown_data()
    print(f"corpus size: {len(c)}")
    print(f"hand-crafted: {N_HAND_CRAFTED}")
    print(f"queries: {len(q)}")
    for query in q:
        print(f"  {query['name']:24} gold={query['gold_id']:4}  {query['query']}")
