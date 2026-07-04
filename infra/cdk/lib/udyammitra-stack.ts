import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as rds from "aws-cdk-lib/aws-rds";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as apprunner from "aws-cdk-lib/aws-apprunner";
import * as amplify from "aws-cdk-lib/aws-amplify";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as targets from "aws-cdk-lib/aws-events-targets";
import * as events from "aws-cdk-lib/aws-events";
import * as iam from "aws-cdk-lib/aws-iam";

export interface UdyammitraStackProps extends cdk.StackProps {
  /** GitHub repo URL for the Next.js frontend, e.g. https://github.com/inbharatai/udyammitra-ai */
  readonly frontendRepoUrl?: string;
  /** GitHub repo URL for the backend (used for App Runner source if not building from ECR). */
  readonly backendRepoUrl?: string;
  /**
   * Phase-1/phase-2 toggle to avoid the ECR↔App Runner chicken-and-egg.
   * Phase 1: set ENABLE_APP_RUNNER=false → creates ECR + Aurora + Secrets +
   *   Amplify + Lambda (no App Runner). Push the image to ECR, then:
   * Phase 2: ENABLE_APP_RUNNER=true (default) → adds App Runner, which now
   *   finds the image in ECR. Defaults to true so a single `cdk deploy` after
   *   the image exists "just works".
   */
  readonly enableAppRunner?: boolean;
}

/**
 * UdyamMitra AI — full AWS structure.
 *
 *   - VPC (public + private + isolated subnets)
 *   - Aurora Serverless v2 Postgres (private, reachable from App Runner)
 *   - Secrets Manager: OpenAI key + connector (GSP/ASP, Sahamati AA, EPFO) secrets
 *   - ECR repo for the FastAPI backend image
 *   - App Runner service (FastAPI, VPC connector → Aurora, streaming/SSE)
 *   - Amplify app (Next.js frontend, from GitHub)
 *   - Alternate-data ingestion: EventBridge schedule → SQS → Lambda connector stub
 *
 * Not deployed in this repo commit — run `cdk synth` then `cdk deploy` with
 * AWS creds. Validate with `cdk synth` before first deploy.
 */
export class UdyammitraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: UdyammitraStackProps) {
    super(scope, id, props);

