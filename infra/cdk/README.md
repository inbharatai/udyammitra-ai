# UdyamMitra AI — AWS CDK stack

Provisions the full AWS structure for UdyamMitra AI. **Not deployed by the
app commit** — run these steps when you're ready to go to AWS.

## What it creates

| Resource | Purpose |
|---|---|
| VPC (public / private / isolated) | Network home for Aurora + App Runner |
| Aurora Serverless v2 (Postgres 16) | Replaces SQLite; `DATABASE_URL` swap |
| Secrets Manager | OpenAI key, connector creds, DB creds |
| ECR repo | Backend Docker image |
| App Runner service | FastAPI backend (streaming/SSE), VPC connector → Aurora |
| Amplify app + `main` branch | Next.js frontend from GitHub |
| SQS + Lambda + EventBridge rule | Alternate-data ingestion (GST/AA/UPI/EPFO) skeleton |

## Prerequisites

1. AWS account + `aws configure` (region `ap-south-1` recommended).
2. `npm install` in this directory (installs CDK + constructs).
3. `npx cdk bootstrap aws://<ACCOUNT>/ap-south-1` (one-time per env).
4. Build + push the backend image to ECR:
   ```bash
   aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <acct>.dkr.ecr.ap-south-1.amazonaws.com
   cd backend && docker build -t udyammitra-backend .
   docker tag udyammitra-backend:latest <acct>.dkr.ecr.ap-south-1.amazonaws.com/udyammitra-backend:latest
   docker push <acct>.dkr.ecr.ap-south-1.amazonaws.com/udyammitra-backend:latest
   ```

## Deploy

```bash
npm install
npm run build        # tsc --noEmit — typecheck the stack
npx cdk synth        # validate the generated CloudFormation
FRONTEND_REPO_URL=https://github.com/inbharatai/udyammitra-ai npx cdk deploy
```

Outputs you'll get back: `DbSecretArn`, `DbClusterEndpoint`, `AppRunnerServiceArn`,
`AmplifyAppId`. Use `DbClusterEndpoint` + `DbSecretArn` to set the backend
`DATABASE_URL`, and the App Runner public URL as the frontend's
`NEXT_PUBLIC_API_BASE` (set in the Amplify build spec or console).

## Before-first-deploy wiring checklist

- Set `CORS_ORIGINS` in the stack to the real Amplify domain (or edit in console).
- Set `DATABASE_URL` in the stack to the Aurora connection string (from `DbSecretArn`), or enhance `app.core.config` to compose it from `DB_SECRET`.
- Fill `OpenAiKey` and `ConnectorCreds` secrets in the Secrets Manager console (do not commit).
- Set `deletionProtection: true` and `removalPolicy: RETAIN` for Aurora in prod.
- For multi-instance App Runner, move `run_manager` event queues to ElastiCache Redis pub/sub (see app README).

## Cost notes (hackathon)

- Aurora Serverless v2 min 0.5 ACU ≈ $10–15/mo baseline.
- App Runner `min-provisioned=1` (warm demo) adds a small steady cost; set to 0 to scale-to-zero between demos (cold start ~20–60s).
- 1 NAT Gateway ≈ $32/mo — `natGateways: 1` is set for cost control; bump to 2 for HA.