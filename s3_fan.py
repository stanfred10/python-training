import boto3
import json
import os


# Paginate function
def paginate(method, **kwargs):
    client = method.__self__
    paginator = client.get_paginator(method.__name__)
    for page in paginator.paginate(**kwargs).result_key_iters():
        for result in page:
            yield result


def get_org_accounts(session):
    # Get list of ACTIVE accounts in the organization, this list contains only accounts that have been created or accepted
    # an invitation to the organization.  This list will also contain those accounts without the Organization service role.
    client = session.client('organizations')
    try:
        org_session = session.client('organizations')
        org_response = org_session.list_accounts()
        org_accounts = []
        for key in paginate(org_session.list_accounts):
            if key['Status'] == 'ACTIVE':
                org_accounts.append(str(key['Id']))
    except Exception as e:
        print('Failed to list organization accounts.', e)
        return
    return org_accounts


# Main entry point for the Lambda Function.
def lambda_handler(event, context):

    # Set environment variables
    aws_region = os.environ.get('aws_region')
    apply_bucket_policy = os.environ.get('apply_bucket_policy')
    master_account_Id = os.environ.get('master_account_Id')
    function_name = os.environ.get('function_name')
    accounts_to_exclude = os.environ.get('accounts_to_exclude')
    organization_service_role = os.environ.get('organization_service_role')
    sts_role_session_name = os.environ.get('sts_role_session_name')
    enable_dry_run_mode = os.environ.get('enable_dry_run_mode')
    exclude_Buckets = os.environ.get('exclude_Buckets')
    dry_run =enable_dry_run_mode if (enable_dry_run_mode.lower() == 'true' or enable_dry_run_mode.lower()== 'false') else 'true'

    
    session = boto3.Session(region_name=aws_region)
    accounts = get_org_accounts(session)
    
    accounts_to_exclude= [account for account in accounts_to_exclude.split(',')]
    accounts = list(set(accounts) - set(accounts_to_exclude))
    print('Excluding accounts', list(set(accounts_to_exclude)))
    print('processing accounts', accounts)


  # Execute CloudWatch Lambda task function
    lambda_client = session.client('lambda')
    try:
        for account in accounts:
            if account not in accounts_to_exclude:
                print('Calling Lambda function to process account ', account)
                payload = {
                    'account' : account,
                    'apply_bucket_policy': apply_bucket_policy,
                    'aws_region' : aws_region,
                    'master_account_Id' : master_account_Id,
                    'organization_service_role' : organization_service_role,
                    'sts_role_session_name' : sts_role_session_name,
                    'enable_dry_run_mode' : enable_dry_run_mode,
                    'exclude_Buckets' : exclude_Buckets
                }
                payload = json.dumps(payload)
                print(payload)
                lambda_client.invoke(
                FunctionName = function_name,
                InvocationType='Event',
                LogType = 'Tail',
                Payload = payload
                )

    except Exception as e:
        
        print('Failed to process accounts.', str(e))