    // ---------------------------------------------------------------- Network
    const vpc = new ec2.Vpc(this, "Vpc", {
      maxAzs: 2,
      // CHEAP MODE: no NAT gateway (~$32/mo saved). App Runner reaches Aurora
      // intra-VPC via the VPC connector (no internet needed); the ingestion
      // Lambda runs outside the VPC so it keeps default internet access.
      natGateways: 0,
      subnetConfiguration: [
        { name: "public", subnetType: ec2.SubnetType.PUBLIC },
        { name: "isolated", subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      ],
    });

    // --------------------------------------------------------------- Secrets
    const openaiSecret = new secretsmanager.Secret(this, "OpenAiKey", {
      description: "OpenAI API key for UdyamMitra agents",
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ OPENAI_MODEL: "gpt-4o-mini" }),
        generateStringKey: "OPENAI_API_KEY",
        excludePunctuation: true,
      },
    });

    const connectorSecret = new secretsmanager.Secret(this, "ConnectorCreds", {
      description: "Alternate-data connector credentials (GSP/ASP, Sahamati AA, EPFO)",
      // Fill real values manually in the console; do not commit.
    });

    // ------------------------------------------------------- Aurora Postgres
    const dbCluster = new rds.DatabaseCluster(this, "Aurora", {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_16_3,
      }),
      // Serverless v2 writer — scales 0.5→4 ACU, cheapest baseline (~$10–15/mo).
      writer: rds.ClusterInstance.serverlessV2("writer"),
      serverlessV2MinCapacity: 0.5,
      serverlessV2MaxCapacity: 4,
      defaultDatabaseName: "udyammitra",
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      storageEncrypted: true,
      deletionProtection: false, // set true for prod
      removalPolicy: cdk.RemovalPolicy.DESTROY, // set RETAIN for prod
    });

    // The cluster auto-creates a credentials secret; expose its ARN for the
    // app to build DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db.
    const dbSecret = dbCluster.secret!;
    new cdk.CfnOutput(this, "DbSecretArn", { value: dbSecret.secretArn });
    new cdk.CfnOutput(this, "DbClusterEndpoint", {
      value: dbCluster.clusterEndpoint.hostname,
    });

    // --------------------------------------------------------- ECR (backend)
    const repo = new ecr.Repository(this, "BackendRepo", {
      repositoryName: "udyammitra-backend",
      imageScanOnPush: true,
      lifecycleRules: [{ maxImageCount: 10 }],
    });

    // ----------------------------------------------------------- App Runner
    // L1 construct for explicit, stable control of the VPC connector + secret
    // env-var wiring. Build & push the image to ECR first (CodeBuild or
    // `docker push`), then set ImageIdentifier below to <repo>:<tag>.
    if (props.enableAppRunner !== false) {
    const vpcConnector = new apprunner.CfnVpcConnector(this, "AppRunnerVpcConn", {
      subnets: vpc.isolatedSubnets.map((s) => s.subnetId),
      securityGroups: [dbCluster.connections.securityGroups[0].securityGroupId],
    });

    // App Runner instance role: pull from ECR + read secrets. Access role for
    // ECR access is configured at the service level via accessRoleArn below.
    const accessRole = new iam.Role(this, "AppRunnerAccessRole", {
      assumedBy: new iam.ServicePrincipal("apprunner.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSAppRunnerServicePolicyForECRAccess"),
      ],
    });

    const instanceRole = new iam.Role(this, "AppRunnerInstanceRole", {
      assumedBy: new iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
      description: "UdyamMitra App Runner instance role — read secrets for env vars",
    });
    openaiSecret.grantRead(instanceRole);
    connectorSecret.grantRead(instanceRole);
    dbSecret.grantRead(instanceRole);

    // CHEAP MODE: scale-to-zero when idle (cold start ~30s). Bump minSize to 1
    // for an always-warm live demo (standard mode).
    const autoScaling = new apprunner.CfnAutoScalingConfiguration(this, "AutoScaling", {
      autoScalingConfigurationName: "udyammitra-autoscaling",
      minSize: 0,
      maxSize: 2,
    });

    const appRunnerService = new apprunner.CfnService(this, "Backend", {
      serviceName: "udyammitra-backend",
      autoScalingConfigurationArn: autoScaling.attrAutoScalingConfigurationArn,
      sourceConfiguration: {
        imageRepository: {
          imageIdentifier: `${repo.repositoryUri}:latest`,
          imageRepositoryType: "ECR",
          imageConfiguration: {
            port: "8000",
            startCommand: "sh -c \"uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}\"",
            runtimeEnvironmentVariables: [
              { name: "OPENAI_MODEL", value: "gpt-4o-mini" },
              { name: "OPENAI_DISABLED", value: "false" },
              { name: "CORS_ORIGINS", value: "https://placeholder.amplify.app" },
              // Set at deploy time to the Aurora connection string, resolved
              // from the DbSecretArn output:
              //   postgresql+psycopg2://<user>:<pass>@<DbClusterEndpoint>:5432/udyammitra
              // (or enhance app.core.config to compose it from DB_SECRET.)
              { name: "DATABASE_URL", value: "postgresql+psycopg2://SET_AT_DEPLOY" },
            ],
            runtimeEnvironmentSecrets: [
              { name: "OPENAI_API_KEY", value: openaiSecret.secretArn },
              { name: "CONNECTOR_CREDS", value: connectorSecret.secretArn },
              { name: "DB_SECRET", value: dbSecret.secretArn },
            ],
          },
        },
        authenticationConfiguration: { accessRoleArn: accessRole.roleArn },
        autoDeploymentsEnabled: false,
      },
      instanceConfiguration: {
        cpu: "1 vCPU",
        memory: "2 GB",
        instanceRoleArn: instanceRole.roleArn,
      },
      healthCheckConfiguration: {
        protocol: "HTTP",
        path: "/health",
        healthyThreshold: 2,
        unhealthyThreshold: 3,
        timeout: 5,
        interval: 10,
      },
      networkConfiguration: {
        egressConfiguration: {
          egressType: "VPC",
          vpcConnectorArn: vpcConnector.attrVpcConnectorArn,
        },
        ingressConfiguration: { isPubliclyAccessible: true },
      },
    });
    new cdk.CfnOutput(this, "AppRunnerServiceArn", { value: appRunnerService.attrServiceArn });
    } // end enableAppRunner

    // ------------------------------------------------------------ Amplify (frontend)
    if (props.frontendRepoUrl) {
      const amplifyApp = new amplify.CfnApp(this, "Frontend", {
        name: "udyammitra-ai",
        repository: props.frontendRepoUrl,
        platform: "WEB",
        // Amplify builds the Next.js app from the frontend/ root.
        buildSpec: JSON.stringify({
          version: 1,
          applications: [
            {
              appRoot: "frontend",
              frontend: {
                phases: {
                  preBuild: { commands: ["npm ci"] },
                  build: { commands: ["npm run build"] },
                },
                artifacts: { baseDirectory: ".next", files: ["**/*"] },
                cache: { paths: ["node_modules/**/*", ".next/cache/**/*"] },
              },
              environment: {
                NEXT_PUBLIC_API_BASE: "https://CHANGE_ME.apprunner.aws",
              },
            },
          ],
        }),
      });
      new amplify.CfnBranch(this, "FrontendMain", {
        appId: amplifyApp.attrAppId,
        branchName: "main",
        enableAutoBuild: true,
      });
      new cdk.CfnOutput(this, "AmplifyAppId", { value: amplifyApp.attrAppId });
    }

    // --------------------- Alternate-data ingestion (EventBridge → SQS → Lambda)
    const ingestionQueue = new sqs.Queue(this, "IngestionQueue", {
      visibilityTimeout: cdk.Duration.minutes(5),
      retentionPeriod: cdk.Duration.days(4),
    });

    // Stub handler. Bundling the app connector package into this Lambda
    // requires a Dockerfile-bundled lambda (aws-lambda.DockerImageFunction)
    // or a layer; left as a wiring step. The stub logs the MSME id + source.
    const connectorLambda = new lambda.Function(this, "ConnectorLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "index.handler",
      code: lambda.Code.fromAsset("lambdas"),
      timeout: cdk.Duration.minutes(3),
      environment: {
        QUEUE_URL: ingestionQueue.queueUrl,
        CONNECTOR_SECRET_ARN: connectorSecret.secretArn,
      },
    });
    connectorSecret.grantRead(connectorLambda);

    // Schedule a daily GST pull for every MSME (demo cadence). Real triggers
    // would be AA consent webhooks + on-demand ULI fetches.
    new events.Rule(this, "DailyGstPull", {
      schedule: events.Schedule.rate(cdk.Duration.hours(24)),
      targets: [new targets.SqsQueue(ingestionQueue)],
    });
    ingestionQueue.grantConsumeMessages(connectorLambda);
  }
}