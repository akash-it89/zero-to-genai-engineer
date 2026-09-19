# Step 05 — Private S3 bucket for UI

Folder: `05_s3_ui_bucket`

## Deploy

```bash
cd 06.progressive-deploy/05_s3_ui_bucket
bash deploy.sh
```

## Verify

S3 bucket name in outputs.

## See the delta vs previous folder

```bash
diff -ru ../04_demo_user . | less
# or in Cursor: open ../04_demo_user/cdk/stack.py and ./cdk/stack.py side-by-side
```

## What changed vs previous

ADD private S3 `UiBucket`.

**Next:** `../06_cloudfront/`

Same CloudFormation stack name: **`LaukiSupportStack`**  
(so step N updates what step N-1 deployed — do not run two folders against different accounts in parallel on the same stack).
