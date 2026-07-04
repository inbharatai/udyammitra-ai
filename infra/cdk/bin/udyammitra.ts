#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { UdyammitraStack } from "../lib/udyammitra-stack";

const app = new cdk.App();

// Default region: ap-south-1 (Mumbai) — lowest latency for an Indian MSME
// jury + AWS Mumbai is the natural home. Override with --require-approval or
// env vars as needed.
new UdyammitraStack(app, "UdyammitraStack", {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || "ap-south-1",
  },
  // Set in CI/CD or override per environment.
  frontendRepoUrl: process.env.FRONTEND_REPO_URL || "",
  backendRepoUrl: process.env.BACKEND_REPO_URL || "",
  // Phase-1/phase-2 toggle (see UdyammitraStackProps.enableAppRunner).
  // Phase 1: ENABLE_APP_RUNNER=false → ECR+Aurora+Secrets+Amplify+Lambda only.
  // Phase 2: default (true) → adds App Runner once the image exists in ECR.
  enableAppRunner: process.env.ENABLE_APP_RUNNER !== "false",
});

app.synth();