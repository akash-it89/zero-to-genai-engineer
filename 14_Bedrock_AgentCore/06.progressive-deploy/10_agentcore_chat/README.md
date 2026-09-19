# Step 10 — AgentCore /api/chat — full demo

Folder: `10_agentcore_chat`

## Deploy

```bash
cd 06.progressive-deploy/10_agentcore_chat
export SUPPORT_RUNTIME_ARN='arn:aws:bedrock-agentcore:...'
bash deploy.sh
```

## Verify

Login → ask about SIM activation → full answer.

## See the delta vs previous folder

```bash
diff -ru ../09_jwt_lock . | less
# or in Cursor: open ../09_jwt_lock/cdk/stack.py and ./cdk/stack.py side-by-side
```

## What changed vs previous

ADD AgentCore invoke IAM + SUPPORT_RUNTIME_ARN + `chatEnabled: true`.

**Done — full stack.**

Same CloudFormation stack name: **`LaukiSupportStack`**  
(so step N updates what step N-1 deployed — do not run two folders against different accounts in parallel on the same stack).
