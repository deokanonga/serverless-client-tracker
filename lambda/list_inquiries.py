"""Returns every inquiry in the DynamoDB table, newest first, for the admin page.

Environment variable (set in Lambda → Configuration → Environment variables):
  TABLE_NAME   the DynamoDB table, e.g. Inquiries
"""
# Tools: JSON replies and settings.
import json
import os

# The AWS SDK for Python, used to talk to DynamoDB.
import boto3

# Connection to the Inquiries table, opened once and reused for every request.
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


# Lambda runs this every time the admin page asks for the list.
def lambda_handler(event, context):
    # Read every row. DynamoDB returns at most 1 MB per call, so keep asking until there is no next page.
    items = []
    options = {}
    while True:
        page = table.scan(**options)
        items += page["Items"]
        if "LastEvaluatedKey" not in page:
            break
        options["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    # Newest inquiries first.
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)

    # Send the list back to the admin page as JSON.
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(items, default=str),
    }
