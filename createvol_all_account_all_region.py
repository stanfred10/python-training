import boto3
import os
import re
import json
import sys
from botocore.exceptions import ClientError


ec2 = boto3.resource('ec2', region_name='us-east-1')
ec2_client = boto3.client('ec2', region_name='us-east-1')
volume = ec2.Volume('id')
client = boto3.client('organizations')

# Paginate function
def paginate(method, **kwargs):
    client = method.__self__
    paginator = client.get_paginator(method.__name__)
    for page in paginator.paginate(**kwargs).result_key_iters():
        for result in page:
            yield result

def lambda_handler(event, context):
 
  organization_service_role = 'OrganizationAccountAccessRole'
  sts_role_session_name = 'org-session'
  
  session = boto3.Session(region_name='us-east-1')
  org_client = session.client('organizations')
  # regions = [regions['RegionName'] for regions in session.client('ec2').describe_regions()['Regions']]

  # Get list of ACTIVE accounts in the organization, this list contains only accounts that have been created or accepted
  # an invitation to the organization.  This list will also contain those accounts without the Organization service role.

  org_accounts = []
  for key in paginate(org_client.list_accounts):
    if key['Status'] == 'ACTIVE':
      org_accounts.append(str(key['Id']))

  result = {}
  all_hosts = []

  # list accounts where you want to the volumes to be created in
  org_accounts = ['845541912972']

  for account in org_accounts:

      sts_client = session.client('sts')

      regions = ['us-east-1']
      # regions = ['us-east-1','us-west-2']
    
      for region in regions:  
        print('=========================================================================================================================================')
        print('Processing account', account, ' and region ', region)

        
          # for Zone in region:

    ##############################################################################################################
    ##############################################################################################################
          # # Use STS to assume a temporary role in the sub account that has the Organization service role.
          # # If the sub account does not have the Organization service role it will be excepted.
        try:
          role_arn = 'arn:aws:iam::' + account + ':role/' + organization_service_role
          # role_arn = 'arn:aws:iam::335418536307:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_account-admin_788ae45a0b3e7ff0'
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
          region_name=region
        )
        except:
        # If sub account does not have Organization service role we log it and ignore the account.
          sts_session = ''
          print('failed to assume role for account', account)
          break
        # else:
        #   sts_session = session 
        
    ##############################################################################################################
    ##############################################################################################################

        if sts_session != '':

          info = []
        
          #### Code to execute against all regions in every account
          ec2_client = sts_session.client('ec2', region_name=region)
          ssm_client = sts_session.client('ssm', region_name=region)
          
          Zones=ec2_client.describe_availability_zones()
          for Zone in Zones['AvailabilityZones']:
            # print(Zone['ZoneName'])
            zone = Zone['ZoneName']
            if region in zone:
              print(region, zone)
              for counter in range(1):
                response=ec2_client.create_volume(
                AvailabilityZone= zone,
                Size=100,
                VolumeType='gp3',
                Iops=3001,
                TagSpecifications=[
                    {
                        'ResourceType': 'volume',
                        #Add tags here, you can add as many as you like
                        'Tags': [
                            {'Key': 'hello','Value': 'world'}, 
                            # {'Key': 'kabza','Value': 'Abalele'},
                           
                          
                        ]
                    },
                ],

                )
                
                print('**VOLUME SUCCESSFULLY CREATED**',response) 
lambda_handler(
  {
    'action': 'run'
  },
  'context'
)

