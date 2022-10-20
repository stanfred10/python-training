import boto3
import json
import os

client = boto3.client('lambda')

# Paginate function
def paginate(method, **kwargs):
    client = method.__self__
    paginator = client.get_paginator(method.__name__)
    for page in paginator.paginate(**kwargs).result_key_iters():
        for result in page:
            yield result
            
# Main entry point for the Lambda Function.
def lambda_handler(event, context):
    # Set environment variables
    region = os.environ.get('region')
    master_account_Id = os.environ.get('master_account_Id')
    account = os.environ.get('account')
    function_name = os.environ.get('function_name')
    accounts_to_exclude = os.environ.get('accounts_to_exclude')
    organization_service_role = os.environ.get('organization_service_role')
    sts_role_session_name = os.environ.get('sts_role_session_name')
    enable_dry_run_mode = os.environ.get('enable_dry_run_mode')
    exclusion_tags = os.environ.get('exclusion_tags')
    enable_dry_run_mode =enable_dry_run_mode if (enable_dry_run_mode.lower == "true" or enable_dry_run_mode.lower()== "false") else "true"


    session = boto3.Session(region_name= region)
    org_client= session.client('organizations')
    org_response = org_client.list_accounts()
    # regions = [regions['RegionName'] for regions in session.client('ec2').describe_regions()['Regions']]
    regions = ['us-east-1', 'us-west-2']

    # Get list of ACTIVE accounts in the organization, this list contains only accounts that have been created or accepted
    # an invitation to the organization.  This list will also contain those accounts without the Organization service role.
    
    
    org_accounts = []
    for key in paginate(org_client.list_accounts):
        if key['Status'] == 'ACTIVE':
            org_accounts.append(str(key['Id']))
    accounts_to_exclude = [account for account in accounts_to_exclude.split(',')]
    org_accounts = list(set(org_accounts) - set(accounts_to_exclude))
    print('Excluding accounts', list(set(accounts_to_exclude)))
    print('processing accounts', org_accounts)
  
  # Execute CloudWatch Lambda task function
    lambda_client = session.client('lambda')
    try:
        for account in org_accounts:
                for aws_region in regions:
                    if session !='':
                        payload = {
                            "account": account,
                            "region": aws_region,
                            "master_account_Id": master_account_Id,
                            "organization_service_role": organization_service_role,
                            "enable_dry_run_mode" :enable_dry_run_mode,
                            "sts_role_session_name" :sts_role_session_name,
                            "exclusion_tags":exclusion_tags
                        }
                        payload = json.dumps(payload)
                        print(payload)
                        lambda_client.invoke(
                        FunctionName=function_name,
                        InvocationType='Event',
                        LogType='Tail',
                        Payload=payload
                        )

    except Exception as e:
        print('Failed to process accounts.', str(e))