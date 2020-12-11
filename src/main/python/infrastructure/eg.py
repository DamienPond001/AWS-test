import awacs
from awacs.aws import Allow, Principal, Statement
from awacs.sts import AssumeRole
from troposphere import GetAtt, Join, Parameter, Ref, Sub, Tags, Template
from troposphere.cloudfront import (
    CloudFrontOriginAccessIdentity,
    CloudFrontOriginAccessIdentityConfig,
    DefaultCacheBehavior,
    Distribution,
    DistributionConfig,
    ForwardedValues,
    Origin,
    S3OriginConfig,
    ViewerCertificate,
)
from troposphere.codebuild import (
    Artifacts,
    Environment,
    Project,
    ProjectTriggers,
    Source,
    SourceAuth,
    WebhookFilter,
)
from troposphere.iam import PolicyType, Role
from troposphere.s3 import (
    Bucket,
    BucketEncryption,
    BucketPolicy,
    ServerSideEncryptionByDefault,
    ServerSideEncryptionRule,
    VersioningConfiguration,
)


t = Template()
t.set_version()
t.set_description(
    'Generate static S3 hosting for Voyc docs as well as the Codebuild pipeline'
    ' for building static docs.'
)

ref_region = Ref('AWS::Region')
ref_account_id = Ref('AWS::AccountId')
ref_stack_name = Ref('AWS::StackName')

###########################################
#                 Params
###########################################

cloudfront_cnames = t.add_parameter(
    Parameter(
        'CloudfrontCnames',
        Description=(
            'Comma delimited list of hostnames that will serve as Cloudfront CNAMEs.'
        ),
        Type='CommaDelimitedList',
        Default='docs.voyc.ai',
    )
)
t.set_parameter_label(cloudfront_cnames, 'Cloudfront CNAMEs')

acl_arn = t.add_parameter(
    Parameter(
        'AclArn',
        Description='Arn for WAFv2 ACL which allows VPN IP access.',
        Type='String',
        Default=(
            'arn:aws:wafv2:us-east-1:585487584801:global/webacl/voyc-docs-acl/'
            '70c9cf49-0771-4a10-8491-fe6d5d401e45'
        ),
        MinLength='51',
        MaxLength='256',
        ConstraintDescription=('WAF2 ACL Arn between 51 and 256 characters.'),
    )
)
t.set_parameter_label(acl_arn, 'ACL Arn')

acm_arn = t.add_parameter(
    Parameter(
        'AcmCertArm',
        Description='Arn for the ACM certificate.',
        Type='String',
        Default=(
            'arn:aws:acm:us-east-1:585487584801:certificate/'
            'fb84241d-1bea-4adc-934a-cd37dd54e1ba'
        ),
        MinLength='51',
        MaxLength='256',
        ConstraintDescription=('ACM certificate Arn between 51 and 256 characters.'),
    )
)
t.set_parameter_label(acl_arn, 'Certificate Arn')

git_location = t.add_parameter(
    Parameter(
        'GitLocation',
        Description='The Github HTTPS clone URL.',
        Type='String',
        Default='https://github.com/voyc-ai/voyc.git',
        MinLength='1',
        MaxLength='128',
        ConstraintDescription=('Git clone URL is required.'),
    )
)
t.set_parameter_label(git_location, 'Github Location')

branch_name = t.add_parameter(
    Parameter(
        'BranchName',
        Description='The Git branch name to use. Eg: develop',
        Type='String',
        Default='develop',
        MinLength='1',
        MaxLength='128',
        ConstraintDescription=('Branch name is required.'),
    )
)
t.set_parameter_label(branch_name, 'Branch Name')

buildspec_location_param = t.add_parameter(
    Parameter(
        'DocsBuildspecPath',
        Description='The documentation buildspec.yml file path.',
        Type='String',
        Default='codebuild/buildspec_docs.yml',
        MinLength='1',
        MaxLength='128',
        ConstraintDescription='Buildspec path smaller than 128 characters is required.',
    )
)
t.set_parameter_label(buildspec_location_param, 'Buildspec Path')

