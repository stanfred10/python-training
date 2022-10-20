from distutils.util import execute
import boto3
import os
import os
import re
import json
import csv
import sys
from collections import OrderedDict
from pprint import pprint
from botocore.exceptions import ClientError


def get_snapshots(ec2,exclusion_tags):
    '''
    Gets all snapshots 
    Exclude snapshots that has tags that match exclusion tags.
    '''
    
    for snapshot in ec2.describe_snapshots(OwnerIds=['self'])['Snapshots']:
        instance_id, image_id = parse_description(snapshot['Description'])
      
        tag_found = False
        snapshotTags = snapshot['Tags'] if 'Tags' in snapshot else []

        for key,value in exclusion_tags.items():
            for tag in snapshotTags:
                if tag['Key'] == key:
                    if tag['Value'].lower() == value.lower() or value == '*':
                        tag_found=True
                        break
            if tag_found == True:
                break
                      
        if tag_found == False: 

            yield {
                'id': snapshot['SnapshotId'],
                'name': snapshot['Name'] if 'Name' in snapshot  else 'no name',
                'status': snapshot['State'],
                'description': snapshot['Description'] if 'Description' in snapshot and snapshot['Description'].strip() != '' else 'no description',
                'start_time': snapshot['StartTime'],
                'size': snapshot['VolumeSize'],
                'volume_id': snapshot['VolumeId'],
                'volume_exists': volume_exists(snapshot['VolumeId'],ec2),
                'instance_id': instance_id,
                'instance_exists': instance_exists(instance_id,ec2),
                'ami_id': image_id,
                'ami_exists': image_exists(image_id,ec2),
                'tags': OrderedDict(sorted([(tag['Key'], tag['Value']) for tag in snapshot['Tags']])) if 'Tags' in snapshot else '##no tags##',
            }


def get_available_volumes(ec2,exclusion_tags):
    '''
    Get all volumes in 'available' state. (Volumes not attached to any instance)
    Exclude volumes that has tags that match exclusion tags.
    '''

    for volume in ec2.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])['Volumes']:
        
        tag_found = False

        volumeTags = volume['Tags'] if 'Tags' in volume else []
        for key,value in exclusion_tags.items():
            for tag in volumeTags:
               if tag['Key'] == key:
                    if tag['Value'].lower() == value.lower() or value == '*':
                        tag_found=True
                        break
            if tag_found == True:
                break
                      
        if tag_found == False:        
            yield {
                
                'id': volume['VolumeId'], 
                'name': volume['Name'] if 'Name' in volume else 'no name' ,      
                'create_time': volume['CreateTime'],
                'status': volume['State'],
                'type': volume['VolumeType'],
                'size': volume['Size'],
                'snapshot_id': volume['SnapshotId'],
                'snapshot_exists': str(snapshot_exists(volume['SnapshotId'],ec2)),
                'tags': OrderedDict(sorted([(tag['Key'], tag['Value']) for tag in volume['Tags']])) if 'Tags' in volume else '##no tags##',
            }    


def get_images(ec2,exclusion_tags):
    '''
    Get all images.
    Exclude images that has tags that match exclusion tags
    '''
    
    for image in ec2.describe_images(Owners=['self'])['Images']:
        instance_id= image['InstanceId'] if 'InstanceId' in image else []

        tag_found = False
        imageTags = image['Tags'] if 'Tags' in image else []

        for key,value in exclusion_tags.items():
            for tag in imageTags:
                if tag['Key'] == key:
                    if tag['Value'].lower() == value.lower() or value == '*':
                        tag_found=True
                        break
            if tag_found == True:
                break
                      
        if tag_found == False: 
               
            yield {
                'id': image['ImageId'],
                'name': image['Name'] if 'Name' in image else 'no name',
                'description': image['Description'] if 'Description' in image else 'no description',
                'instance_exists': instance_exists(instance_id,ec2),
                'tags': OrderedDict(sorted([(tag['Key'], tag['Value']) for tag in image['Tags']])) if 'Tags' in image else '##no tags##',
            }


def snapshot_exists(snapshot_id,ec2):
    if not snapshot_id:
        return False
    try:
        ec2.describe_snapshots(SnapshotIds=[snapshot_id])
        return True
    except ClientError:
        return False


def volume_exists(volume_id,ec2):
    if not volume_id:
        return False
    try:
        ec2.describe_volumes(VolumeIds=[volume_id])
        return True
    except ClientError:
        return False


def instance_exists(instance_id,ec2):
    if not instance_id:
        return False
    try:
        return len(ec2.describe_instances(InstanceIds=[instance_id])['Reservations']) != 0
    except ClientError:
        return False


