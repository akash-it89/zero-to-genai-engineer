# Step 03 — Cognito SPA app client

Folder: `03_cognito_client`

## Deploy

```bash
cd 06.progressive-deploy/03_cognito_client
bash deploy.sh
```

## Verify

App client `lauki-support-spa` on the pool.

## See the delta vs previous folder

```bash
diff -ru ../02_cognito_pool . | less
# or in Cursor: open ../02_cognito_pool/cdk/stack.py and ./cdk/stack.py side-by-side
```

## What changed vs previous

ADD SPA app client (`SpaClient`) with USER_PASSWORD_AUTH.

**Next:** `../04_demo_user/`

Same CloudFormation stack name: **`LaukiSupportStack`**  
(so step N updates what step N-1 deployed — do not run two folders against different accounts in parallel on the same stack).
