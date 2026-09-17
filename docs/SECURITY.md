# Guardrails and threat boundaries

| Threat | Implemented control | Remaining limitation |
|---|---|---|
| Public API abuse | Bearer service key, 8 KiB body limit, 2,000-character question limit, global rate limit, concurrency cap | Put a gateway in front for distributed abuse, slow clients, TLS and per-user controls |
| Instruction injection | Normalisation, common-pattern blocking, untrusted evidence prompt, no tool execution | Obfuscated attacks can bypass regex; a model can select misleading evidence |
| Invented fees/citations | Output schema, retrieved-ID allowlist, exact complete source passages | Incorrect source policy or irrelevant selection can still mislead |
| Unsupported facts | Retrieval relevance threshold, model sufficiency decision, abstention | Similarity is not calibrated confidence; requires real-model evaluation |
| Customer PII | No conversation store, basic email/phone/key redaction, no raw query logs | Detection is incomplete; do not ingest customer documents |
| Poisoned documents | Reviewed manifest, SHA-256 verification, instruction/secret/contact scanning | Anyone allowed to edit the manifest can approve bad content |
| Parser abuse | Admin-only local files, allowlisted formats, symlink/path restrictions, subprocess timeout, size caps | Not a general hostile-upload sandbox; no upload endpoint is exposed |
| Index corruption | File lock, immutable generations, atomic pointer, profile checks | Embedded Qdrant is single-process; disk/volume failures require recovery |
| Provider failure | Timeout, bounded retry, safe 503, no raw SDK exception exposure | Readiness is local and does not prove Groq uptime |
| Secret leakage | SecretStr config, ignored env files, no keys in API responses | Operators must keep keys out of Git, screenshots and frontend builds |

No claim of “every possible guardrail” or complete production certification is made. Before customer launch, perform live Groq evaluation, human policy review, deployment smoke tests, access review, dependency scanning and load testing for the intended traffic. This implementation is a deliberately small production-oriented baseline.
