from troposphere import (
    Template,
    Parameter,
    Ref,
    Join,
    Sub,
    GetAtt
)
from troposphere.codebuild import (
    Artifacts,
    Environment,
    Source,
    Project,
    SourceAuth,
    ProjectTriggers, 
    WebhookFilter
)
from troposphere.iam import PolicyType, Role
from troposphere.s3 import Bucket, PublicRead, WebsiteConfiguration

import awacs
from awacs.aws import Allow, Principal, Statement, PolicyDocument
from awacs.sts import AssumeRole



t = Template()
t.set_description(
    'Voyclib CloudFormation template generation'
)

account_id = Ref('AWS::AccountId')
region = Ref('AWS::Region')

defaults = {
    'app_name': 'voyclib',
    'github_location': 'https://github.com/DamienPond001/AWS-test.git',
    'github_branch': 'main',
    'buildspec_path': 'buildspec.yml',
    'build_image': 'aws/codebuild/amazonlinux2-x86_64-standard:3.0',
    'build_name': 'voyclib_build',
    'bucket_name': 'voyclib'
}


#############################
#  Parameters
#############################

app_name = t.add_parameter(
    Parameter(
        'AppName',
        Description='Name of the application',
        Type='String',
        Default=defaults['app_name'],
        MinLength='1',
        MaxLength='128',
        ConstraintDescription=('Git URL is required')
    )
)
t.set_parameter_label(app_name, 'Application Name')

github_location = t.add_parameter(
    Parameter(
        'GithubLocation',
        Description='Github repo URL',
        Type='String',
        Default=defaults['github_location'],
        MinLength='1',
        MaxLength='128',
        ConstraintDescription=('Git URL is required')
    )
)
t.set_parameter_label(github_location, 'Github location')

github_branch = t.add_parameter(
    Parameter(
        'GithubBranch',
        Description='Github branch to track',
        Type='String',
        Default=defaults['github_branch'],
        MinLength='1',
        MaxLength='128',
        ConstraintDescription=('Git branch is required')
    )
)
t.set_parameter_label(github_branch, 'Github branch')

buildspec_path = t.add_parameter(
    Parameter(
        'Buildspec',
        Description='Path to buildspec.yml',
        Type='String',
        Default=defaults['buildspec_path'],
        MinLength='1',
        MaxLength='128',
        ConstraintDescription=('buildspec.yml must exist')
    )
)
t.set_parameter_label(buildspec_path, 'Buildspec Path')

build_image = t.add_parameter(
    Parameter(
        'BuildImage',
        Description='The Codebuild build image.',
        Type='String',
        Default=defaults['build_image'],
        MinLength='1',
        MaxLength='256',
        ConstraintDescription=('Build image is required.'),
    )
)
t.set_parameter_label(build_image, 'Build Image')

s3_bucket_name = t.add_parameter(
    Parameter(
        'S3BucketName',
        Description='Name of s3 voyclib bucket',
        Type='String',
        Default=defaults['bucket_name'],
        MinLength='1',
        MaxLength='128',
        ConstraintDescription=('Bucket name must be provided'),
    )
)
t.set_parameter_label(s3_bucket_name, 'S3 Bucket Name')

s3_bucket_secret = t.add_parameter(
    Parameter(
        'S3BucketSecret',
        Description='Name of s3 voyclib secret file',
        Type='String',
        MinLength='1',
        MaxLength='128',
        ConstraintDescription=('Bucket secret directoty must be provided'),
    )
)
t.set_parameter_label(s3_bucket_secret, 'S3 Bucket Secret')

for p in [github_branch, github_location]:
    t.add_parameter_to_group(p, 'Git')

for p in [buildspec_path, build_image]:
    t.add_parameter_to_group(p, 'Codebuild')

for p in [s3_bucket_name, s3_bucket_secret]:
    t.add_parameter_to_group(p, 'S3')

#############################
#  S3
#############################

s3bucket = t.add_resource(
    Bucket(
        'VoyclibBucket',
        BucketName=Ref('S3BucketName'),
        AccessControl=PublicRead,
        WebsiteConfiguration=WebsiteConfiguration(
            IndexDocument='index.html',
            ErrorDocument='error.html'
        )
    )
)

#############################
#  Codebuild - Roles and Policies
#############################

codebuild_role = t.add_resource(
    Role(
        'CodebuildRole',
        AssumeRolePolicyDocument=PolicyDocument(
            Statement=[
                Statement(
                    Principal=Principal('Service', ['codebuild.amazonaws.com']),
                    Effect=Allow,
                    Action=[AssumeRole]
                )
            ]
        ),
        RoleName=Sub('voyc-${AppName}')
    )
)

codebuild_policy = t.add_resource(
    PolicyType(
        'CodebuildPolicy',
        DependsOn=[
           'CodebuildRole',
           'VoyclibBucket',
        ],
        PolicyDocument=awacs.aws.Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[
                        awacs.aws.Action('logs', 'CreateLogStream'),
                        awacs.aws.Action('logs', 'CreateLogGroup'),
                        awacs.aws.Action('logs', 'PutLogEvents')
                    ],
                    Resource=[
                        Join(
                            ':',
                            [
                                'arn:aws:logs',
                                region,
                                account_id,
                                'log_group',
                                Sub(
                                    '/aws/codebuild/voyc-${AppName}-build'
                                ),
                                'log-stream',
                                '*'
                            ]
                        )
                    ]
                ),
                Statement(
                    Effect=Allow,
                    Action=[
                        awacs.aws.Action('s3', 'PutObject'),
                        awacs.aws.Action('s3', 'PutObjectAcl')
                    ],
                    Resource=[
                        Join("", [GetAtt('VoyclibBucket', 'Arn'), '/*'])
                    ]
                )
            ]
        ),
        PolicyName='CodebuildVoyclibPolicy',
        Roles=[
            Ref(codebuild_role)
        ]
    )
)

#############################
#  Codebuild
#############################

artifacts = Artifacts(Type='NO_ARTIFACTS')

source = Source(
    Auth=SourceAuth(
        Type='OAUTH'
    ),
    Location=Ref(github_location),
    BuildSpec=Ref(buildspec_path),
    GitCloneDepth=1,
    ReportBuildStatus=True,
    Type='GITHUB'
)

environment = Environment(
    ComputeType='BUILD_GENERAL1_SMALL',
    Image=Ref(build_image),
    Type='LINUX_CONTAINER',
    EnvironmentVariables=[
        {
            'Name': 'SECRET',
            'Value': Ref(s3_bucket_secret)
        },
        {
            'Name': 'BUCKET',
            'Value': Ref(s3_bucket_name)
        }
    ]
)

project = Project(
    'VoyclibProject',
    Artifacts=artifacts,
    Description='Voyclib build project',
    Name=Sub("voyc-${AppName}-build"),
    Source=source,
    SourceVersion=Ref(github_branch),
    Environment=environment,
    ServiceRole=Ref(codebuild_role),
    Triggers=ProjectTriggers(
        Webhook=True,
        FilterGroups=[
            [
                WebhookFilter(
                    Type='EVENT',
                    Pattern='PUSH,PULL_REQUEST_MERGED'
                ),
                WebhookFilter(
                    Type='HEAD_REF',
                    Pattern=Sub('refs/heads/${GithubBranch}')
                )
            ]
        ]
    )
)

t.add_resource(project)

with open('voyclib.json', 'w') as f:
    f.write(t.to_json())