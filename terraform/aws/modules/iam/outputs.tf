output "instance_profile_name" {
  description = "Instance profile to attach to the EC2 instance."
  value       = aws_iam_instance_profile.instance.name
}

output "readonly_policy_arn" {
  description = "ARN of the CloudOps360 read-only policy."
  value       = aws_iam_policy.readonly.arn
}
