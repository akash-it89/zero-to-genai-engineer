#!/usr/bin/env bash
# Clone the NIH MedQuAD Q&A dump next to this script.
# Not shipped in git (11,000+ XML files). See README.md in this folder.
set -euo pipefail
cd "$(dirname "$0")"
if [ -d MedQuAD-master/.git ] || [ -d MedQuAD-master/1_CancerGov_QA ]; then
  echo "MedQuAD-master/ already exists. Remove it first to re-download."
  exit 0
fi
git clone --depth 1 https://github.com/abachaa/MedQuAD.git MedQuAD-master
echo "Done. Index 2–3 source folders only (see README.md) — do not embed all 11k docs."
