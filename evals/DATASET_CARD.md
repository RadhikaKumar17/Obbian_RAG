# Golden dataset v1

60 manually specified synthetic cases: 36 answerable, 6 injection, 6 live-action, 3 out-of-scope and 9 unanswerable questions. Ground truth is the supplied demo-policy snapshot, not invented rental terms. No customer data is used.

`dev` is for debugging thresholds and prompts. `test` is a regression holdout; do not tune on its failures. These splits share policy documents, so this measures paraphrase generalization, not unseen-document generalization. Expand with separately reviewed customer questions before calling this a production benchmark.

Each row has a stable ID, split, category, question, expected status, expected document IDs, and required factual phrases. Phrase matching is deliberately suitable for citation-first exact text. It is not a semantic correctness judge. Citation grounding checks source correspondence; human reviewers must assess relevance, missing qualifications and completeness.

Review all cases with a policy owner before release. Keep changes version-controlled; do not silently change answers to improve scores. No paid-model result is claimed until a live evaluation report exists.
