# Railway deployment runbook

## What will be deployed

One Python container named `obbian-rag`, independent of the existing frontend and backend. It uses Groq over HTTPS, runs embeddings on CPU, and stores the Qdrant index plus embedding-model cache on a persistent volume. Start with one replica/worker and monitor memory; a 1–2 GiB memory allocation is a starting estimate, not a measured requirement or price quotation.

## Before deploying

- Run tests and the Groq-mode evaluation, and review policy content.
- Create a GitHub repository for this directory. Do not commit `.env`, `.venv` or `storage`.
- Have a Groq API key, a random service API key, and access to the intended Railway project.

## Railway dashboard

1. Open your existing Railway project, choose **New service**, and deploy this repository. Name it `obbian-rag`. Do not replace the Node backend service.
2. Railway detects the Dockerfile. Leave its start command in place.
3. Attach a persistent volume at `/data`.
4. Set the production environment variables from README. Add `RAG_MODEL_CACHE_DIR=/data/models` so redeploys do not redownload weights.
5. Keep one replica. The Docker command already uses one worker.
6. Deploy. First startup downloads model weights and indexes the approved documents. If startup takes longer than the configured 300-second healthcheck timeout, inspect download logs before increasing that timeout.
7. Configure a domain in service networking if external testing is needed. Keep bearer authentication enabled. Later integration can use Railway private networking.
8. Check `/health/live` and `/health/ready`, then send an authenticated policy question. Verify missing/wrong keys get 401, a live vehicle request returns `requires_backend`, and an unsupported policy fact abstains.

Railway mounts volumes at runtime rather than image-build time. Index creation therefore happens at startup, not in Docker build or a pre-deploy command. The Docker image uses an unprivileged user; if an attached volume is not writable, fix its ownership for UID 10001 (or configure Railway volume permissions) rather than running the app as root permanently.

## Optional CLI

```sh
railway login
railway link
railway up --service obbian-rag
```

Choose the intended project/environment carefully. Create/configure the new service and volume first. Do not pass a secret as a CLI argument that gets saved in shell history; set it through the Railway Variables UI.

## Updates and rollback

Policy changes alter the manifest fingerprint, so startup builds a fresh index generation. The old one stays on the volume. A running process never switches index directories mid-request. Deploying a service with a volume can involve brief downtime; schedule updates accordingly. Roll back the source revision plus matching manifest to reuse the prior snapshot.

Do not delete a snapshot while a process is using it. Back up the source documents, manifest, lockfile and deployment configuration. The vector index can be rebuilt from source. Model availability and the provider key must still be valid.

## Deployment acceptance

Record the deployed URL, commit hash, index version, Groq model, evaluation report, and a smoke-test timestamp in `reports/DEPLOYMENT_STATUS.md`. A successful Docker build or a prepared config is not a deployed service.
