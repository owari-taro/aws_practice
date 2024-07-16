import sys
import os
import boto3
import json


def handler(event, context):
    #print(event)
    #print(context)
    subject = "日本語OKKKK???"
    object_key = event["Records"][0]["s3"]["object"]["key"]
    msg = f"{object_key}がアップロードされました???????????????"
    client = boto3.client("sns")
    message_attributes = {
        "test": {
            "DataType": "String",
            "StringValue": "hoge",  # 通知者表示に使用される送信者ID
        }
    }

    request = {
        "TargetArn": os.environ["SnsTopicArn"],
        "Message": msg,
        "Subject": subject,
        # "MessageAttributes": message_attributes,
    }
    response = client.publish(**request)
    print(response)
    return {"statusCode": 200, "body": json.dumps("Hello from Lambda!")}
