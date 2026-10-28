# AWS integration

The AWS adapter (`app/cloud/aws.py`) is **read-only** and optional. Without credentials the API returns:

```json
{ "provider": "AWS", "configured": false, "message": "AWS credentials are not configured", "...": "..." }
```

and everything else keeps working.

## What it reads

| Area | API calls | Used for |
|---|---|---|
| Identity | `sts:GetCallerIdentity`, `iam:ListAccountAliases` | credential verification (account ids are masked in output) |
| EC2 | `ec2:DescribeInstances` | instance discovery and state |
| EBS | `ec2:DescribeVolumes` | volume size, state, encryption, attachment |
| VPC | `ec2:DescribeVpcs`, `ec2:DescribeSubnets` | basic network information |
| CloudWatch | `cloudwatch:GetMetricData` | latest `CPUUtilization` of running instances |

Each section is independent: a missing permission produces an entry in `warnings` (e.g. `ebs: UnauthorizedOperation`),
not a failure. Results are cached for `CLOUD_CACHE_TTL_SECONDS` and refreshed in the background.

## Least-privilege policy

`terraform/aws` creates this policy (`cloudops360_readonly_policy_arn` output). It is the entire permission set required:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "CloudOps360ReadOnly",
    "Effect": "Allow",
    "Action": [
      "ec2:DescribeInstances", "ec2:DescribeVolumes", "ec2:DescribeVpcs", "ec2:DescribeSubnets",
      "cloudwatch:GetMetricData", "cloudwatch:ListMetrics", "iam:ListAccountAliases"
    ],
    "Resource": "*"
  }]
}
```

## Providing credentials safely (best to worst)

1. **IAM role** when running on AWS (EC2 instance profile, ECS task role). No secrets exist at all. `terraform/aws`
   attaches the read-only policy to the example instance's role.
2. **IAM Identity Center (SSO)** locally: `aws configure sso`, `aws sso login --profile cloudops360-readonly`, then
   `AWS_PROFILE=cloudops360-readonly make run`. Short-lived credentials.
3. **A named profile** in `~/.aws/credentials` for a dedicated read-only IAM user, with MFA and key rotation.
4. **Environment variables** (`AWS_ACCESS_KEY_ID` ...) in your **git-ignored** `.env`. Last resort.

For Docker, copy `docker-compose.override.example.yml` to `docker-compose.override.yml` to mount `~/.aws` read-only
instead of putting keys in `.env`. Never commit credentials; `.gitignore` already excludes `.env` and key files.

## Verify

```bash
export AWS_PROFILE=cloudops360-readonly AWS_DEFAULT_REGION=eu-west-1
make run &
curl -s localhost:8000/api/cloud/aws | python3 -m json.tool
curl -s localhost:8000/metrics | grep cloudops_cloud
```

## Terraform example and cost

`terraform/aws` creates a VPC, subnet, internet gateway, locked-down default security group, an instance security
group (no inbound unless `allowed_ssh_cidrs` is set), IAM role/instance profile/read-only policy, one `t3.micro`
(IMDSv2 required, encrypted root volume) and one encrypted 8 GiB gp3 data volume. There is no NAT gateway.
Rough cost is a few USD per month if left running (instance + two small volumes + public IPv4). Set
`enable_ec2 = false` to plan only network and IAM. Always finish with `terraform destroy`.
