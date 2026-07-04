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
});

app.synth();