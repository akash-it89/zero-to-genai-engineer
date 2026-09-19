# Step 09 — JWT lock on /api/me

Folder: `09_jwt_lock`

## Deploy

```bash
cd 06.progressive-deploy/09_jwt_lock
bash deploy.sh
```

## Verify

`curl $CloudFrontUrl/api/me` → 401 without token.

## See the delta vs previous folder

```bash
diff -ru ../08_apprunner_health . | less
# or in Cursor: open ../08_apprunner_health/cdk/stack.py and ./cdk/stack.py side-by-side
```

## What changed vs previous

ADD JWT verification in API + Cognito env on App Runner (`AUTH_DISABLED=false`).

**Next:** `../10_agentcore_chat/`

Same CloudFormation stack name: **`LaukiSupportStack`**  
(so step N updates what step N-1 deployed — do not run two folders against different accounts in parallel on the same stack).
