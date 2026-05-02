from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_iam as iam,
    RemovalPolicy,
    Duration,
    CfnOutput
)

from constructs import Construct
from typing import Optional

class StaticSiteStack(Stack):
    def __init__(
            self, 
            scope: Construct, 
            construct_id: str, 
            repo_name: str, 
            hosted_zone_name: str, 
            hosted_zone_id: str, 
            domain_name: Optional[str]=None,
            **kwargs
            ) -> None:
        
        super().__init__(scope, construct_id, **kwargs)

        constructed_domain_name = f"{repo_name}.{hosted_zone_name}" if not domain_name else domain_name
        formatted_domain_id = constructed_domain_name.replace('.', '-')
        record_name = constructed_domain_name if constructed_domain_name != hosted_zone_name else "@"

        # Hosted Zone lookup
        hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
            self, 
            "HostedZone",
            hosted_zone_id=hosted_zone_id,
            zone_name=hosted_zone_name
        )

        # S3 Bucket for static site
        bucket = s3.Bucket(
            self,
            "SiteBucket",
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )


        # Cloudfront S3 Origin Access Control
        oac = cloudfront.S3OriginAccessControl(
            self, 
            "OAC",
            description=f"OAC for {constructed_domain_name} site",
            signing=cloudfront.Signing(
                protocol=cloudfront.SigningProtocol.SIGV4,
                behavior=cloudfront.SigningBehavior.ALWAYS
            )
        )


        # ACM certificate in us-east-1 (required for CloudFront)
        cert = acm.Certificate(
            self,
            "SiteCert",
            domain_name=constructed_domain_name,
            validation=acm.CertificateValidation.from_dns(hosted_zone)
        )


        # Create CloudFront distribution
        distribution = cloudfront.Distribution(
            self,
            "SiteDistribution",
            default_root_object="index.html",
            domain_names=[constructed_domain_name],
            certificate=cert,
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin(bucket, origin_access_control_id=oac.origin_access_control_id),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED
            ),
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(1)
                )
            ]
        )

        bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[bucket.arn_for_objects('*')],
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                conditions={
                    "StringEquals" : {
                        "AWS:SourceARN": f"arn:aws:cloudfront::{self.account}:distribution/{distribution.distribution_id}"
                    }
                }
            )
        )

        # Route53 record for subdomain
        route53.ARecord(
            self,
            "AliasRecord",
            zone=hosted_zone,
            record_name=record_name,
            target=route53.RecordTarget.from_alias(targets.CloudFrontTarget(distribution))
        )


        CfnOutput(self, "BucketNameOutput", value=bucket.bucket_name, export_name=f"{formatted_domain_id}-bucket-name")
        CfnOutput(self, "CloudFrontIdOutput", value=distribution.distribution_id, export_name=f"{formatted_domain_id}-cloudfront-id")


