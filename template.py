from troposphere import Template, Parameter, Condition
from troposphere.iam import Role
from troposphere.iam import PolicyType as IAMPolicy
from troposphere.events import Rule, Target
from troposphere.awslambda import Function, Code, Permission, Environment
from troposphere.logs import MetricFilter, MetricTransformation, LogGroup
from troposphere.s3 import Bucket, PublicRead
from troposphere import GetAtt, Join, Ref, Equals, Not, If

from awacs.aws import Action, Allow, Statement, Principal, Policy
from awacs.sts import AssumeRole

import json


t = Template()

t.add_version("2010-09-09")
t.add_description("Monitors a key in an api call for a value and prints to cloudwatch logs")

# Parameters

url = t.add_parameter(Parameter(
    "url",
    Description="Url for the api you are checking",
    Type="String",
    Default="https://members.heatsynclabs.org/space_api.json"
    ))
    
key = t.add_parameter(Parameter(
    "key",
    Description="Key youd like to get a value for.",
    Type="String",
    Default="open"
    ))
    
cloudwatch_metric = t.add_parameter(Parameter(
    "CloudwatchMetricName",
    Description="Fill this out if you want a true/false binary metric transformation to be created on your logs",
    Type="String",
    Default=""
    ))

# Conditions

metric_filter = t.add_condition(
    "MakeMetric", 
    Not(Equals(
        Ref(cloudwatch_metric),
        ""
        ))
    )

# Resources

code = [
    'import boto3, os',
    'from botocore.vendored import requests',
    '',
    'def handler(event, context):',
    '    try:',
    '        r = requests.get(event["url"])',
    '        print(r.json()[event["key"]])',
    '        if "bucket" in os.environ:',
    '            s3 = boto3.resource("s3")',
    '            cw = boto3.client("cloudwatch")',
    '            response = cw.get_metric_widget_image(MetricWidget=os.environ["json"])',
    '            object = s3.Object(os.environ["bucket"], "image.png")',
    '            object.put(Body=response["MetricWidgetImage"])',
    '    except Exception as e:',
    '        print(str(e))',
    '    return'
    ]

metric_image_json = {
    "width": 600,
    "height": 395,
    "metrics": [
        [ "HeatSyncDoors", "open", { "stat": "Average" } ]
    ],
    "period": 300,\
    "title": "HeatSyncDoors",
    "timezone": "+0000"
}
        


log_group = t.add_resource(LogGroup(
    "LogGroup",
    LogGroupName=Join("", ["/aws/lambda/", Ref("AWS::StackName")])
    ))
    
bucket = t.add_resource(Bucket(
    "S3Bucket",
    Condition=metric_filter,
    AccessControl=PublicRead
    ))

function = t.add_resource(Function(
    "Function",
    DependsOn=log_group,
    FunctionName=Ref("AWS::StackName"),
    Code=Code(
        ZipFile=Join("\n", code)
    ),
    Timeout="10",
    Handler="index.handler",
    Role=GetAtt("LambdaExecutionRole", "Arn"),
    Runtime="python3.7",
    Environment=Environment(Variables=
        If(metric_filter, 
            {
                "bucket": Ref(bucket),
                "json" : json.dumps(metric_image_json)
                
            },
            Ref("AWS::NoValue")
        )
    )
))

# Create the Event Target
target = Target(
    "Target",
    Arn=GetAtt('Function', 'Arn'),
    Id="WebsiteCheck",
    Input=Join('', [
        '{',
        '"url": "', Ref(url), '",'
        '"key": "', Ref(key), '"'
        '}'
        ])
)

# Create the Event Rule
rule = t.add_resource(Rule(
    "Rule",
    ScheduleExpression= "rate(1 minute)",
    Description="Checks api key value once per minute",
    State="ENABLED",
    Targets=[target]
))

# Create Permssion to Event to invoke Lambda
permission = t.add_resource(Permission(
    'Permission',
    Action='lambda:invokeFunction',
    Principal='events.amazonaws.com',
    FunctionName=Ref(function),
    SourceArn=GetAtt(rule, 'Arn')
))

#Permissions lambda runs with
lambda_role = t.add_resource(Role(
    "LambdaExecutionRole",
    AssumeRolePolicyDocument=Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Action=[AssumeRole],
                Principal=Principal("Service", ["lambda.amazonaws.com"])
            )
        ]
    ),
    ManagedPolicyArns = ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
))

t.add_resource(IAMPolicy(
    "Policy",
    PolicyName="CheckAPI",
    Roles=[Ref(lambda_role)],
    PolicyDocument=Policy(
        Statement=[
            Statement(
                Effect=Allow, 
                Action=[Action("s3", "PutObject")],
                Resource=[Join("", ["arn:aws:s3:::", Ref(bucket), "/*"])]
                ),
            Statement(
                Effect=Allow, 
                Action=[Action("cloudwatch", "GetMetricWidgetImage")],
                Resource=["*"]
                )
        ]
    )
))



true_filter = t.add_resource(MetricFilter(
    "MetricFilterTrue",
    DependsOn=log_group,
    Condition=metric_filter,
    FilterPattern="?True ?true ?TRUE",
    LogGroupName=Join("", ["/aws/lambda/", Ref(function)]),
    MetricTransformations=[
        MetricTransformation(
            MetricName=Ref(key),
            MetricNamespace=Ref(cloudwatch_metric),
            MetricValue= "1"
        )
    ]
))

false_filter = t.add_resource(MetricFilter(
    "MetricFilterFalse",
    DependsOn=log_group,
    Condition=metric_filter,
    FilterPattern="?False ?false ?FALSE",
    LogGroupName=Join("", ["/aws/lambda/", Ref("AWS::StackName")]),
    MetricTransformations=[
        MetricTransformation(
            MetricName=Ref(key),
            MetricNamespace=Ref(cloudwatch_metric),
            MetricValue= "0"
        )
    ]
))



yaml = (t.to_yaml())
print(yaml)

file = open("template.yaml","w") 
file.write(yaml) 
file.close() 