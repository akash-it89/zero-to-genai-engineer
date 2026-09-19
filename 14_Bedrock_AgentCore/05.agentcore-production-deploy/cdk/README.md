# CDK — Lauki Support (staged deploys)

Parent lab: [`../README.md`](../README.md)  
Stage-by-stage guide: [`../CLASSROOM_10_CDK_DEPLOYS.md`](../CLASSROOM_10_CDK_DEPLOYS.md)  
Folder snapshots (often easier): [`../../06.progressive-deploy/`](../../06.progressive-deploy/)

Grow the same stack with **10 deploys**:

```bash
bash cdk/deploy.sh 1   # empty marker (SSM)
bash cdk/deploy.sh 2   # Cognito pool
# ...
bash cdk/deploy.sh 9   # JWT lock
SUPPORT_RUNTIME_ARN=arn:... bash cdk/deploy.sh 10   # AgentCore chat
```

Or jump straight to the full stack (same as stage 10):

```bash
export SUPPORT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT:runtime/strands_support_copilot-XXXX
bash cdk/deploy.sh 10
```

Open **`CloudFrontUrl`**. Login: **`demo` / `DemoUser1!`** (created from stage 4).

## Stage map

| Stage | What appears |
|------:|--------------|
| 1 | SSM stage marker |
| 2 | Cognito User Pool |
| 3 | SPA app client |
| 4 | Demo user |
| 5 | Private S3 UI bucket |
| 6 | CloudFront + placeholder HTML |
| 7 | React login UI (`chatEnabled: false`) |
| 8 | App Runner `/health` (+ CF `/health`, `/api/*`) |
| 9 | Cognito JWT on API |
| 10 | `SUPPORT_RUNTIME_ARN` + chat UI |

## Outputs

| Output | From stage |
|---|---|
| `DeployStage` / `StageHint` | 1+ |
| `UserPoolId` | 2+ |
| `UserPoolClientId` | 3+ |
| `DemoUsername` / `DemoPassword` | 4+ |
| `UiBucketName` | 5+ |
| `CloudFrontUrl` | 6+ |
| `AppRunnerUrl` | 8+ |
| `SupportRuntimeArn` | 10 |

## Destroy

```bash
cd cdk && source .venv/bin/activate
npx cdk destroy -c stage=10 -c supportRuntimeArn="$SUPPORT_RUNTIME_ARN" --force
```

Does **not** delete AgentCore Runtime / Memory / Gateway / Guardrail from lab 02.
