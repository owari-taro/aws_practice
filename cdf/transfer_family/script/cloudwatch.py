"""
cloudwatchから直近x分内のログで次の条件に該当するものがある場合SNSにアラートを飛ばす

・READが1000件以上ある。
"""

from datetime import datetime, timedelta
import boto3
import time

client = boto3.client("logs")
log_group = "/aws/transfer/s-cc02c068ad6b47efb"
end_time = datetime.now()
start_time = end_time - timedelta(hours=2)

start_query_response = client.start_query(
    logGroupName=log_group,
    startTime=start_time,
    endTime=end_time,
    queryString='fields @timestamp,@message  @logStream, @log| sort @timestamp desc| filter @message like /"mode":"READ"/',
    limit=1000,
)

query_id = start_query_response["queryId"]

while True:
    response = client.get_query_results(queryId=query_id)
    if response["status"] == "Complete":
        results = response["results"]
        break
    time.sleep(1)

for result in results:
    print(result)
