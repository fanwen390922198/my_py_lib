from boto3.session import Session
from botocore.exceptions import ClientError, EndpointConnectionError

import _io
from botocore.config import Config


class S3Api:
    def __init__(self, access_key, secret_key, endpoint):
        try:
            config = Config(connect_timeout=10, read_timeout=10)
            session = Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)
            self.s3_client = session.client('s3', endpoint_url=endpoint, config=config, verify=False)  # ssl 配置也是在此
        except Exception as e:
            raise e

    def list_buckets(self):
        buckets = []
        try:
            response = self.s3_client.list_buckets()
            for bucket in response['Buckets']:
                buckets.append(bucket['Name'])
        except Exception as e:
            raise e

        return buckets

    def list_bucket_objects(self, bucket_name, marker=None):
        bucket_objs = []
        try:
            _marker = marker
            while True:
                list_kwargs = dict(MaxKeys=1000, Bucket=bucket_name)
                if _marker is not None:
                    list_kwargs['Marker'] = _marker
                response = self.s3_client.list_objects(**list_kwargs)

                if 'Contents' not in response:
                    return bucket_objs
                for key in response['Contents']:
                    bucket_objs.append([key['Key'],
                                        key['Size'],
                                        key['LastModified'].replace(tzinfo=None),
                                        key['ETag']])
                if not response.get('IsTruncated'):
                    break
                _marker = response.get('NextMarker')
        except Exception as e:
            raise e

        return bucket_objs

