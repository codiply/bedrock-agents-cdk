import os
import boto3
import json
from boto3.dynamodb.conditions import Key

RESERVATIONS_DYNAMODB_TABLE_NAME = os.environ["RESERVATIONS_DYNAMODB_TABLE_NAME"]
METADATA_S3_BUCKET = os.environ["METADATA_S3_BUCKET"]
METADATA_S3_KEY = os.environ["METADATA_S3_KEY"]

s3_resource = boto3.resource("s3")
dynamo_resource = boto3.resource("dynamodb")

reservations_table = dynamo_resource.Table(RESERVATIONS_DYNAMODB_TABLE_NAME)


def _get_parameter(event, param_name):
    return next(p for p in event["parameters"] if p["name"] == param_name)["value"]


def _load_metadata_json():
    metadata_object = s3_resource.Object(METADATA_S3_BUCKET, METADATA_S3_KEY)
    metadata_content = metadata_object.get()["Body"].read().decode("utf-8")
    metadata_json = json.loads(metadata_content)

    return metadata_json


ALL_RESTAURANT_METADATA = _load_metadata_json()


def _get_metadata(restaurant_name):
    return next(
        m for m in ALL_RESTAURANT_METADATA if m["restaurant_name"] == restaurant_name
    )


def _get_total_reservations_persons(restaurant_name):
    reservations = reservations_table.scan(
        FilterExpression=Key("restaurant_name").eq(restaurant_name)
    )["Items"]

    if reservations:
        return sum([int(r["number_of_persons"]) for r in reservations])

    return 0


def main(event, context):

    print(json.dumps(event, indent=4))

    restaurant_name = _get_parameter(event, "restaurant_name")
    restaurant_metadata = _get_metadata(restaurant_name)

    capacity_persons = restaurant_metadata["capacity_persons"]
    total_reservations_persons = _get_total_reservations_persons(restaurant_name)

    remaining_capacity_persons = capacity_persons - total_reservations_persons

    if remaining_capacity_persons <= 0:
        response = (
            "The restaurant is fully booked. "
            f"Remaining capacity is {remaining_capacity_persons} persons."
        )
    else:
        response = f"There is availability for {remaining_capacity_persons} persons."

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
