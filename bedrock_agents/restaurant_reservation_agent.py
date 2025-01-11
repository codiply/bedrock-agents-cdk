import json
import aws_cdk
from aws_cdk import Stack, Duration
from aws_cdk import (
    Aws,
    aws_iam as iam,
    aws_bedrock as bedrock,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_opensearchserverless as aoss,
    aws_lambda as _lambda,
    triggers,
    custom_resources as cr,
)
from constructs import Construct


class RestaurantReservationAgentStack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str, prefix: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        agent_foundation_model_id = "amazon.nova-micro-v1:0"
        # agent_foundation_model_id = "amazon.nova-lite-v1:0"
        # agent_foundation_model_id = "amazon.nova-pro-v1:0"

        knowledge_base_foundation_model_vector_dimension = 1536
        knowledge_base_foundation_model_id = "amazon.titan-embed-text-v1"

        # knowledge_base_foundation_model_vector_dimension = 1024
        # knowledge_base_foundation_model_id = "amazon.titan-embed-text-v2:0"

        # Create S3 bucket and upload data

        s3_bucket = s3.Bucket(
            self,
            "s3-bucket",
            bucket_name=f"{prefix}-{Aws.ACCOUNT_ID}",
            removal_policy=aws_cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        restaurant_descriptions_deployment = s3_deploy.BucketDeployment(
            self,
            "s3-deployment",
            sources=[
                s3_deploy.Source.asset(
                    "./data/restaurants/descriptions/",
                )
            ],
            destination_bucket=s3_bucket,
            prune=True,
            retain_on_delete=False,
            destination_key_prefix="restaurants/descriptions/",
        )

        # Define the IAM role for the Knowledge Base

        knowledge_base_role = iam.Role(
            self,
            "knowledge-base-role",
            role_name=f"{prefix}-knowledge-base-role",
            assumed_by=iam.PrincipalWithConditions(
                principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
                conditions={
                    "StringEquals": {"aws:SourceAccount": Aws.ACCOUNT_ID},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:knowledge-base/*"
                    },
                },
            ),
        )

        embedding_model_arn = f"arn:aws:bedrock:{Aws.REGION}::foundation-model/{knowledge_base_foundation_model_id}"

        knowledge_base_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=[embedding_model_arn],
            )
        )

        knowledge_base_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:ListBucket", "s3:GetObject"],
                resources=[
                    s3_bucket.bucket_arn,
                    s3_bucket.arn_for_objects("restaurants/*"),
                ],
            )
        )

        knowledge_base_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["aoss:APIAccessAll"],
                resources=["*"],
            )
        )

        # Create Open Search Collection for knowledge base

        # The security policies '{collection_name}-security-policy' need to have maximum 31 characters
        collection_name = prefix[:15]

        open_search_network_security_policy = aoss.CfnSecurityPolicy(
            self,
            "open-search-network-security-policy",
            # Specific naming convention
            name=f"{collection_name}-security-policy",
            type="network",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "Resource": [f"collection/{collection_name}"],
                                "ResourceType": "dashboard",
                            },
                            {
                                "Resource": [f"collection/{collection_name}"],
                                "ResourceType": "collection",
                            },
                        ],
                        "AllowFromPublic": True,
                    }
                ],
                indent=2,
            ),
        )

        open_search_encryption_security_policy = aoss.CfnSecurityPolicy(
            self,
            "open-search-encryption-security-policy",
            # Specific naming convention
            name=f"{collection_name}-security-policy",
            type="encryption",
            policy=json.dumps(
                {
                    "Rules": [
                        {
                            "Resource": [f"collection/{collection_name}"],
                            "ResourceType": "collection",
                        }
                    ],
                    "AWSOwnedKey": True,
                },
                indent=2,
            ),
        )

        open_search_collection = aoss.CfnCollection(
            self,
            "open-search-serverless-collection",
            name=collection_name,
            type="VECTORSEARCH",
        )

        open_search_collection.add_dependency(open_search_encryption_security_policy)
        open_search_collection.add_dependency(open_search_network_security_policy)

        vector_index_name = "restaurant-descriptions-vector-index"

        vector_index_metadata_field = "AMAZON_BEDROCK_METADATA"
        vector_index_text_field = "AMAZON_BEDROCK_TEXT"
        vector_index_vector_field = "VECTOR_FIELD"

        trigger_function_runtime = _lambda.Runtime.PYTHON_3_12
        create_index_trigger_function = triggers.TriggerFunction(
            self,
            "trigger-create-vector-index-lambda",
            runtime=trigger_function_runtime,
            code=_lambda.Code.from_asset(
                "./assets/create_aoss_index_lambda/",
                bundling=aws_cdk.BundlingOptions(
                    # NOTE: for this to work an extra step of logging into public ECR is required
                    image=trigger_function_runtime.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install --no-cache -r requirements.txt -t /asset-output && cp -au . /asset-output",
                    ],
                ),
            ),
            handler="handler.main",
            timeout=Duration.seconds(180),
            environment={
                "COLLECTION_ENDPOINT": open_search_collection.attr_collection_endpoint,
                "VECTOR_INDEX_NAME": vector_index_name,
                "METADATA_FIELD": vector_index_metadata_field,
                "TEXT_FIELD": vector_index_text_field,
                "VECTOR_FIELD": vector_index_vector_field,
                "VECTOR_DIMENSION": str(
                    knowledge_base_foundation_model_vector_dimension
                ),
            },
            execute_after=[open_search_collection],
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "aoss:APIAccessAll",
                    ],
                    resources=[open_search_collection.attr_arn],
                )
            ],
        )

        open_search_access_policy = aoss.CfnAccessPolicy(
            self,
            "open-search-access-policy",
            # Specific naming convention
            name=f"{collection_name}-policy",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "Resource": [f"collection/{collection_name}"],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:DeleteCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                    "aoss:DescribeCollectionItems",
                                ],
                                "ResourceType": "collection",
                            },
                            {
                                "Resource": [f"index/{collection_name}/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DeleteIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument",
                                ],
                                "ResourceType": "index",
                            },
                        ],
                        "Principal": [
                            knowledge_base_role.role_arn,
                            create_index_trigger_function.role.role_arn,
                            f"arn:aws:iam::{Aws.ACCOUNT_ID}:user/panos",
                        ],
                        "Description": "data-access-rule",
                    }
                ],
                indent=2,
            ),
        )
        create_index_trigger_function.execute_after(open_search_access_policy)

        # Define the knowledge base
        restaurant_descriptions_knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "knowledge-base-restaurant-descriptions",
            name=f"{prefix}-descriptions-knowledge-base",
            role_arn=knowledge_base_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=embedding_model_arn,
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=open_search_collection.attr_arn,
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        metadata_field=vector_index_metadata_field,
                        text_field=vector_index_text_field,
                        vector_field=vector_index_vector_field,
                    ),
                    vector_index_name=vector_index_name,
                ),
            ),
        )
        restaurant_descriptions_knowledge_base.add_dependency(open_search_collection)
        create_index_trigger_function.execute_before(
            restaurant_descriptions_knowledge_base
        )

        restaurant_descriptions_data_source = bedrock.CfnDataSource(
            self,
            "knowledge-base-data-source-restaurant-descriptions",
            name=f"{prefix}-data-source",
            knowledge_base_id=restaurant_descriptions_knowledge_base.attr_knowledge_base_id,
            # We will delete the collection anyway.
            # If we do not RETAIN the cloudformation cannot be deleted smoothly.
            data_deletion_policy="RETAIN",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=s3_bucket.bucket_arn,
                    inclusion_prefixes=["restaurants/descriptions/"],
                ),
                type="S3",
            ),
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="FIXED_SIZE",
                    fixed_size_chunking_configuration=bedrock.CfnDataSource.FixedSizeChunkingConfigurationProperty(
                        max_tokens=300, overlap_percentage=20
                    ),
                )
            ),
        )
        restaurant_descriptions_data_source.add_dependency(
            restaurant_descriptions_knowledge_base
        )
        restaurant_descriptions_data_source.node.add_dependency(
            restaurant_descriptions_deployment
        )

        # Sync the Data Source
        sync_data_source = cr.AwsCustomResource(
            self,
            "sync-data-source",
            on_create=cr.AwsSdkCall(
                service="bedrock-agent",
                action="startIngestionJob",
                parameters={
                    "dataSourceId": restaurant_descriptions_data_source.attr_data_source_id,
                    "knowledgeBaseId": restaurant_descriptions_knowledge_base.attr_knowledge_base_id,
                },
                physical_resource_id=cr.PhysicalResourceId.of("Parameter.ARN"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            ),
        )

        sync_data_source.grant_principal.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:StartIngestionJob", "iam:CreateServiceLinkedRole", "iam:PassRole"],
                resources=["*"],
            )
        )

        # Define the IAM role for the Agent
        agent_role = iam.Role(
            self,
            "agent-role",
            role_name=f"{prefix}-agent-role",
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
                    f"arn:aws:bedrock:{Aws.REGION}::foundation-model/{agent_foundation_model_id}"
                ],
            )
        )
        agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:Retrieve"],
                resources=[
                    restaurant_descriptions_knowledge_base.attr_knowledge_base_arn
                ],
            )
        )

        # Define the Agent

        bedrock.CfnAgent(
            self,
            "ai-agent",
            agent_name=f"{prefix}-agent",
            foundation_model=agent_foundation_model_id,
            idle_session_ttl_in_seconds=600,
            instruction=(
                "You are an agent that helps me to find the right restaurant and then make a reservation. "
                "You are polite, patient and accurate. Your answers are short and to the point."
            ),
            agent_resource_role_arn=agent_role.role_arn,
            auto_prepare=True,
            knowledge_bases=[
                bedrock.CfnAgent.AgentKnowledgeBaseProperty(
                    description=(
                        "Restaurant descriptions with district, cuisine, dishes and signature dish."
                        "Includes average price and customer scores."
                        "1 star is the lowest score and 5 stars is the highest."
                        ),
                    knowledge_base_id=restaurant_descriptions_knowledge_base.attr_knowledge_base_id,
                    knowledge_base_state="ENABLED",
                )
            ],
        )
