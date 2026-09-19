# Step 01 — Empty CDK stack (SSM marker)

Folder: `01_empty_cdk`

## Deploy

```bash
cd 06.progressive-deploy/01_empty_cdk
bash deploy.sh
```

## Verify

CloudFormation stack exists; output `DeployStep=1`.

## What changed vs previous

START — first deployable CDK app (SSM parameter only).

**Next:** `../02_cognito_pool/`

Same CloudFormation stack name: **`LaukiSupportStack`**  
(so step N updates what step N-1 deployed — do not run two folders against different accounts in parallel on the same stack).