def image_exists(image_id,ec2):
    if not image_id:
        return False
    try:
        return len(ec2.describe_images(ImageIds=[image_id])['Images']) != 0
    except ClientError:
        return False


def parse_description(description):
    regex = r"^Created by CreateImage\((.*?)\) for (.*?) "
    matches = re.finditer(regex, description, re.MULTILINE)
    for matchNum, match in enumerate(matches):
        return match.groups()
    return '', ''


def csv_writer():
    '''
    writes the heading in the csv file.
    '''
    with open('report.csv', 'w') as csv_file:
                            write_csv = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL,lineterminator='\n')
                            write_csv.writerow([
                                'Dry run',
                                'Account',
                                'Region',
                                'Resource ID', 
                                'Name', 
                                'State',
                                'Size', 
                                'Description/Type'                           
                                ])


def csv_append(Dry_run,Account,Region,resource_id, resource_name, resource_state, resource_size, resource_description):
    '''
    Appends ec2 resources changes to csv file.
    '''
    with open('report.csv', 'a') as csv_file:
                            write_csv = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
                            write_csv.writerow([
                                Dry_run ,
                                Account,
                                Region,
                                resource_id, 
                                resource_name,
                                resource_state, 
                                resource_size,
                                resource_description  
                                ])


def paginate(method, **kwargs):
    client = method.__self__
    paginator = client.get_paginator(method.__name__)
    for page in paginator.paginate(**kwargs).result_key_iters():
        for result in page:
            yield result


def get_sts_session(account, master_accountId, organization_service_role, sts_role_session_name):
    # Use STS to assume a temporary role in the sub account that has the Organization service role.
    # If the sub account does not have the Organization service role it will be excepted.
    session = boto3.Session(region_name='us-east-1')
    sts_client = session.client('sts')
    

    if account != master_accountId:
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


