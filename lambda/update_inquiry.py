"""Changes the status and/or private notes of one inquiry, for the admin page.

Called by PATCH /inquiries/{id} with a JSON body such as {"status": "booked"} or {"notes": "..."}.

Environment variable (set in Lambda → Configuration → Environment variables):
  TABLE_NAME   the DynamoDB table, e.g. Inquiries
"""
# Tools: base64 decoding, JSON replies, settings, timestamps.
import base64
import json
import os
from datetime import datetime, timezone

# The AWS SDK for Python, used to talk to DynamoDB.
import boto3

# Connection to the Inquiries table, opened once and reused for every request.
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

# The client journey. Any other status is refused (must match STATUSES in admin.html).
STATUSES = ["new", "replied", "contract_sent", "deposit_paid", "booked", "delivered"]


# Builds the answer sent back to the admin page.
def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


# Lambda runs this every time the admin page saves a change.
def lambda_handler(event, context):
    # The inquiry ID comes from the address, e.g. /inquiries/1b2c...
    inquiry_id = (event.get("pathParameters") or {}).get("id")
    # Read the JSON body, decoding it if it arrived in base64.
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    try:
        changes = json.loads(body)
    except ValueError:
        changes = None
    if not isinstance(changes, dict):
        return respond(400, {"error": "Body must be a JSON object"})

    # Build the update: only "status" and "notes" may change.
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sets, names, values = [], {}, {}
    if "status" in changes:
        if changes["status"] not in STATUSES:
            return respond(400, {"error": "Unknown status"})
        sets += ["#s = :s", "#t = :now"]
        names.update({"#s": "status", "#t": "status_updated_at"})
        values[":s"] = changes["status"]
        values[":now"] = now
    if "notes" in changes:
        sets.append("#n = :n")
        names["#n"] = "notes"
        values[":n"] = str(changes["notes"])[:5000]
    if not inquiry_id or not sets:
        return respond(400, {"error": "Nothing to update"})

    try:
        # Field names are written as #s, #t, #n because "status" is a reserved word in DynamoDB.
        # The condition stops this from creating a new row if the ID does not exist.
        result = table.update_item(
            Key={"id": inquiry_id},
            UpdateExpression="SET " + ", ".join(sets),
            ExpressionAttributeValues=values,
            ExpressionAttributeNames=names,
            ConditionExpression="attribute_exists(id)",
            ReturnValues="ALL_NEW",
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return respond(404, {"error": "Inquiry not found"})

    # Send the updated inquiry back so the page shows what was saved.
    return respond(200, result["Attributes"])
