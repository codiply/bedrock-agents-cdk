import os
import boto3
import json
from datetime import datetime, timezone

import pandas as pd
from pandasql import sqldf
from pandasql.sqldf import PandaSQLException

METADATA_S3_BUCKET = os.environ["METADATA_S3_BUCKET"]
METADATA_S3_KEY = os.environ["METADATA_S3_KEY"]
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]

# Limit the results to 50, because otherwise the lambda cannot handle the response
MAX_RESULTS = 50


s3_resource = boto3.resource("s3")
dynamodb_client = boto3.client("dynamodb")


def _load_metadata_json():
    metadata_object = s3_resource.Object(METADATA_S3_BUCKET, METADATA_S3_KEY)
    metadata_content = metadata_object.get()["Body"].read().decode("utf-8")
    metadata_json = json.loads(metadata_content)
    df = pd.DataFrame(metadata_json)
    df["dishes"] = df["dishes"].apply(lambda dishes: ", ".join(dishes))

    return df


restaurants = _load_metadata_json()


def _get_parameter(event, param_name):
    return next(p for p in event["parameters"] if p["name"] == param_name)["value"]


def main(event, context):

    print(json.dumps(event, indent=4))

    sql_query = _get_parameter(event, "sql_query")

    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Store the query in a DynamoDB table for debugging
    dynamodb_client.put_item(
        TableName=DYNAMODB_TABLE_NAME,
        Item={
            "timestamp_utc": {"S": timestamp_utc},
            "sql_query": {"S": sql_query},
        },
    )

    try:
        df = sqldf(sql_query)[:MAX_RESULTS]
        response = df.to_json(orient="records", index=False)
    except PandaSQLException as e:
        # Give the exception back to the model to see if it can fix the query
        response = (
            f"The query failed, if you think that you can fix your query try again."
            f'The error was: "{str(e)}"'
        )

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event["actionGroup"],
            "function": event["function"],
            "functionResponse": {"responseBody": {"TEXT": {"body": response}}},
        },
        "sessionAttributes": event["sessionAttributes"],
        "promptSessionAttributes": event["promptSessionAttributes"],
    }
