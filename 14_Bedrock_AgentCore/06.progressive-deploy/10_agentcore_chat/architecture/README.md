# Architecture diagrams — Step 10

AWS architecture artifacts for the full demo in `10_agentcore_chat`.

## Files

| File | What |
|---|---|
| [`lauki-step10-aws-architecture.drawio`](./lauki-step10-aws-architecture.drawio) | **Editable draw.io** — open in [diagrams.net](https://app.diagrams.net) or a Draw.io editor. Two pages: *AWS Architecture* + *Request Sequence*. |
| [`lauki-step10-aws-architecture.png`](./lauki-step10-aws-architecture.png) | AWS icon diagram (CloudFront, Cognito, App Runner, AgentCore) |
| [`lauki-step10-request-flows.png`](./lauki-step10-request-flows.png) | Login + chat request flows |
| [`generate_diagrams.py`](./generate_diagrams.py) | Script to regenerate the PNGs |

## Open the draw.io file

```bash
# Option A: diagrams.net in the browser (File → Open from → Device)
open lauki-step10-aws-architecture.drawio

# Option B: VS Code / Cursor Draw.io extension — open the .drawio file in the editor
```

## Regenerate PNGs

```bash
brew install graphviz   # once (macOS)
cd architecture
uv run --with diagrams python generate_diagrams.py
```

Requires [Graphviz](https://graphviz.org/) and the Python [`diagrams`](https://diagrams.mingrammer.com/) library.