build_image = t.add_parameter(
    Parameter(
        'BuildImage',
        Description='The Codebuild build image.',
        Type='String',
        Default='aws/codebuild/amazonlinux2-x86_64-standard:3.0',
        MinLength='1',
        MaxLength='256',
        ConstraintDescription=('Build image is required.'),
    )
)
t.set_parameter_label(build_image, 'Build Image')

for cf_param in [cloudfront_cnames, acl_arn, acm_arn]:
    t.add_parameter_to_group(cf_param, 'Cloudfront')

for git_param in [git_location, branch_name]:
    t.add_parameter_to_group(git_param, 'Git')

for codebuild_param in [buildspec_location_param, build_image]:
    t.add_parameter_to_group(codebuild_param, 'Codebuild')

###########################################
#                  OAI
###########################################

cloudfront_oai = t.add_resource(
    CloudFrontOriginAccessIdentity(
        'CloudfrontOAI',
        CloudFrontOriginAccessIdentityConfig=CloudFrontOriginAccessIdentityConfig(
            Comment='OAI to private Voyc docs S3 bucket.',
        ),
    )
)

###########################################
#                  S3
###########################################

s3_storage = t.add_resource(
    Bucket(
        'S3StorageBucket',
        BucketName=Sub('voyc-docs'),
        BucketEncryption=BucketEncryption(
            ServerSideEncryptionConfiguration=[
                ServerSideEncryptionRule(
                    ServerSideEncryptionByDefault=ServerSideEncryptionByDefault(
                        SSEAlgorithm='AES256'
                    )
                )
            ]
        ),
        VersioningConfiguration=VersioningConfiguration(Status='Enabled'),
        Tags=Tags(
            Name=Sub('voyc-${AWS::StackName}'),
        ),
    )
)

codebuild_role = t.add_resource(
    Role(
        'CodebuildRole',
        AssumeRolePolicyDocument=awacs.aws.PolicyDocument(
            Statement=[
                Statement(
                    Principal=Principal('Service', ['codebuild.amazonaws.com']),
                    Effect=Allow,
                    Action=[AssumeRole],
                )
            ]
        ),
        RoleName=Sub('voyc-docs-codebuild'),
    )
)

cloudfront_policy = t.add_resource(
    BucketPolicy(
        'CloudfrontBucketPolicy',
        DependsOn=[
            'CloudfrontOAI',
            'S3StorageBucket',
            'DocsProject',
        ],
        Bucket=Ref(s3_storage),
        PolicyDocument=awacs.aws.Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[
                        awacs.aws.Action('s3', 'GetObject'),
                    ],
                    Resource=[
                        Join('', [GetAtt('S3StorageBucket', 'Arn'), '/*']),
                    ],
                    Principal=Principal(
                        'AWS',
                        Join(
                            '',
                            [
                                (
                                    'arn:aws:iam::cloudfront:user/'
                                    'CloudFront Origin Access Identity '
                                ),
                                Ref(cloudfront_oai),
                            ],
                        ),
                    ),
                ),
                Statement(
                    Effect=Allow,
                    Action=[
                        awacs.aws.Action('s3', 'AbortMultipartUpload'),
                        awacs.aws.Action('s3', 'ListMultipartUploadParts'),
                        awacs.aws.Action('s3', '*Object'),
                        awacs.aws.Action('s3', 'GetObjectAcl'),
                        awacs.aws.Action('s3', 'PutObjectAcl'),
                    ],
                    Resource=[
                        Join('', [GetAtt('S3StorageBucket', 'Arn'), '/*']),
                    ],
                    Principal=Principal(
                        'AWS',
                        GetAtt(codebuild_role, 'Arn'),
                    ),
                ),
                Statement(
                    Effect=Allow,
                    Action=[
                        awacs.aws.Action('s3', 'ListBucket'),
                    ],
                    Resource=[
                        GetAtt('S3StorageBucket', 'Arn'),
                    ],
                    Principal=Principal(
                        'AWS',
                        GetAtt(codebuild_role, 'Arn'),
                    ),
                ),
            ],
        ),
    ),
)

