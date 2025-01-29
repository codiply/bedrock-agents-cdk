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
    aws_dynamodb as dynamodb,
    triggers,
    custom_resources as cr,
)
from constructs import Construct


RESTAURANT_METADATA_COLUMNS = [
    "district_name"
    "restaurant_name"
    "restaurant_cuisine"
    "signature_dish"
    "dishes"
    "average_price_per_person"
    "rating_food_stars"
    "rating_service_stars",
    "capacity_persons",
]


QUOTED_RESTAURANT_METADATA_COLUMNS = list(
    map(lambda x: f"'{x}'", RESTAURANT_METADATA_COLUMNS)
)


class RestaurantReservationAgentV2Stack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str, prefix: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # agent_foundation_model_id = "amazon.nova-micro-v1:0"
        # agent_foundation_model_id = "amazon.nova-lite-v1:0"
        agent_foundation_model_id = "amazon.nova-pro-v1:0"

        # knowledge_base_foundation_model_vector_dimension = 1536
        # knowledge_base_foundation_model_id = "amazon.titan-embed-text-v1"

        knowledge_base_foundation_model_vector_dimension = 1024
        knowledge_base_foundation_model_id = "amazon.titan-embed-text-v2:0"

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
                    "./data/restaurants-v2/",
                )
            ],
            destination_bucket=s3_bucket,
            prune=True,
            retain_on_delete=False,
            destination_key_prefix="restaurants-v2/",
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
                    s3_bucket.arn_for_objects("restaurants-v2/*"),
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
                    inclusion_prefixes=["restaurants-v2/descriptions/"],
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
                actions=[
                    "bedrock:StartIngestionJob",
                    "iam:CreateServiceLinkedRole",
                    "iam:PassRole",
                ],
                resources=["*"],
            )
        )

        # Create DynamoDB table for reservations

        reservations_table = dynamodb.TableV2(
            self,
            f"{prefix}-reservations",
            partition_key=dynamodb.Attribute(
                name="restaurant_name", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="main_guest_name", type=dynamodb.AttributeType.STRING
            ),
            removal_policy=aws_cdk.RemovalPolicy.DESTROY,
        )

        # Create DynamoDB table to store SQL queries performed by agent

        sql_queries_table = dynamodb.TableV2(
            self,
            f"{prefix}-sql-queries",
            partition_key=dynamodb.Attribute(
                name="timestamp_utc", type=dynamodb.AttributeType.STRING
            ),
            removal_policy=aws_cdk.RemovalPolicy.DESTROY,
        )

        # Define the IAM role for the reservations lambda function

        reservations_lambda_role = iam.Role(
            self,
            "reservations-lambda-role",
            role_name=f"{prefix}-reservations-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        reservations_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:BatchGetItem",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:ConditionCheckItem",
                    "dynamodb:PutItem",
                    "dynamodb:DescribeTable",
                    "dynamodb:DeleteItem",
                    "dynamodb:GetItem",
                    "dynamodb:Scan",
                    "dynamodb:Query",
                    "dynamodb:UpdateItem",
                ],
                resources=[reservations_table.table_arn],
            )
        )

        # Define the reservations lambda function

        reservations_lambda = _lambda.Function(
            self,
            "reservations-lambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.main",
            code=_lambda.Code.from_asset("./assets/v2/reservations_lambda/"),
            role=reservations_lambda_role,
            description="Lambda function for Bedrock Agent Actions related to reservations",
            environment={"DYNAMODB_TABLE_NAME": reservations_table.table_name},
        )

        # Define the IAM role for the availability lambda function

        availability_lambda_role = iam.Role(
            self,
            "availability-lambda-role",
            role_name=f"{prefix}-availability-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        availability_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:BatchGetItem",
                    "dynamodb:DescribeTable",
                    "dynamodb:GetItem",
                    "dynamodb:Scan",
                    "dynamodb:Query",
                ],
                resources=[reservations_table.table_arn],
            )
        )

        availability_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=[
                    s3_bucket.arn_for_objects("restaurants-v2/*"),
                ],
            )
        )

        # Define the reservations lambda function

        availability_lambda = _lambda.Function(
            self,
            "availability-lambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.main",
            code=_lambda.Code.from_asset("./assets/v2/availability_lambda/"),
            role=availability_lambda_role,
            description="Lambda function for Bedrock Agent Actions related to availability",
            environment={
                "RESERVATIONS_DYNAMODB_TABLE_NAME": reservations_table.table_name,
                "METADATA_S3_BUCKET": s3_bucket.bucket_name,
                "METADATA_S3_KEY": "restaurants-v2/restaurant-metadata.json",
            },
        )

        # # Define the IAM role for the metadata lambda function

        metadata_query_lambda_role = iam.Role(
            self,
            "metadata-query-lambda-role",
            role_name=f"{prefix}-metadata-query-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        metadata_query_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=[
                    s3_bucket.arn_for_objects("restaurants-v2/*"),
                ],
            )
        )

        metadata_query_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:BatchGetItem",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:ConditionCheckItem",
                    "dynamodb:PutItem",
                    "dynamodb:DescribeTable",
                    "dynamodb:DeleteItem",
                    "dynamodb:GetItem",
                    "dynamodb:Scan",
                    "dynamodb:Query",
                    "dynamodb:UpdateItem",
                ],
                resources=[sql_queries_table.table_arn],
            )
        )

        # Define the lambda function for retrieving metadata

        metadata_query_lambda = _lambda.Function(
            self,
            "metadata-lambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.main",
            code=_lambda.Code.from_asset(
                "./assets/v2/metadata_query_lambda/",
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
            role=metadata_query_lambda_role,
            description="Lambda function for retrieving restaurant metadata with SQL query",
            environment={
                "METADATA_S3_BUCKET": s3_bucket.bucket_name,
                "METADATA_S3_KEY": "restaurants-v2/restaurant-metadata.json",
                "DYNAMODB_TABLE_NAME": sql_queries_table.table_name,
            },
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

        # Define the action groups
        check_availability_action_group = bedrock.CfnAgent.AgentActionGroupProperty(
            action_group_name="CheckRestaurantAvailability",
            description=(
                "Check restaurant availability before making reservation. "
                "The available capacity should be greater or equal to the number of persons to reserve."
            ),
            action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                lambda_=availability_lambda.function_arn
            ),
            function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                functions=[
                    bedrock.CfnAgent.FunctionProperty(
                        name="check_restaurant_availability",
                        parameters={
                            "restaurant_name": bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="the name of the restaurant to check availability for",
                                required=True,
                            ),
                        },
                    )
                ]
            ),
            skip_resource_in_use_check_on_delete=True,
        )

        find_restaurants_action_group = bedrock.CfnAgent.AgentActionGroupProperty(
            action_group_name="FindRestaurants",
            description=(
                "Find restaurants based on a SQL query. The table to query must always be 'restaurants'. "
                "Example: 'SELECT * FROM restaurants'. "
                "Give preference to this action over searching in any knowledge base."
            ),
            action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                lambda_=metadata_query_lambda.function_arn
            ),
            function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                functions=[
                    bedrock.CfnAgent.FunctionProperty(
                        name="find_restaurants",
                        parameters={
                            "sql_query": bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description=(
                                    f"A query in SQL for a relational table with columns {','.join(QUOTED_RESTAURANT_METADATA_COLUMNS)}. "
                                    "The column 'dishes' is a string containing all dishes separated by a comma (',')."
                                ),
                                required=True,
                            ),
                        },
                    )
                ]
            ),
            skip_resource_in_use_check_on_delete=True,
        )

        make_reservation_action_group = bedrock.CfnAgent.AgentActionGroupProperty(
            action_group_name="MakeRestaurantReservation",
            description=(
                "Make a restaurant reservation. "
                "Always check beforehand if there is availability for all persons."
            ),
            action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                lambda_=reservations_lambda.function_arn
            ),
            function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                functions=[
                    bedrock.CfnAgent.FunctionProperty(
                        name="make_restaurant_reservation",
                        parameters={
                            "restaurant_name": bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="the name of the restaurant to be reserved",
                                required=True,
                            ),
                            "main_guest_name": bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="the name of the person making the reservation",
                                required=True,
                            ),
                            "number_of_persons": bedrock.CfnAgent.ParameterDetailProperty(
                                type="integer",
                                description="number of persons for the reservation. must be positive number.",
                                required=True,
                            ),
                        },
                    )
                ]
            ),
            skip_resource_in_use_check_on_delete=True,
        )

        # Define guardrails

        guardrail = bedrock.CfnGuardrail(
            self,
            "guardrails",
            name=f"{prefix}-guardrails",
            description="Guardrails for restaurant reservation agent",
            blocked_input_messaging="Input blocked by guardrail",
            blocked_outputs_messaging="Outputs blocked by guardrail",
            sensitive_information_policy_config=bedrock.CfnGuardrail.SensitiveInformationPolicyConfigProperty(
                pii_entities_config=[
                    bedrock.CfnGuardrail.PiiEntityConfigProperty(
                        type="EMAIL", action="ANONYMIZE"
                    ),
                    bedrock.CfnGuardrail.PiiEntityConfigProperty(
                        type="IP_ADDRESS", action="ANONYMIZE"
                    ),
                ]
            ),
            word_policy_config=bedrock.CfnGuardrail.WordPolicyConfigProperty(
                words_config=[
                    bedrock.CfnGuardrail.WordConfigProperty(
                        # Let's ban risotto
                        text="risotto"
                    )
                ]
            ),
        )

        guardrail_version = bedrock.CfnGuardrailVersion(
            self,
            "guardrail-version",
            guardrail_identifier=guardrail.attr_guardrail_id,
            description="Published version of the guardrail",
        )

        agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:ApplyGuardrail"],
                resources=[guardrail.attr_guardrail_arn],
            )
        )

        # Define the Agent

        agent = bedrock.CfnAgent(
            self,
            "ai-agent",
            agent_name=f"{prefix}-agent",
            foundation_model=agent_foundation_model_id,
            idle_session_ttl_in_seconds=600,
            instruction=(
                "You are an agent that helps me to find the right restaurant and then make a reservation. "
                "You check the availability of a restaurant before making a reservation."
            ),
            agent_resource_role_arn=agent_role.role_arn,
            auto_prepare=True,
            knowledge_bases=[
                bedrock.CfnAgent.AgentKnowledgeBaseProperty(
                    description=(
                        "Restaurant descriptions in free text with user reviews. "
                        "Only use this for accessing user reviews."
                    ),
                    knowledge_base_id=restaurant_descriptions_knowledge_base.attr_knowledge_base_id,
                    knowledge_base_state="ENABLED",
                )
            ],
            action_groups=[
                check_availability_action_group,
                find_restaurants_action_group,
                make_reservation_action_group,
            ],
            guardrail_configuration=bedrock.CfnAgent.GuardrailConfigurationProperty(
                guardrail_identifier=guardrail.attr_guardrail_id,
                guardrail_version=guardrail_version.attr_version,
            ),
        )

        for lambda_function in [
            availability_lambda,
            reservations_lambda,
            metadata_query_lambda,
        ]:
            lambda_function.add_permission(
                "allow-invoke-bedrock-agent",
                principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
                action="lambda:InvokeFunction",
                source_arn=agent.attr_agent_arn,
            )