def lambda_handler(event, context):
    run_delete_volumes = str(input('Run delete volumes(yes/no)?'))  
    run_delete_snapshots= str(input('Run delete snapshots(yes/no)?'))
    run_delete_images = str(input('Run delete images(yes/no)?'))
    
    # exclusion_tags = {'rk_component':'Cloud Native Protection', 'rk_taskchain_id':'*','rk_work':'Money'}
    exclusion_tags={}
    print('Specify the key value pairs,when done entering the key value pairs enter exit in tag key: and in tag value: ')
    while True:

        try:

            key = str(input('Exclusion tag key: '))

            value = str(input('Exclusion tag value: '))

            exclusion_tags[key] = value

            if key == 'exit' or value == exit:

                break

            print(exclusion_tags)

        except Exception as e:
            print(e)

    accounts_to_exclude=['845541912972','513936039192','345625197086']
    
    organization_service_role = 'OrganizationAccountAccessRole'
    sts_role_session_name = 'org-session'
    master_accountId='335418536307'
    enable_dry_run_mode = '--dry-run' in sys.argv    

    
    session = boto3.Session(region_name='us-east-1')
    org_client = session.client('organizations')
    
    

    # Get list of ACTIVE accounts in the organization, this list contains only accounts that have been created or accepted
    # an invitation to the organization.  This list will also contain those accounts without the Organization service role.

    org_accounts = []
    for key in paginate(org_client.list_accounts):
        if key['Status'] == 'ACTIVE':
            org_accounts.append(str(key['Id']))
        accounts_to_exclude = [account for account in accounts_to_exclude]
        org_accounts = list(set(org_accounts) - set(accounts_to_exclude))

    print('Excluding accounts', list(set(accounts_to_exclude)))
    print('processing accounts', org_accounts)
    
    csv_writer()
    

    for account in org_accounts:
        sts_session = get_sts_session(account, master_accountId, organization_service_role, sts_role_session_name)
        # regions = [regions['RegionName'] for regions in sts_session.client('ec2').describe_regions()['Regions']]
        regions = ['us-east-1','us-west-2'] 
        for region in regions:  

           
            if sts_session != '':
                ec2_client = sts_session.client('ec2', region_name=region)

                print('Processing account', account, ' and region ', region)
                
                '''
                calls get_available_volumes()
                deletes volumes and calls csv_append() if run_delete_volumes's input is yes
                '''

                volCount = 0
            
                if run_delete_volumes.lower() == 'yes':
                    
                    print('Volumes to act on, in  account: {}, region: {} '.format(account,region))
                    print('*******************Volumes For deletion************************')   
                    for volume in get_available_volumes(ec2_client,exclusion_tags):
                        volCount +=1
                        try:
                            volume_Id = volume['id']
                            volume_Name = volume['name'] 
                            volume_Status = volume['status'] 
                            volume_Size = str(volume['size']) + 'gb' if 'size' in volume else 'no Size'
                            volume_Type = volume['type']             

                            csv_append(enable_dry_run_mode,account,region,volume_Id, volume_Name, volume_Status, volume_Size, volume_Type)       
                            response = ec2_client.delete_volume(VolumeId=volume_Id, DryRun=enable_dry_run_mode)   
                        
                            print('dryrun={} response = {}'.format(enable_dry_run_mode,response))                                  
                            print(volume_Id, '****DELETED****')
                        
                        except ClientError as e:
                            if e.response['Error']['Code'] == 'DryRunOperation':
                                print(volume_Id, volume['tags'] , 'DeleteVolume operation: ****DRY RUN**** NO ACTION HAS BEEN TAKEN ', e)
                                
                        except Exception as  e:
                            print('Exception Occurred: %s' % e) 
                    if volCount == 0:
                        print('No Volumes were Found / Volumes match the exclusion criteria')       

                else:
                    print('skipping volumes')   

                print('====================================************====================================')  
                
                '''
                calls get_images()
                deletes Images and calls csv_append() if run_delete_images's input is yes
                '''

                
                imagesCount = 0
                if run_delete_images == 'yes':
                    print('Images to act on, in account: {}, region: {} '.format(account,region))
                    print('********************images For deletion*************************')
                    for image in get_images(ec2_client,exclusion_tags):
                        imagesCount += 1
                        try:   
                            image_Id = image['id']             
                            image_Name = image['name']
                            image_State = image['state'] if 'state' in image else 'no Status '
                            image_Size = str(image['Size']) + 'gb' if 'Size' in image else 'no Size'
                            image_Description = image['description']  

                            csv_append(enable_dry_run_mode,account,region,image_Id, image_Name, image_State, image_Size,image_Description)
                            response = ec2_client.deregister_image(ImageId=image_Id, DryRun=enable_dry_run_mode)  
        
                        
                            print('dryrun={} response = {}'.format(enable_dry_run_mode,response))                  
                            print(image_Id, '****Deregistered****')
                        
                        except ClientError as e:  
                            if e.response['Error']['Code'] == 'DryRunOperation':
                                print(image_Id,image['tags'], 'Deregisterimage operation: ****DRY RUN**** NO ACTION HAS BEEN TAKEN ', e)
                        except Exception as  e:
                            print('Exception Occurred: %s' % e)   
                    if imagesCount == 0:            
                        print('No images were Found / images match the exclusion criteria')
                else:
                    print('skipping images')

               
                print('====================================************====================================')

                '''
                calls get_snapshots() 
                excludes snapshots that are not associated with any volume, image and instance
                deletes snapshots and calls csv_append() if run_delete_snapshots's input is yes
                '''                
                               
                snapCount = 0
                if run_delete_snapshots.lower() == 'yes':
                    print('Snapshots to act on, in  account: {}, region: {} '.format(account,region))
                    print('********************Snapshots For deletion*************************')
                    for snapshot in get_snapshots(ec2_client,exclusion_tags): 
                        snapCount +=1
                        if not volume_exists(snapshot['volume_id'],ec2_client) and not image_exists(snapshot['ami_id'],ec2_client) and not instance_exists(snapshot['instance_id'],ec2_client):
                            try: 
                                snapshot_Id = snapshot['id'] 
                                snapshot_Name = snapshot['name'] 
                                snapshot_Status = snapshot['status']
                                snapshot_Size = str(snapshot['size']) + 'gb' if 'size' in snapshot else 'no Size'
                                snapshot_Description = snapshot['description'] 

                                csv_append(enable_dry_run_mode,account,region,snapshot_Id, snapshot_Name,snapshot_Status, snapshot_Size, snapshot_Description)
                                response = ec2_client.delete_snapshot(SnapshotId=snapshot_Id, DryRun=enable_dry_run_mode) 
                                            
                                print('dryrun={} response = {} '.format(enable_dry_run_mode,response))                  
                                print(snapshot_Id, '****DELETED****')

                            except ClientError as e:  
                                if e.response['Error']['Code'] == 'DryRunOperation':
                                    print(snapshot_Id,snapshot['tags'], 'DeleteSnapshot operation: ****DRY RUN**** NO ACTION HAS BEEN TAKEN ', e)
                            except Exception as  e:
                                print('Exception Occurred: %s' % e) 
                    if snapCount == 0:            
                        print('No Snapshots were Found / Snapshots match the exclusion criteria')
                else:
                    print('skipping snapshots')
                
                print('====================================************====================================')

            else:
                print('No valid session') 

lambda_handler(
  {
    'action': 'run'
  },
  'context'
)