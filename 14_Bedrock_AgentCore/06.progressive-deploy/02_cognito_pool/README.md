# Step 02 — Cognito User Pool

Folder: `02_cognito_pool`

## Deploy

```bash
cd 06.progressive-deploy/02_cognito_pool
bash deploy.sh
```

## Verify

Cognito console → `lauki-support-users`.

## See the delta vs previous folder

```bash
diff -ru ../01_empty_cdk . | less
# or in Cursor: open ../01_empty_cdk/cdk/stack.py and ./cdk/stack.py side-by-side
```

## What changed vs previous

ADD Cognito User Pool (`UserPool`).

**Next:** `../03_cognito_client/`

Same CloudFormation stack name: **`LaukiSupportStack`**  
(so step N updates what step N-1 deployed — do not run two folders against different accounts in parallel on the same stack).
