# Step 08 — App Runner FastAPI /health

Folder: `08_apprunner_health`

## Deploy

```bash
cd 06.progressive-deploy/08_apprunner_health
bash deploy.sh
```

## Verify

`curl $CloudFrontUrl/health` → ok.

## See the delta vs previous folder

```bash
diff -ru ../07_react_login . | less
# or in Cursor: open ../07_react_login/cdk/stack.py and ./cdk/stack.py side-by-side
```

## What changed vs previous

ADD `api/` FastAPI health + App Runner + CF `/health` and `/api/*` behaviors.

**Next:** `../09_jwt_lock/`

Same CloudFormation stack name: **`LaukiSupportStack`**  
(so step N updates what step N-1 deployed — do not run two folders against different accounts in parallel on the same stack).
