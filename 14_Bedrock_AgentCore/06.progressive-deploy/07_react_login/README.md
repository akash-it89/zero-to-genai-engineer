# Step 07 — React Cognito login (chat locked)

Folder: `07_react_login`

## Deploy

```bash
cd 06.progressive-deploy/07_react_login
bash deploy.sh
```

## Verify

Open `CloudFrontUrl` → login as demo / DemoUser1! (chat locked).

## See the delta vs previous folder

```bash
diff -ru ../06_cloudfront . | less
# or in Cursor: open ../06_cloudfront/cdk/stack.py and ./cdk/stack.py side-by-side
```

## What changed vs previous

ADD `web/` React app + BucketDeployment of login UI (`chatEnabled: false`).

**Next:** `../08_apprunner_health/`

Same CloudFormation stack name: **`LaukiSupportStack`**  
(so step N updates what step N-1 deployed — do not run two folders against different accounts in parallel on the same stack).
