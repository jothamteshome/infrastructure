import os
import aws_cdk as cdk
from StaticSiteStack import StaticSiteStack

app = cdk.App()

repo_name: str = app.node.try_get_context("repo_name")
hosted_zone_name: str = os.getenv("HOSTED_ZONE_NAME")
hosted_zone_id: str = os.getenv("HOSTED_ZONE_ID")
domain_name: str = os.getenv("DOMAIN_NAME")


StaticSiteStack(
    app, 
    f"{repo_name}-static-site",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), 
        region=os.getenv("CDK_DEFAULT_REGION")
        ),
    repo_name=repo_name,
    hosted_zone_name=hosted_zone_name,
    hosted_zone_id=hosted_zone_id,
    domain_name=domain_name
)

app.synth()