<div align="center">

# Student group datasets — Session 10

**9 real-company RAG briefs · one folder per group**

</div>

Each folder has source documents, a `REQUIREMENT.md`, and a short `README.md`.

**Read this first:** [`REQUIREMENTS_OVERVIEW.md`](REQUIREMENTS_OVERVIEW.md) (deliverables, ablation tables, grading).  
**How you will be scored on numbers:** [`EVALUATION_METHODOLOGY.md`](EVALUATION_METHODOLOGY.md).

**Browser (same ideas as the briefs):** [Tiny RAG](https://nursnaaz.github.io/tutorial/tiny-rag) · [Citations and refusals](https://nursnaaz.github.io/tutorial/citations-and-refusals) · [Prompt injection in RAG](https://nursnaaz.github.io/tutorial/rag-injection-guardrails)

| # | Folder | Bot you build |
|---|---|---|
| 1 | [`01_banking/`](01_banking/) | Wells Fargo customer support |
| 2 | [`02_ecommerce/`](02_ecommerce/) | Amazon seller support |
| 3 | [`03_telecom/`](03_telecom/) | Verizon customer support |
| 4 | [`04_legal/`](04_legal/) | Law-firm contract search |
| 5 | [`05_healthcare/`](05_healthcare/) | NIH/MedlinePlus-style health info (**must refuse diagnosis**) |
| 6 | [`06_finance_complaints/`](06_finance_complaints/) | Consumer credit-rights helpline |
| 7 | [`07_airline_travel/`](07_airline_travel/) | Delta passenger support |
| 8 | [`08_tax_government/`](08_tax_government/) | IRS taxpayer assistance |
| 9 | [`09_insurance/`](09_insurance/) | State Farm customer support |

`_excluded_out_of_scope/` holds competitor / wrong-persona documents. Use them as **must-refuse** tests — they are not in-scope knowledge.

### Healthcare extra download

Group 5's MedQuAD XML dump is **not in git** (11,000+ files). Clone it with [`05_healthcare/download_medquad.sh`](05_healthcare/download_medquad.sh) — see that folder's README.
