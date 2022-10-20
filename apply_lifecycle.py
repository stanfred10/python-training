import boto3
import sys
from botocore.exceptions import ClientError
import json
import csv


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
        aws_session_token=sts_response['Credentials']['SessionToken'],
      )
    except Exception as err:
      # If sub account does not have Organization service role we log it and ignore the account.
      sts_session = ''
      print('failed to assume role for account', account, err)
  else:
    sts_session = session 
  return sts_session


def lifecycle_apply(bucketName, rule, dry_run,default_LifeCycle_Policy, message):
    try:
        s3_resource = boto3.resource('s3')
        
        if dry_run == True:
           
            print('DRY_RUN: ', dry_run,'STATUS: ',message, 'BUCKET: ',bucketName,'RULE: ', rule)
            print('')
           
        elif dry_run == False:
            bucket_lifecycle_configuration = s3_resource.BucketLifecycleConfiguration(bucketName)
            response = bucket_lifecycle_configuration.put(
            LifecycleConfiguration={
                'Rules':default_LifeCycle_Policy
            })
            print('DRY_RUN: ', dry_run,'STATUS: ',message,'BUCKET: ',bucketName,'RULE: ', rule)
            
    except Exception as e:
        print('Uncaught exception: ',e)


def apply_Bucket_Policy(bucketName, session, dry_run, apply_bucket_policy_permission):
     #Applies bucket policies
    s3_resource = session.resource('s3')
    bucket_policy = s3_resource.BucketPolicy(bucketName)
    enable_dry_run = 'False' if dry_run==False else 'True'
    basePolicy = {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Sid': 'cross_Account_Access',
                        'Effect': 'Allow',
                        'Principal': {
                            'AWS':'arn:aws:iam::335418536307:role/jcrew-management-prod-LambdaRoleFullOrgAccess'
                        },
                        'Action': 's3:*',
                        'Resource': [
                            'arn:aws:s3:::{}'.format(bucketName),
                            'arn:aws:s3:::{}/*'.format(bucketName)
                        ]
                    }
                ]
                }
    policy = get_Bucket_Policy(session, bucketName, dry_run)
    updatePolicy={}
    change= 'No change'
    foundCrossAccoint= False
    if policy == {}:
        change='Applied'
        updatePolicy = basePolicy
    else:
        for statement_id in policy['Statement']:
            if statement_id['Sid'] == 'cross_Account_Access':
                foundCrossAccoint= True
        
        if not foundCrossAccoint:
            list = policy['Statement'][0]
            basic = basePolicy['Statement'][0]
            updatePolicy ={ 'Version': '2012-10-17',
                        'Statement': [list, basic]}
            change='Updated'

    if dry_run == False:
        if change != 'No change' and apply_bucket_policy_permission:
            response= bucket_policy.put(Bucket=bucketName, Policy=json.dumps(updatePolicy, indent = 4))
    elif not apply_bucket_policy_permission and not foundCrossAccoint:
        print('Could not access lifecycle configuration of ', bucketName, "Apply bucket policy to view lifecycle configuration")

    print('DRY_RUN: '+enable_dry_run+' BUCKET_NAME: '+bucketName+' BUCKET_POLICY: '+change)
 
    
def get_Bucket_Policy(session, bucketName, dry_run):
    '''
    Gets bucket policy 
    '''
    s3_client = session.client('s3')
   
    try:
        BucketPolicy = s3_client.get_bucket_policy(Bucket = bucketName)
        policy = json.loads(BucketPolicy['Policy'])
        return policy
            
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
            policy = {}
            return policy


def lambda_handler(event, context):
    
    s3_client = boto3.client('s3')
    bucket_list = s3_client.list_buckets()
    exclude_by_name = []
    default_LifeCycle_Policy = [
                    {
                        'Expiration': {
                            'Days': 30,
                        },
                        'ID': 'jcrew-default-s3-lifecycle',
                        'Prefix': 'test',
                        'Status': 'Enabled',
                        'Transitions': [
                            {
                                'Days': 7,
                                'StorageClass': 'INTELLIGENT_TIERING'
                            },
                        ],
                        'NoncurrentVersionTransitions': [
                            {
                                'NoncurrentDays': 7,
                                'StorageClass': 'INTELLIGENT_TIERING'
                            },
                        ],
                        'NoncurrentVersionExpiration': {
                            'NoncurrentDays': 31
                        },
                        'AbortIncompleteMultipartUpload': {
                            'DaysAfterInitiation': 7
                        }
                    }
                ]
    
    enable_dry_run_mode = event['enable_dry_run_mode']
    master_account_Id = event['master_account_Id']
    account = event['account']
    aws_region = event['aws_region']
    apply_bucket_policy_permission = event['apply_bucket_policy']
    organization_service_role = event['organization_service_role']
    sts_role_session_name = event['sts_role_session_name']
    exclude_Buckets = event['exclude_Buckets']
    buckets_to_exclude = [exclude_Buckets for exclude_Buckets in exclude_Buckets.split(',')]
    dry_run = False if enable_dry_run_mode.lower() == 'false' else True
    apply_bucket_policy_permission = False if apply_bucket_policy_permission.lower() == 'false' else True
    session = get_sts_session(account, master_account_Id, organization_service_role, sts_role_session_name)
    
    s3_resource = session.resource('s3')
    message = ""
    
    if session != '':
        print('ACCOUNT: ', account)
        for bucket in s3_resource.buckets.all():
            bucketName = bucket.name
            if 'jc-' not in bucketName and 'test' not in bucketName:
                
                try:
                    apply_Bucket_Policy(bucketName,session, dry_run,apply_bucket_policy_permission)
                    # response = get_Bucket_Policy(session, bucketName, dry_run)
                    
                    
                    lifecycle = s3_client.get_bucket_lifecycle(Bucket = bucketName)

                    rules = lifecycle['Rules'] if 'Rules' in lifecycle else []
                    for rule in rules:
                        if 'jcrew-default-s3-lifecycle' in rule.values():
                            message = 'Default lifecycle already exist'
                            print('BUCKET_NAME: ',bucketName,'RULE: ', message)
                        elif 'jcrew-default-s3-lifecycle' not in rule.values():
                            message = 'Already has lifecycle applied that is not the default.'
                            print('BUCKET_NAME: ',bucketName,'RULE: ', message)
                    if rules == []:
                        message = 'Default lifecycle applied'
                        lifecycle_apply(bucketName, rules, dry_run, default_LifeCycle_Policy, message)
                        
                            
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NoSuchLifecycleConfiguration':
                        rules='No lifecycle policy'
                        message= 'Default lifecycle applied'
                        lifecycle_apply(bucketName, rules, dry_run, default_LifeCycle_Policy, message)
                       
                except Exception as e:

                    print('Uncaught exception: ', e)
            # else:
            #     print('Exclude: ', bucket)

