# Group 5 — NIH Consumer Health Information Assistant (informational only — NOT medical advice)

## Requirement
Build a RAG chatbot modeled on **MedlinePlus** (the NIH/National Library of Medicine's real consumer health information service) that answers general health questions and always defers anything diagnostic to a real doctor.

**Why this is coherent despite 12 different source folders:** MedlinePlus itself is a single, real, unified service that aggregates content from exactly these 12 NIH-affiliated sources (cancer.gov, Genetics Home Reference, NIDDK, NINDS, CDC, etc.) into one consumer portal. This isn't a random mashup — it's the same aggregation MedlinePlus performs in real life, under one real mission (NIH public health education).

## Data sources (all real NIH-affiliated content)
| Item | Count | What it is |
|---|---|---|
| `MedQuAD-master/` | **11,274 real XML documents** across 12 source folders | Real medical Q&A pulled from CancerGov, GARD, GHR, MPlus Health Topics, NIDDK, NINDS, SeniorHealth, NHLBI, CDC, MPlus Drugs, MPlus Herbs, MPlus ADAM. **Not in git** — download below. |
| `NIDDK_Diabetes_in_America_Factsheet.pdf` | 2 pages | Real NIH/NIDDK fact sheet — same source as one of the 12 MedQuAD folders |
| `CDC_Diabetes_Statistics.tsv` | — | Real CDC Healthy People objective-tracking data (access to health services, baseline/final values) |

### Download MedQuAD (required for this group)

The XML dump is too large to ship in this repo (~11k files). From this folder:

```bash
chmod +x download_medquad.sh
./download_medquad.sh
```

That clones [abachaa/MedQuAD](https://github.com/abachaa/MedQuAD) into `MedQuAD-master/`.

## Required system prompt (hard requirement)
This bot MUST refuse diagnostic questions ("do I have X") and redirect to a real healthcare provider. Ties into the M04 escalation-trigger pattern — this is not optional for this group.

## Sample questions to validate retrieval
- "What are common treatments for type 2 diabetes?" (informational — should answer)
- "Do I have diabetes based on these symptoms?" (diagnostic — should refuse and redirect)
- "What does NIDDK say about diabetes prevalence in America?" (tests the bonus fact sheet)

## Note
11,274 documents is a lot for a class project — filter to 2-3 source folders (e.g. NIDDK + SeniorHealth + MPlus Health Topics) to keep the indexing time and KB size manageable.
