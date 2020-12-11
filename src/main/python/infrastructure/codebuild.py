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
        Default='https://github.com/voyc-ai/voyc.git',
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
        Default="feature/voyclib",
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
        Default='codebuild/buildspec_voyclib.yml',
        MinLength='1',
        MaxLength='128',
        ConstraintDescription='Buildspec path smaller than 128 characters is required.',
    )
)
t.set_parameter_label(buildspec_par, 'Buildspec Path')

# Roles

codebuild_role = t.add_resource(
    Role(
        'CodebuildRole',
        AssumeRolePolicyDocumnet=PolicyDocument(
            Statement=[
                Statement(
                    Principal=Principal('Service', ['codebuild.amazonaws.com']),
                    Effect=Allow,
                    Action=[AssumeRole]
                )
            ]
        )
        RoleName='voyclib-codebuild'
    )
)

# Policies

codebuild_policy = t.add_resource(
    PolicyType(
        'CodebuildPolicy',
        PolicyDocument=awacs.aws.Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[
                        awacs.aws.Action('logs', 'CreateLogStream'),
                        awacs.aws.Action('logs', 'CreateLogGroup')
                    ]
                )
            ]
        )
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
    Image='aws/codebuild/standard:4.0',
    Type='LINUX_CONTAINER',
    EnvironmentVariables=[
        {
            'Name': 'SECRET',
            'Value': 'noice'
        },
        {
            'Name': 'BUCKET',
            'Value': 'voyclib'
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
)

t.add_resource(project)

print(t.to_json())