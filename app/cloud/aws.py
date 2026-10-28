"""AWS adapter (boto3). Uses the standard credential chain; never stores keys."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.cloud.base import CloudAdapter, mask_account_ids, safe_error
from app.cloud.models import (
    CloudInstance,
    CloudMetricPoint,
    CloudNetwork,
    CloudOverview,
    CloudVolume,
)
from app.config import Settings
from app.models.schemas import Provider

_MAX_ITEMS = 50
_MAX_METRIC_INSTANCES = 10


def _tag(tags: list[dict[str, str]] | None, key: str = "Name") -> str | None:
    for tag in tags or []:
        if tag.get("Key") == key:
            return tag.get("Value")
    return None


class AwsAdapter(CloudAdapter):
    """EC2, EBS, CloudWatch, VPC and identity information for one AWS account/region."""

    provider = Provider.AWS

    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Any] | None = None,
        cache_ttl_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        ttl = settings.cloud_cache_ttl_seconds if cache_ttl_seconds is None else cache_ttl_seconds
        super().__init__(ttl, clock)
        self._settings = settings
        self._session_factory = session_factory or self._default_session

    def _default_session(self) -> Any:
        import boto3

        # Fail fast instead of waiting on the EC2 metadata service when running on a laptop.
        os.environ.setdefault("AWS_METADATA_SERVICE_TIMEOUT", "1")
        os.environ.setdefault("AWS_METADATA_SERVICE_NUM_ATTEMPTS", "1")
        return boto3.Session(
            profile_name=self._settings.aws_profile, region_name=self._settings.aws_region
        )

    def _collect(self) -> CloudOverview:
        if not self._settings.aws_enabled:
            return self._not_configured("AWS integration is disabled (AWS_ENABLED=false)")
        try:
            session = self._session_factory()
            credentials = session.get_credentials()
        except Exception as exc:  # noqa: BLE001 - e.g. ProfileNotFound
            return self._not_configured("AWS credentials are not configured", safe_error(exc))
        if credentials is None:
            return self._not_configured("AWS credentials are not configured")

        config = Config(
            connect_timeout=3,
            read_timeout=8,
            retries={"max_attempts": 2, "mode": "standard"},
            user_agent_extra="cloudops360",
        )
        region = getattr(session, "region_name", None) or self._settings.aws_region
        try:
            identity = session.client("sts", config=config).get_caller_identity()
        except (ClientError, BotoCoreError) as exc:
            return self._not_configured("AWS credentials could not be verified", safe_error(exc))

        warnings: list[str] = []
        ec2 = session.client("ec2", config=config)
        cloudwatch = session.client("cloudwatch", config=config)
        iam = session.client("iam", config=config)

        instances = self._section("ec2", lambda: self._instances(ec2, region), [], warnings)
        volumes = self._section("ebs", lambda: self._volumes(ec2, region), [], warnings)
        networks = self._section("vpc", lambda: self._networks(ec2, region), [], warnings)
        metrics = self._section(
            "cloudwatch", lambda: self._cpu_metrics(cloudwatch, instances), [], warnings
        )
        aliases = self._section("iam", lambda: self._account_aliases(iam), [], warnings)

        return CloudOverview(
            provider=self.provider,
            configured=True,
            message="AWS credentials verified",
            region=region,
            identity={
                "account": mask_account_ids(identity.get("Account")),
                "arn": mask_account_ids(identity.get("Arn")),
                "user_id": identity.get("UserId"),
                "account_aliases": aliases,
            },
            instances=instances,
            volumes=volumes,
            networks=networks,
            metrics=metrics,
            warnings=warnings,
        )

    # ------------------------------------------------------------------ sections

    @staticmethod
    def _instances(ec2: Any, region: str) -> list[CloudInstance]:
        response = ec2.describe_instances(MaxResults=_MAX_ITEMS)
        found: list[CloudInstance] = []
        for reservation in response.get("Reservations", []):
            for item in reservation.get("Instances", []):
                found.append(
                    CloudInstance(
                        provider=Provider.AWS,
                        id=item["InstanceId"],
                        name=_tag(item.get("Tags")),
                        state=item.get("State", {}).get("Name", "unknown"),
                        instance_type=item.get("InstanceType"),
                        region=region,
                        zone=item.get("Placement", {}).get("AvailabilityZone"),
                        private_ip=item.get("PrivateIpAddress"),
                        public_ip=item.get("PublicIpAddress"),
                        launch_time=item.get("LaunchTime"),
                    )
                )
        return found

    @staticmethod
    def _volumes(ec2: Any, region: str) -> list[CloudVolume]:
        response = ec2.describe_volumes(MaxResults=_MAX_ITEMS)
        found: list[CloudVolume] = []
        for item in response.get("Volumes", []):
            attachments = item.get("Attachments") or [{}]
            found.append(
                CloudVolume(
                    provider=Provider.AWS,
                    id=item["VolumeId"],
                    name=_tag(item.get("Tags")),
                    size_gb=item.get("Size"),
                    state=item.get("State"),
                    volume_type=item.get("VolumeType"),
                    encrypted=item.get("Encrypted"),
                    attached_to=attachments[0].get("InstanceId"),
                    region=region,
                )
            )
        return found

    @staticmethod
    def _networks(ec2: Any, region: str) -> list[CloudNetwork]:
        found: list[CloudNetwork] = []
        for vpc in ec2.describe_vpcs().get("Vpcs", []):
            found.append(
                CloudNetwork(
                    provider=Provider.AWS,
                    id=vpc["VpcId"],
                    name=_tag(vpc.get("Tags")),
                    kind="vpc",
                    cidrs=[vpc["CidrBlock"]] if vpc.get("CidrBlock") else [],
                    region=region,
                    details={"is_default": vpc.get("IsDefault", False), "state": vpc.get("State")},
                )
            )
        for subnet in ec2.describe_subnets().get("Subnets", []):
            found.append(
                CloudNetwork(
                    provider=Provider.AWS,
                    id=subnet["SubnetId"],
                    name=_tag(subnet.get("Tags")),
                    kind="subnet",
                    cidrs=[subnet["CidrBlock"]] if subnet.get("CidrBlock") else [],
                    region=region,
                    details={
                        "vpc_id": subnet.get("VpcId"),
                        "zone": subnet.get("AvailabilityZone"),
                        "available_ips": subnet.get("AvailableIpAddressCount"),
                    },
                )
            )
        return found[: _MAX_ITEMS * 2]

    @staticmethod
    def _cpu_metrics(cloudwatch: Any, instances: list[CloudInstance]) -> list[CloudMetricPoint]:
        running = [i for i in instances if i.state == "running"][:_MAX_METRIC_INSTANCES]
        if not running:
            return []
        end = datetime.now(UTC)
        queries = [
            {
                "Id": f"cpu{index}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/EC2",
                        "MetricName": "CPUUtilization",
                        "Dimensions": [{"Name": "InstanceId", "Value": instance.id}],
                    },
                    "Period": 300,
                    "Stat": "Average",
                },
                "ReturnData": True,
            }
            for index, instance in enumerate(running)
        ]
        response = cloudwatch.get_metric_data(
            MetricDataQueries=queries,
            StartTime=end - timedelta(minutes=30),
            EndTime=end,
            ScanBy="TimestampDescending",
        )
        points: list[CloudMetricPoint] = []
        for result in response.get("MetricDataResults", []):
            values = result.get("Values") or []
            if not values:
                continue
            index = int(result["Id"].removeprefix("cpu"))
            timestamps = result.get("Timestamps") or [None]
            points.append(
                CloudMetricPoint(
                    provider=Provider.AWS,
                    resource_id=running[index].id,
                    metric="CPUUtilization",
                    value=float(values[0]),
                    unit="Percent",
                    timestamp=timestamps[0],
                )
            )
        return points

    @staticmethod
    def _account_aliases(iam: Any) -> list[str]:
        return list(iam.list_account_aliases().get("AccountAliases", []))
