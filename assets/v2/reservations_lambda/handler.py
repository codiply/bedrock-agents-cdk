import os
import boto3
import json
from datetime import datetime, timezone

DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]

dynamodb_client = boto3.client("dynamodb")


def _get_parameter(event, param_name):
    return next(p for p in event["parameters"] if p["name"] == param_name)["value"]


def main(event, context):

    print(json.dumps(event, indent=4))

    restaurant_name = _get_parameter(event, "restaurant_name")
    main_guest_name = _get_parameter(event, "main_guest_name")
    number_of_persons = _get_parameter(event, "number_of_persons")

    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    dynamodb_client.put_item(
        TableName=DYNAMODB_TABLE_NAME,
        Item={
            "restaurant_name": {"S": restaurant_name},
            "main_guest_name": {"S": main_guest_name},
            "number_of_persons": {"N": number_of_persons},
            "timestamp_utc": {"S": timestamp_utc},
        },
    )

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event["actionGroup"],
            "function": event["function"],
            "functionResponse": {
                "responseBody": {"TEXT": {"body": "Reservation was made successfully"}}
            },
        },
        "sessionAttributes": event["sessionAttributes"],
        "promptSessionAttributes": event["promptSessionAttributes"],
    }