codebuild_policy = t.add_resource(
    PolicyType(
        'CodebuildAccessPolicy',
        DependsOn=[
            'DocsDistribution',
            'DocsProject',
        ],
        PolicyDocument=awacs.aws.Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[
                        awacs.aws.Action('logs', 'CreateLogStream'),
                        awacs.aws.Action('logs', 'CreateLogGroup'),
                        awacs.aws.Action('logs', 'PutLogEvents'),
                        awacs.aws.Action('logs', 'DescribeLogStreams'),
                    ],
                    Resource=[
                        (
                            'arn:aws:logs:eu-west-1:585487584801:log-group:'
                            '/aws/codebuild/voyc-docs:log-stream:'
                            '*'
                        ),
                    ],
                ),
                Statement(
                    Effect=Allow,
                    Action=[
                        awacs.aws.Action('cloudfront', 'CreateInvalidation'),
                    ],
                    Resource=[
                        Join(
                            '',
                            [
                                'arn:aws:cloudfront::585487584801:distribution/',
                                Ref('DocsDistribution'),
                            ],
                        ),
                    ],
                ),
            ]
        ),
        PolicyName=Sub('voyc-docs-S3'),
        Roles=[
            Ref(codebuild_role),
        ],
    )
)

###########################################
#               Cloudfront
###########################################

cloudfront = t.add_resource(
    Distribution(
        'DocsDistribution',
        DistributionConfig=DistributionConfig(
            Comment='Voyc static docs.',
            DefaultRootObject='index.html',
            DefaultCacheBehavior=DefaultCacheBehavior(
                TargetOriginId='S3Origin',
                ForwardedValues=ForwardedValues(
                    QueryString=False,
                ),
                ViewerProtocolPolicy='redirect-to-https',
            ),
            PriceClass='PriceClass_100',
            Origins=[
                Origin(
                    DomainName=GetAtt(s3_storage, 'DomainName'),
                    Id='S3Origin',
                    S3OriginConfig=S3OriginConfig(
                        OriginAccessIdentity=Join(
                            '',
                            [
                                'origin-access-identity/cloudfront/',
                                Ref(cloudfront_oai),
                            ],
                        ),
                    ),
                    OriginPath='/docs',
                ),
            ],
            Enabled=True,
            WebACLId=Ref(acl_arn),
            Aliases=Ref(cloudfront_cnames),
            ViewerCertificate=ViewerCertificate(
                AcmCertificateArn=Ref(acm_arn),
                SslSupportMethod='sni-only',
            ),
        ),
    )
)

###########################################
#               Codebuild
###########################################

build_source = Source(
    Auth=SourceAuth(
        Type='OAUTH',
    ),
    Location=Ref(git_location),
    BuildSpec=Ref(buildspec_location_param),
    GitCloneDepth=1,
    ReportBuildStatus=True,
    Type='GITHUB',
)

environment = Environment(
    ComputeType='BUILD_GENERAL1_SMALL',
    Image=Ref(build_image),
    Type='LINUX_CONTAINER',
    EnvironmentVariables=[
        {
            'Name': 'AWS_DEFAULT_REGION',
            'Value': ref_region,
        },
        {
            'Name': 'AWS_ACCOUNT_ID',
            'Value': ref_account_id,
        },
        {
            'Name': 'DEPLOY_BUCKET',
            'Value': Ref(s3_storage),
        },
        {
            'Name': 'DISTRIBUTION_ID',
            'Value': Ref(cloudfront),
        },
    ],
)

codebuild_project = Project(
    'DocsProject',
    Artifacts=Artifacts(Type='NO_ARTIFACTS'),
    BadgeEnabled=True,
    Description='Voyc documentation build project.',
    Environment=environment,
    Name='voyc-docs',
    ServiceRole=Ref(codebuild_role),
    Source=build_source,
    SourceVersion=Ref(branch_name),
    Triggers=ProjectTriggers(
        Webhook=True,
        FilterGroups=[
            [
                WebhookFilter(
                    Type='EVENT',
                    Pattern='PUSH',
                ),
                WebhookFilter(
                    Type='FILE_PATH',
                    Pattern='^docs/.*',
                ),
                WebhookFilter(
                    Type='HEAD_REF',
                    Pattern=Sub('refs/heads/${BranchName}'),
                ),
            ],
        ],
    ),
)
t.add_resource(codebuild_project)

###########################################
#                 Output
###########################################

with open('docs_ci.json', 'w') as f:
    f.write(t.to_json())
