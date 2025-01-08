#!/usr/bin/env python3
import os

import aws_cdk as cdk

from bedrock_agents.agents_stack import AgentsStack

app = cdk.App()

AgentsStack(
    app,
    "bedrock-agents-cdk-agents-stack",
    env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region="us-east-1"),
)

app.synth()
