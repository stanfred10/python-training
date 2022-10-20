import json
import boto3
import sys
from botocore.exceptions import ClientError

def paginate(method, **kwargs):
    client = method.__self__
    paginator = client.get_paginator(method.__name__)
    for page in paginator.paginate(**kwargs).result_key_iters():
        for result in page:
            yield result


def get_sts_session(account, master_account_Id, organization_service_role, sts_role_session_name):
    session = boto3.Session(region_name='us-east-1')
    
    sts_client = session.client('sts')
    # Use STS to assume a temporary role in the sub account that has the Organization service role.
    # If the sub account does not have the Organization service role it will be excepted.

    if account != master_account_Id:
        try:
            role_arn = 'arn:aws:iam::' + account + ':role/' + organization_service_role
            sts_response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=sts_role_session_name,
                DurationSeconds=900
                )
            # Create boto3 session for account.
            sts_session = boto3.Session(
                aws_access_key_id=sts_response['Credentials']['AccessKeyId'],
                aws_secret_access_key=sts_response['Credentials']['SecretAccessKey'],
                aws_session_token=sts_response['Credentials']['SessionToken']
            )
        except Exception as err:
            # If sub account does not have Organization service role we log it and ignore the account.
            sts_session = ''
            print('failed to assume role for account', account, err)
    else:
        sts_session = session 
    return sts_session

            
def lambda_handler(event, context):
    #Variables that are parsed from the fan function through the payload
    enable_dry_run_mode = event['enable_dry_run_mode']
    master_account_Id = event['master_account_Id']
    region = event['region']
    account = event['account']
    organization_service_role = event['organization_service_role']
    sts_role_session_name = event['sts_role_session_name']
    exclusion_tags_event = event['exclusion_tags']
    
    dry_run = False if enable_dry_run_mode.lower() == 'false' else True
    
    #Create sts session
    session = get_sts_session(account, master_account_Id, organization_service_role, sts_role_session_name)
    
    #Code to execute against all regions in every account 
    ec2_client = session.client('ec2', region_name=region)
    
    
    ebs_volumes = ec2_client.describe_volumes()
    exclusion_tags =  dict(x.split(":") for x in exclusion_tags_event.split(","))
    
    #Execute code if session is valid
    if session != '':
        try:
            print('Processing account', account, ' and region ', region)

            for volume in ebs_volumes['Volumes']:
                VolumeId = volume['VolumeId']
                VolumeType = volume['VolumeType']
                VolumeIops = volume['Iops']
                VolumeSize = volume['Size']
                volumeTags = volume['Tags'] if "Tags" in volume else []
                tagsMatch = False
                
                #Executing on volumes that are gp2
                if VolumeType == 'gp2':
                    try:
                        #Exclude volumes that have tags that match the exclusion tags
                        volumeTags = volume['Tags'] if "Tags" in volume else []
                        for key,value in exclusion_tags.items():
                            
                            for tag in volumeTags:
                                #Evaluating or comparing the tags when a wild card is present
                                if (tag['Key'].lower() == key.lower() and tag['Value'].lower() == value.lower()) or (tag['Key'].lower() == key.lower() and value == '*'):
                                    tagsMatch=True
                                    break
                            if tagsMatch == True:
                                break
                        
                        if tagsMatch == False:
                            #Modify volumes and assign IOPS and Throughput values
                            if volume['Iops'] < 3000:
                                if VolumeSize >= 350:
                                    message= 'DRY_RUN: , {dry_run_mode}, VOLUME: {Id},TAGS: {tags}, Volume iops is less than 3000 and volume size is more than 350. Setting throughput to 250 and iops to 3000'.format(Id=VolumeId, tags=volumeTags, dry_run_mode= dry_run )
                                    modify = ec2_client.modify_volume(VolumeId=VolumeId, Iops=3000,VolumeType='gp3', Throughput=250, DryRun=dry_run)
                                    print("STATUS: ",message)
                                else:
                                    message='DRY_RUN: , {dry_run_mode}, VOLUME: {Id},TAGS: {tags}, Volume iops is less than 3000 and volume size is less than 350. Setting throughput to 125 and iops to 3000'.format(Id=VolumeId, tags=volumeTags, dry_run_mode= dry_run)
                                    modify = ec2_client.modify_volume(VolumeId=VolumeId, Iops=3000, VolumeType='gp3', Throughput=125, DryRun=dry_run)
                                    print("STATUS: ",message)
                            elif volume['Iops'] >= 3000:
                                if VolumeSize >= 350:
                                    message='DRY_RUN: , {dry_run_mode}, VOLUME: {Id},TAGS: {tags}, Volume iops is more than 3000 and volume size is more than 350. Setting throughput to 250 and iops to , {Iops}'.format(Id=VolumeId, tags=volumeTags, Iops=VolumeIops, dry_run_mode= dry_run)
                                    modify = ec2_client.modify_volume(VolumeId=VolumeId, Iops=VolumeIops, VolumeType='gp3', Throughput=250, DryRun=dry_run)
                                    print("STATUS: ",message)
                    except ClientError as e:
                        if e.response['Error']['Code'] == 'DryRunOperation':
                            print("STATUS: ",message)
                            
                    except Exception as  e:
                        print('Exception Occurred: %s' % e)

        except Exception as e:
            print("Uncaught exception: ", e)
    
    else:
        print('No valid session')