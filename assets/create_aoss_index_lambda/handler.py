import os
import time
import json

import boto3
from requests import request
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

AWS_REGION = os.environ["AWS_REGION"]
COLLECT_ENDPOINT = os.environ["COLLECTION_ENDPOINT"]
VECTOR_INDEX_NAME = os.environ["VECTOR_INDEX_NAME"]
VECTOR_DIMENSION = int(os.environ["VECTOR_DIMENSION"])
METADATA_FIELD = os.environ["METADATA_FIELD"]
TEXT_FIELD = os.environ["TEXT_FIELD"]
VECTOR_FIELD = os.environ["VECTOR_FIELD"]


def main(event, context):
    url = COLLECT_ENDPOINT + "/" + VECTOR_INDEX_NAME
    headers = {
        "content-type": "application/json",
        "accept": "application/json",
    }
    payload = {
        "settings": {"index": {"knn": "true"}},
        "mappings": {
            "properties": {
                VECTOR_FIELD: {
                    "type": "knn_vector",
                    "dimension": VECTOR_DIMENSION,
                    "method": {
                        "name": "hnsw",
                        "engine": "faiss",
                        "space_type": "l2",
                        "parameters": {
                            "ef_construction": VECTOR_DIMENSION,
                            "m": 16,
                            "ef_search": VECTOR_DIMENSION,
                        },
                    },
                },
                METADATA_FIELD: {"type": "text"},
                TEXT_FIELD: {"type": "text"},
            }
        },
    }

    service = "aoss"
    credentials = boto3.Session().get_credentials()

    params = None
    payload_json = json.dumps(payload)

    signer = SigV4Auth(credentials, service, AWS_REGION)
    while True:
        try:
            req = AWSRequest(
                method="PUT", url=url, data=payload_json, params=params, headers=headers
            )
            req.headers["X-Amz-Content-SHA256"] = signer.payload(req)
            SigV4Auth(credentials, service, AWS_REGION).add_auth(req)
            req = req.prepare()

            response = request(
                method=req.method, url=req.url, headers=req.headers, data=req.body
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to create index - status: {response.status_code}. Reason: {response.reason}"
                )

        except Exception as e:
            print("Retrying to create index...")
            time.sleep(3)
            continue

        print(f"Index create successfully: {response.text}")
        break
    
    # Attempt to avoid CloudFormation error:
    # The knowledge base storage configuration provided is invalid...
    time.sleep(10)
