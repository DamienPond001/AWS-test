from troposphere import Template, Parameter, Ref
from troposphere.codebuild import (
    Artifacts,
    Environment,
    Source,
    Project,
    SourceAuth
)
from troposphere.iam import PolicyType, Role

import awacs
from awacs.aws import Allow, Principal, Statement, PolicyDocument
from awacs.sts import AssumeRole

t = Template()

# Parameters

github_par = t.add_parameter(
    Parameter(
        'GitLocation',
        Description='Github clone URL',
        Type="String",
        Default='https://github.com/DamienPond001/AWS-test.git',
        MinLength='1',
        MaxLength='128',
        ConstraintDescription=('Git clone URL is required')
    )
)
t.set_parameter_label(github_par, 'Github location')

branch = t.add_parameter(
    Parameter(
        'BranchName',
        Description="Branch to use",
        Type="String",
        Default="main",
        MinLength='1',
        MaxLength='128',
        ConstraintDescription=('Branch name is required.'),
    )
)
t.set_parameter_label(branch, 'Github Branch')

buildspec_par = t.add_parameter(
    Parameter(
        'BuildSpec',
        Description='Path to buildspec yaml',
        Type='String',
        Default='buildspec.yml',
        MinLength='1',
        MaxLength='128',
        ConstraintDescription='Buildspec path smaller than 128 characters is required.',
    )
)
t.set_parameter_label(buildspec_par, 'Buildspec Path')

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

for git_param in [github_par, branch]:
    t.add_parameter_to_group(git_param, 'Git')

for codebuild_param in [buildspec_par, build_image]:
    t.add_parameter_to_group(codebuild_param, 'Codebuild')

# Roles

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

# Policies

codebuild_policy = t.add_resource(
    PolicyType(
        'CodebuildPolicy',
        DependsOn=[
            'VoyclibProject'
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
                        (
                            'arn:aws:logs:eu-west-1:714249467706:log-group:'
                            '/aws/codebuild/voyclib-test-build:log-stream:*'
                        ),
                    ]
                )
            ]
        ),
        PolicyName='TemplateTest',
        Roles=[
            Ref(codebuild_role)
        ]
    )
)



artifacts = Artifacts(Type='NO_ARTIFACTS')

source = Source(
    Auth=SourceAuth(
        Type='OAUTH'
    ),
    Location=Ref(github_par),
    BuildSpec=Ref(buildspec_par),
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
    SourceVersion=Ref(branch),
    Environment=environment,
    ServiceRole=Ref(codebuild_role)
)

t.add_resource(project)

with open('voyclib_ci.json', 'w') as f:
    f.write(t.to_json())