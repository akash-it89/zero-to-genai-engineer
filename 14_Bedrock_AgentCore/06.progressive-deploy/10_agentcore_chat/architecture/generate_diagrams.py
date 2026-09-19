#!/usr/bin/env python3
"""
Regenerate Step 10 AWS architecture diagrams (same engine as diagrams-mcp).

Requires:
  brew install graphviz
  uv run --with diagrams python generate_diagrams.py
"""

from __future__ import annotations

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import AppRunner, ECR
from diagrams.aws.management import SystemsManagerParameterStore
from diagrams.aws.ml import Bedrock
from diagrams.aws.network import CloudFront
from diagrams.aws.security import Cognito, IAMRole
from diagrams.aws.storage import S3
from diagrams.onprem.client import Users

HERE = Path(__file__).resolve().parent

GRAPH = {
    "fontsize": "12",
    "bgcolor": "white",
    "pad": "0.6",
    "splines": "ortho",
    "nodesep": "0.55",
    "ranksep": "0.85",
    "fontname": "Helvetica",
}
NODE = {"fontsize": "11", "fontname": "Helvetica"}
EDGE = {"fontsize": "10", "fontname": "Helvetica"}


def render_architecture() -> Path:
    filename = str(HERE / "lauki-step10-aws-architecture")
    with Diagram(
        "Lauki Support Copilot — Step 10 AWS Architecture",
        filename=filename,
        outformat="png",
        show=False,
        direction="LR",
        graph_attr=GRAPH,
        node_attr=NODE,
        edge_attr=EDGE,
    ):
        user = Users("Browser\n(Student / Demo)")

        with Cluster("Public Edge"):
            cf = CloudFront("Amazon CloudFront\nHTTPS CDN + path routing")

        with Cluster("Static UI Origin (private)"):
            s3 = S3("S3 UI Bucket\nSPA + config.json\nBlock Public Access + OAC")

        with Cluster("Identity"):
            cognito = Cognito("Cognito User Pool\nSPA client (no secret)\ndemo user")

        with Cluster("API Compute"):
            ecr = ECR("ECR\nFastAPI image")
            api = AppRunner("AWS App Runner\nFastAPI :8000\nJWT verify + proxy")
            role = IAMRole("Instance Role\nInvokeAgentRuntime")

        with Cluster("AI Runtime (external to this CDK stack)"):
            bedrock = Bedrock(
                "Bedrock AgentCore\nStrands Support Copilot\nDEFAULT endpoint"
            )

        with Cluster("Ops"):
            ssm = SystemsManagerParameterStore("SSM\ndeploy-stage=10")

        user >> Edge(label="1 HTTPS /*", color="#232F3E") >> cf
        cf >> Edge(label="OAC SigV4\nstatic assets", color="#7AA116", style="dashed") >> s3
        user >> Edge(label="2 USER_PASSWORD_AUTH\nID token", color="#DD344C") >> cognito
        cf >> Edge(label="3 /api/*  /health\nno cache", color="#ED7100") >> api
        ecr >> Edge(label="pull image", color="#7AA116", style="dashed") >> api
        api >> Edge(label="JWKS verify", color="#DD344C", style="dashed") >> cognito
        api >> role
        role >> Edge(
            label="4 InvokeAgentRuntime\npayload + session", color="#01A88D"
        ) >> bedrock
        api >> Edge(style="dashed", color="#545B64") >> ssm

    return Path(filename + ".png")


def render_flows() -> Path:
    filename = str(HERE / "lauki-step10-request-flows")
    with Diagram(
        "Lauki Step 10 — Request Flows (Login + Chat)",
        filename=filename,
        outformat="png",
        show=False,
        direction="TB",
        graph_attr={**GRAPH, "splines": "spline", "pad": "0.5"},
        node_attr=NODE,
        edge_attr=EDGE,
    ):
        user = Users("Browser SPA")

        with Cluster("A — Login Flow"):
            cf1 = CloudFront("CloudFront\nserves SPA")
            s3 = S3("S3\nconfig.json")
            cognito = Cognito("Cognito\nID Token")

        with Cluster("B — Chat Flow (JWT locked)"):
            cf2 = CloudFront("CloudFront\n/api/*")
            api = AppRunner("App Runner\nFastAPI JWT")
            role = IAMRole("IAM\nInvoke")
            agent = Bedrock("AgentCore\nStrands")

        user >> Edge(label="GET /", color="#232F3E") >> cf1
        cf1 >> Edge(label="OAC", color="#7AA116") >> s3
        user >> Edge(label="sign-in", color="#DD344C") >> cognito
        user >> Edge(label="POST /api/chat\nBearer JWT", color="#ED7100") >> cf2
        cf2 >> api
        api >> Edge(label="JWKS", color="#DD344C", style="dashed") >> cognito
        api >> role >> Edge(label="InvokeAgentRuntime", color="#01A88D") >> agent

    return Path(filename + ".png")


if __name__ == "__main__":
    a = render_architecture()
    f = render_flows()
    print(f"Wrote {a}")
    print(f"Wrote {f}")
