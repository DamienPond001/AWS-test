from troposphere import Template, Parameter, Ref
from troposphere.codebuild import (
    Artifacts,
    Environment,
    Source,
    Project,
    SourceAuth
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

#############################
#  Parameters
#############################

github_location = t.add_parameter(
    Parameter(
        'GithubLocation',
        Description='Github repo URL',
        Type='String',
        Default='https://github.com/DamienPond001/AWS-test.git',
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
        Default='main',
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
        Default='buildspec.yml',
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
        Default='aws/codebuild/amazonlinux2-x86_64-standard:3.0',
        MinLength='1',
        MaxLength='256',
        ConstraintDescription=('Build image is required.'),
    )
)
t.set_parameter_label(build_image, 'Build Image')

for p in [github_branch, github_location]:
    t.add_parameter_to_group(p, 'Git')

for p in [buildspec_path, build_image]:
    t.add_parameter_to_group(p, 'Codebuild')

#############################
#  S3
#############################

s3bucket = t.add_resource(
    Bucket(
        'VoyclibBucket',
        BucketName='voyclib-bucket',
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
        RoleName='voyclib-codebuild'
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
                    Resource=[ #add join here
                        (
                            'arn:aws:logs:eu-west-1:714249467706:log-group:'
                            '/aws/codebuild/voyclib-test-build:log-stream:*'
                        ),
                    ]
                ),
                Statement(
                    Effect=Allow,
                    Action=[
                        awacs.aws.Action('s3', 'PutObject'),
                        awacs.aws.Action('s3', 'PutObjectAcl')
                    ],
                    Resource=[
                        (
                            'arn:aws:s3:::voyclib-bucket/*'
                        )
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
            'Value': 'noice'
        },
        {
            'Name': 'BUCKET',
            'Value': 'voyclib-bucket'
        }
    ]
)

project = Project(
    'VoyclibProject',
    Artifacts=artifacts,
    Description='Voyclib build project',
    Name="voyclib-test-build",
    Source=source,
    SourceVersion=Ref(github_branch),
    Environment=environment,
    ServiceRole=Ref(codebuild_role)
)

t.add_resource(project)

with open('voyclib.json', 'w') as f:
    f.write(t.to_json())