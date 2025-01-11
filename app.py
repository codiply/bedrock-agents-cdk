#!/usr/bin/env python3
import os

import aws_cdk as cdk

from bedrock_agents.restaurant_reservation_agent import RestaurantReservationAgentStack


PREFIX = "bedrock-agents-cdk"


app = cdk.App()

RestaurantReservationAgentStack(
    app,
    f"{PREFIX}-restaurant-reservations-agent",
    prefix="restaurant-reservations",
    env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region="us-east-1"),
)

app.synth()
