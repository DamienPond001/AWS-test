from troposphere import Template
from troposphere.s3 import Bucket, PublicRead, WebsiteConfiguration


t = Template()

t.set_description(
    "S3 test troposphere template"
)

s3bucket = t.add_resource(
    Bucket(
        'TestBucket',
        BucketName='test-bucket'
        AccessControl=PublicRead,
        WebsiteConfiguration=WebsiteConfiguration(
            IndexDocument="index.html",
            ErrorDocument="error.html"
        )
    )
)

print(t.to_json())