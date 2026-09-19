# Step 06 — CloudFront + placeholder HTML

Folder: `06_cloudfront`

## Deploy

```bash
cd 06.progressive-deploy/06_cloudfront
bash deploy.sh
```

## Verify

Open `CloudFrontUrl` → placeholder HTML.

## See the delta vs previous folder

```bash
diff -ru ../05_s3_ui_bucket . | less
# or in Cursor: open ../05_s3_ui_bucket/cdk/stack.py and ./cdk/stack.py side-by-side
```

## What changed vs previous

ADD CloudFront + OAC + placeholder index.html deploy.

**Next:** `../07_react_login/`

Same CloudFormation stack name: **`LaukiSupportStack`**  
(so step N updates what step N-1 deployed — do not run two folders against different accounts in parallel on the same stack).
