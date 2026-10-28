terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

data "aws_iam_policy_document" "assume_ec2" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${var.name}-instance-role"
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json
}

# SSM Session Manager (shell access without opening SSH) and the CloudWatch agent.
resource "aws_iam_role_policy_attachment" "managed" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
  ])

  role       = aws_iam_role.instance.name
  policy_arn = each.value
}

# The exact read-only permissions the CloudOps360 AWS adapter uses.
data "aws_iam_policy_document" "readonly" {
  statement {
    sid    = "CloudOps360ReadOnly"
    effect = "Allow"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeVolumes",
      "ec2:DescribeVpcs",
      "ec2:DescribeSubnets",
      "cloudwatch:GetMetricData",
      "cloudwatch:ListMetrics",
      "iam:ListAccountAliases",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "readonly" {
  name        = "${var.name}-readonly"
  description = "Least-privilege read-only access for the CloudOps360 AWS adapter"
  policy      = data.aws_iam_policy_document.readonly.json
}

resource "aws_iam_role_policy_attachment" "readonly" {
  role       = aws_iam_role.instance.name
  policy_arn = aws_iam_policy.readonly.arn
}

resource "aws_iam_instance_profile" "instance" {
  name = "${var.name}-instance-profile"
  role = aws_iam_role.instance.name
}
