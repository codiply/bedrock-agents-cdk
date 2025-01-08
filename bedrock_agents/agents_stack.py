from aws_cdk import Stack
from aws_cdk import Aws, aws_iam as iam, aws_bedrock as bedrock
from constructs import Construct


class AgentsStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        foundation_model_id = "amazon.titan-text-lite-v1"

        # Define the IAM role for the Agent

        agent_role = iam.Role(
            self,
            "agent-role",
            assumed_by=iam.PrincipalWithConditions(
                principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
                conditions={
                    "StringEquals": {"aws:SourceAccount": Aws.ACCOUNT_ID},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:agent/*"
                    },
                },
            ),
        )

        agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{Aws.REGION}::foundation-model/{foundation_model_id}"
                ],
            )
        )

        # Define the Agent

        bedrock.CfnAgent(
            self,
            "ai-agent",
            agent_name="my-first-ai-agent",
            foundation_model=foundation_model_id,
            idle_session_ttl_in_seconds=600,
            instruction=(
                "You are an AI agent created with AWS CDK. You cannot perform any actions yet."
            ),
            agent_resource_role_arn=agent_role.role_arn,
        )
