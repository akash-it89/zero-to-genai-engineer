# Step 04 — Demo user demo / DemoUser1!

Folder: `04_demo_user`

## Deploy

```bash
cd 06.progressive-deploy/04_demo_user
bash deploy.sh
```

## Verify

User `demo` exists. Outputs show password.

## See the delta vs previous folder

```bash
diff -ru ../03_cognito_client . | less
# or in Cursor: open ../03_cognito_client/cdk/stack.py and ./cdk/stack.py side-by-side
```

## What changed vs previous

ADD demo user custom resources + DemoUsername/DemoPassword outputs.

**Next:** `../05_s3_ui_bucket/`

Same CloudFormation stack name: **`LaukiSupportStack`**  
(so step N updates what step N-1 deployed — do not run two folders against different accounts in parallel on the same stack).
