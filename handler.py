import json
import logging
import boto3
import os
import uuid

from lib.s3_helper import send_to_s3
from lib.target import Target
from scanners.port_scanner import PortScanner
from lib.response import Response
from scanners.http_observatory_scanner import HTTPObservatoryScanner
from lib.hosts import Hosts

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
SQS_CLIENT = boto3.client('sqs')


def addHttpObservatoryScanToQueue(event, context):
    data = json.loads(event['body'])
    if "target" not in data:
        logger.error("Unrecognized payload")
        return Response({
            "statusCode": 500,
            "body": json.dumps({'error': 'Unrecognized payload'})
        }).with_security_headers()

    target = Target(data.get('target'))
    if not target:
        logger.error("Target validation failed of: " +
                     target.name)
        return Response({
            "statusCode": 400,
            "body": json.dumps({'error': 'Target was not valid or missing'})
        }).with_security_headers()

    scan_uuid = str(uuid.uuid4())
    print(SQS_CLIENT.send_message(
        QueueUrl=os.getenv('SQS_URL'),
        MessageBody="httpobservatory|" + target.name
        + "|" + scan_uuid
    ))

    return Response({
        "statusCode": 200,
        "body": json.dumps({'uuid': scan_uuid})
    }).with_security_headers()


def addSshObservatoryScanToQueue(event, context):
    data = json.loads(event['body'])
    if "target" not in data:
        logger.error("Unrecognized payload")
        return Response({
            "statusCode": 500,
            "body": json.dumps({'error': 'Unrecognized payload'})
        }).with_security_headers()

    target = Target(data.get('target'))
    if not target:
        logger.error("Target validation failed of: " +
                     target.name)
        return Response({
            "statusCode": 400,
            "body": json.dumps({'error': 'Target was not valid or missing'})
        }).with_security_headers()

    scan_uuid = str(uuid.uuid4())
    print(SQS_CLIENT.send_message(
        QueueUrl=os.getenv('SQS_URL'),
        MessageBody="sshobservatory|" + target.name
        + "|" + scan_uuid
    ))

    return Response({
        "statusCode": 200,
        "body": json.dumps({'uuid': scan_uuid})
    }).with_security_headers()


def runScanFromQ(event, context):

    # This is needed for nmap static library to be added to the path
    original_pathvar = os.environ['PATH']
    os.environ['PATH'] = original_pathvar \
        + ':' + os.environ['LAMBDA_TASK_ROOT'] \
        + '/vendor/nmap-standalone/'

    # Read the queue
    for record, keys in event.items():
        for item in keys:
            if "body" in item:
                message = item['body']
                scan_type, target, uuid = message.split('|')
                if scan_type == "httpobservatory":
                    scanner = HTTPObservatoryScanner()
                    scan_result = scanner.scan(target)
                    send_to_s3(target + "_httpobservatory", scan_result)
                elif scan_type == "sshobservatory":
                    scanner = SSHObservatoryScanner()
                    scan_result = scanner.scan(target)
                    send_to_s3(target + "_sshobservatory", scan_result)
                elif scan_type == "portscan":
                    scanner = PortScanner(target)
                    nmap_scanner = scanner.scanTCP()
                    while nmap_scanner.still_scanning():
                        # Wait for 1 second after the end of the scan
                        nmap_scanner.wait(1)
                    send_to_s3(target + "_tcpscan", scanner.results)
                else:
                    # Manually invoked, just log the message
                    logger.info("Message in queue: " +
                                message)
            else:
                logger.error("Unrecognized message in queue: " +
                             message)

    os.environ['PATH'] = original_pathvar


def addScheduledHttpObservatoryScansToQueue(event, context):
    hosts = Hosts()
    hostname_list = hosts.getList()
    for hostname in hostname_list:
        SQS_CLIENT.send_message(
            QueueUrl=os.getenv('SQS_URL'),
            DelaySeconds=2,
            MessageBody="httpobservatory|" + hostname
            + "|"
        )
        logger.info("Tasking http observatory scan of: " + hostname)

    logger.info("Host list has been added to the queue for http observatory scan.")


def addScheduledSshObservatoryScansToQueue(event, context):
    hosts = Hosts()
    hostname_list = hosts.getList()
    for hostname in hostname_list:
        SQS_CLIENT.send_message(
            QueueUrl=os.getenv('SQS_URL'),
            DelaySeconds=2,
            MessageBody="sshobservatory|" + hostname
            + "|"
        )
        logger.info("Tasking ssh observatory scan of: " + hostname)

    logger.info("Host list has been added to the queue for ssh observatory scan.")


def putInQueue(event, context):
    # For demo purposes, this function is invoked manually
    # Also for demo purposes, we will use a static list here
    # We need to figure out a way to put stuff in the queue regularly
    target_list = [
        "www.mozilla.org",
        "infosec.mozilla.org",
    ]
    hosts = Hosts(target_list)
    target = Target(hosts.next())
    print(SQS_CLIENT.send_message(
        QueueUrl=os.getenv('SQS_URL'),
        MessageBody="manual|" + target.name
    ))
