"""AWS / Azure adapters without real accounts: graceful degradation and parsing."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from app.cloud.aws import AwsAdapter
from app.cloud.azure import AzureAdapter, AzureClients
from app.cloud.base import mask_account_ids
from app.container import build_container
from app.main import create_app
from tests.helpers import StaticCollector, build_snapshot, make_settings, sample_value

# ---------------------------------------------------------------------- AWS fakes


class FakeAwsSession:
    region_name = "eu-west-1"

    def __init__(self, credentials=object(), clients=None):
        self._credentials = credentials
        self._clients = clients or {}

    def get_credentials(self):
        return self._credentials

    def client(self, name, **_kwargs):
        return self._clients[name]


class FakeSts:
    def __init__(self, error=None):
        self.error = error

    def get_caller_identity(self):
        if self.error:
            raise self.error
        return {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/demo", "UserId": "AIDATEST"}


class FakeEc2:
    def describe_instances(self, **_):
        return {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0abc",
                            "State": {"Name": "running"},
                            "InstanceType": "t3.micro",
                            "Placement": {"AvailabilityZone": "eu-west-1a"},
                            "PrivateIpAddress": "10.0.0.5",
                            "Tags": [{"Key": "Name", "Value": "web-1"}],
                            "LaunchTime": datetime(2026, 1, 1, tzinfo=UTC),
                        },
                        {"InstanceId": "i-0def", "State": {"Name": "stopped"}},
                    ]
                }
            ]
        }

    def describe_volumes(self, **_):
        return {
            "Volumes": [
                {
                    "VolumeId": "vol-1",
                    "Size": 8,
                    "State": "in-use",
                    "VolumeType": "gp3",
                    "Encrypted": True,
                    "Attachments": [{"InstanceId": "i-0abc"}],
                }
            ]
        }

    def describe_vpcs(self):
        return {"Vpcs": [{"VpcId": "vpc-1", "CidrBlock": "10.0.0.0/16", "IsDefault": False}]}

    def describe_subnets(self):
        return {"Subnets": [{"SubnetId": "subnet-1", "CidrBlock": "10.0.1.0/24", "VpcId": "vpc-1"}]}


class FakeCloudWatch:
    def get_metric_data(self, **_):
        return {"MetricDataResults": [{"Id": "cpu0", "Values": [12.5, 10.0], "Timestamps": [datetime(2026, 1, 1, tzinfo=UTC)]}]}


class FakeIam:
    def list_account_aliases(self):
        return {"AccountAliases": ["demo-alias"]}


def aws_clients(sts=None, ec2=None):
    return {
        "sts": sts or FakeSts(),
        "ec2": ec2 or FakeEc2(),
        "cloudwatch": FakeCloudWatch(),
        "iam": FakeIam(),
    }


def aws_settings(tmp_path, **kw):
    return make_settings(tmp_path, aws_enabled=True, **kw)


# ---------------------------------------------------------------------- AWS tests


def test_aws_without_credentials_is_not_configured(tmp_path):
    adapter = AwsAdapter(aws_settings(tmp_path), session_factory=lambda: FakeAwsSession(credentials=None))
    overview = adapter.get_overview()
    assert overview.configured is False
    assert overview.message == "AWS credentials are not configured"
    assert overview.instances == []


def test_aws_session_failure_does_not_crash(tmp_path):
    def broken():
        raise RuntimeError("profile not found")

    overview = AwsAdapter(aws_settings(tmp_path), session_factory=broken).get_overview()
    assert overview.configured is False
    assert overview.message == "AWS credentials are not configured"
    assert overview.detail == "RuntimeError"


def test_aws_disabled_flag_skips_everything(tmp_path):
    def must_not_run():
        raise AssertionError("session must not be created when disabled")

    adapter = AwsAdapter(make_settings(tmp_path, aws_enabled=False), session_factory=must_not_run)
    assert "disabled" in adapter.get_overview().message


def test_aws_invalid_credentials_report_error_code_only(tmp_path):
    error = ClientError({"Error": {"Code": "InvalidClientTokenId", "Message": "AKIAABCDEFGHIJKLMNOP is bad"}}, "GetCallerIdentity")
    session = FakeAwsSession(clients=aws_clients(sts=FakeSts(error)))
    overview = AwsAdapter(aws_settings(tmp_path), session_factory=lambda: session).get_overview()
    assert overview.configured is False
    assert overview.detail == "InvalidClientTokenId"
    assert "AKIA" not in overview.model_dump_json()


def test_aws_configured_collects_resources(tmp_path):
    session = FakeAwsSession(clients=aws_clients())
    overview = AwsAdapter(aws_settings(tmp_path), session_factory=lambda: session).get_overview()
    assert overview.configured is True
    assert overview.region == "eu-west-1"
    assert overview.identity["account"] == "********9012"
    assert "123456789012" not in overview.model_dump_json()
    assert [(i.id, i.state, i.name) for i in overview.instances] == [
        ("i-0abc", "running", "web-1"),
        ("i-0def", "stopped", None),
    ]
    assert overview.volumes[0].attached_to == "i-0abc"
    assert {n.kind for n in overview.networks} == {"vpc", "subnet"}
    assert overview.metrics[0].value == 12.5 and overview.metrics[0].resource_id == "i-0abc"
    assert overview.identity["account_aliases"] == ["demo-alias"]
    assert overview.warnings == []


def test_aws_partial_permissions_produce_warnings_not_failures(tmp_path):
    class DeniedEc2(FakeEc2):
        def describe_volumes(self, **_):
            raise ClientError({"Error": {"Code": "UnauthorizedOperation", "Message": "denied"}}, "DescribeVolumes")

    session = FakeAwsSession(clients=aws_clients(ec2=DeniedEc2()))
    overview = AwsAdapter(aws_settings(tmp_path), session_factory=lambda: session).get_overview()
    assert overview.configured is True
    assert overview.volumes == []
    assert overview.warnings == ["ebs: UnauthorizedOperation"]
    assert overview.instances


def test_aws_overview_is_cached_until_ttl_expires(tmp_path):
    calls = {"count": 0}
    now = {"t": 0.0}

    def factory():
        calls["count"] += 1
        return FakeAwsSession(credentials=None)

    adapter = AwsAdapter(aws_settings(tmp_path), session_factory=factory, cache_ttl_seconds=60, clock=lambda: now["t"])
    adapter.get_overview()
    adapter.get_overview()
    assert calls["count"] == 1
    now["t"] = 61.0
    adapter.get_overview()
    assert calls["count"] == 2
    adapter.get_overview(force=True)
    assert calls["count"] == 3


def test_mask_account_ids():
    assert mask_account_ids("arn:aws:iam::123456789012:root") == "arn:aws:iam::********9012:root"
    assert mask_account_ids(None) is None


# ---------------------------------------------------------------------- Azure fakes


class FakeCredential:
    def __init__(self, error=None):
        self.error = error

    def get_token(self, *_scopes):
        if self.error:
            raise self.error
        return SimpleNamespace(token="never-logged", expires_on=0)


class CredentialUnavailableError(Exception):
    """Same class name as azure.identity.CredentialUnavailableError."""


def fake_azure_clients(_credential, _subscription):
    vm_id = "/subscriptions/s/resourceGroups/rg-demo/providers/Microsoft.Compute/virtualMachines/vm1"
    vm = SimpleNamespace(id=vm_id, name="vm1", location="westeurope", hardware_profile=SimpleNamespace(vm_size="Standard_B1s"))
    view = SimpleNamespace(statuses=[SimpleNamespace(code="ProvisioningState/succeeded"), SimpleNamespace(code="PowerState/running")])
    disk = SimpleNamespace(id="/d/disk1", name="disk1", location="westeurope", disk_size_gb=8, disk_state="Attached", sku=SimpleNamespace(name="Standard_LRS"), managed_by=vm_id)
    vnet = SimpleNamespace(id="/v/vnet1", name="vnet1", location="westeurope", address_space=SimpleNamespace(address_prefixes=["10.30.0.0/16"]), subnets=[SimpleNamespace(name="default", address_prefix="10.30.1.0/24")])
    rules = [
        SimpleNamespace(name="ssh-any", direction="Inbound", access="Allow", source_address_prefix="*"),
        SimpleNamespace(name="deny", direction="Inbound", access="Deny", source_address_prefix="*"),
    ]
    nsg = SimpleNamespace(id="/n/nsg1", name="nsg1", location="westeurope", security_rules=rules)
    point = SimpleNamespace(average=42.0, time_stamp=datetime(2026, 1, 1, tzinfo=UTC))
    metrics = SimpleNamespace(value=[SimpleNamespace(timeseries=[SimpleNamespace(data=[point, SimpleNamespace(average=None, time_stamp=None)])])])
    return AzureClients(
        resources=SimpleNamespace(resource_groups=SimpleNamespace(list=lambda: [SimpleNamespace(name="rg-demo", location="westeurope")])),
        compute=SimpleNamespace(
            virtual_machines=SimpleNamespace(list_all=lambda: [vm], instance_view=lambda rg, name: view),
            disks=SimpleNamespace(list=lambda: [disk]),
        ),
        network=SimpleNamespace(
            virtual_networks=SimpleNamespace(list_all=lambda: [vnet]),
            network_security_groups=SimpleNamespace(list_all=lambda: [nsg]),
        ),
        monitor=SimpleNamespace(metrics=SimpleNamespace(list=lambda **_: metrics)),
    )


def azure_settings(tmp_path, subscription="00000000-0000-0000-0000-00000000abcd"):
    return make_settings(tmp_path, azure_enabled=True, azure_subscription_id=subscription)


# ---------------------------------------------------------------------- Azure tests


def test_azure_without_subscription_is_not_configured(tmp_path):
    def must_not_run():
        raise AssertionError("no credential lookup without a subscription")

    adapter = AzureAdapter(azure_settings(tmp_path, subscription=None), credential_factory=must_not_run)
    overview = adapter.get_overview()
    assert overview.configured is False
    assert overview.message == "Azure credentials are not configured"


def test_azure_credential_unavailable_is_not_configured(tmp_path):
    adapter = AzureAdapter(azure_settings(tmp_path), credential_factory=lambda: FakeCredential(CredentialUnavailableError("no creds")))
    overview = adapter.get_overview()
    assert overview.configured is False
    assert overview.message == "Azure credentials are not configured"
    assert overview.detail == "CredentialUnavailableError"


def test_azure_bad_credentials_are_reported_as_unverified(tmp_path):
    adapter = AzureAdapter(azure_settings(tmp_path), credential_factory=lambda: FakeCredential(PermissionError("secret-value")))
    overview = adapter.get_overview()
    assert overview.configured is False
    assert overview.message == "Azure credentials could not be verified"
    assert "secret-value" not in overview.model_dump_json()


def test_azure_disabled_flag(tmp_path):
    adapter = AzureAdapter(make_settings(tmp_path, azure_enabled=False))
    assert "disabled" in adapter.get_overview().message


def test_azure_configured_collects_resources(tmp_path):
    adapter = AzureAdapter(azure_settings(tmp_path), credential_factory=FakeCredential, clients_factory=fake_azure_clients)
    overview = adapter.get_overview()
    assert overview.configured is True
    assert overview.identity == {"subscription_id": "********abcd"}
    assert [g.name for g in overview.resource_groups] == ["rg-demo"]
    assert (overview.instances[0].name, overview.instances[0].state, overview.instances[0].instance_type) == ("vm1", "running", "Standard_B1s")
    assert overview.volumes[0].attached_to == "vm1" and overview.volumes[0].volume_type == "Standard_LRS"
    kinds = {n.kind: n for n in overview.networks}
    assert kinds["vnet"].cidrs == ["10.30.0.0/16"]
    assert kinds["nsg"].details["inbound_allow_from_internet"] == ["ssh-any"]
    assert overview.metrics[0].value == 42.0
    assert overview.warnings == []


# ---------------------------------------------------------------------- API + metrics


def make_api_client(tmp_path, **kwargs):
    container = build_container(make_settings(tmp_path), collector=StaticCollector(build_snapshot()), **kwargs)
    return TestClient(create_app(container))


def test_api_returns_clean_not_configured_responses(tmp_path):
    client = make_api_client(tmp_path)
    aws = client.get("/api/cloud/aws")
    azure = client.get("/api/cloud/azure")
    assert aws.status_code == azure.status_code == 200
    assert aws.json()["configured"] is False and azure.json()["configured"] is False
    assert aws.json()["provider"] == "AWS" and azure.json()["provider"] == "AZURE"
    assert "disabled" in aws.json()["message"]


def test_api_application_keeps_running_with_missing_credentials(tmp_path):
    settings = make_settings(tmp_path, aws_enabled=True, azure_enabled=True)
    container = build_container(
        settings,
        collector=StaticCollector(build_snapshot()),
        aws=AwsAdapter(settings, session_factory=lambda: FakeAwsSession(credentials=None)),
        azure=AzureAdapter(settings),
    )
    client = TestClient(create_app(container))
    assert client.get("/api/cloud/aws").json()["message"] == "AWS credentials are not configured"
    assert client.get("/api/cloud/azure").json()["message"] == "Azure credentials are not configured"
    assert client.get("/health").status_code == 200
    assert client.get("/api/status").status_code == 200


def test_cloud_resources_appear_in_hosts_and_metrics(tmp_path):
    settings = make_settings(tmp_path, aws_enabled=True)
    session = FakeAwsSession(clients=aws_clients())
    container = build_container(
        settings,
        collector=StaticCollector(build_snapshot()),
        aws=AwsAdapter(settings, session_factory=lambda: session),
    )
    client = TestClient(create_app(container))
    container.aws.get_overview(force=True)  # what the background refresher does
    hosts = client.get("/api/hosts").json()
    assert hosts["counts"] == {"LOCAL": 1, "AWS": 2, "AZURE": 0}
    assert {h["provider"] for h in hosts["hosts"]} == {"LOCAL", "AWS"}
    text = client.get("/metrics").text
    assert sample_value(text, "cloudops_cloud_configured", provider="AWS") == 1.0
    assert sample_value(text, "cloudops_cloud_instances", provider="AWS", state="running") == 1.0
    assert sample_value(text, "cloudops_cloud_volumes", provider="AWS") == 1.0
    assert sample_value(text, "cloudops_cloud_instance_cpu_percent", provider="AWS", instance="i-0abc") == 12.5
