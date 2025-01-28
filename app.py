#!/usr/bin/env python3
import os

import aws_cdk as cdk

from bedrock_agents.restaurant_reservation_agent import RestaurantReservationAgentStack
from bedrock_agents.restaurant_reservation_agent_v2 import (
    RestaurantReservationAgentV2Stack,
)


PREFIX = "bedrock-agents-cdk"


app = cdk.App()

RestaurantReservationAgentStack(
    app,
    f"{PREFIX}-restaurant-reservations-agent",
    prefix="restaurant-reservations",
    env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region="us-east-1"),
)

RestaurantReservationAgentV2Stack(
    app,
    f"{PREFIX}-restaurant-reservations-agent-v2",
    prefix="v2-restaurant-reservations",
    env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region="us-east-1"),
)

app.synth()
