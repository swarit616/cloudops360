output "vpc_id" {
  description = "VPC id."
  value       = module.network.vpc_id
}

output "subnet_id" {
  description = "Subnet id."
  value       = module.network.subnet_id
}

output "security_group_id" {
  description = "Instance security group id."
  value       = module.network.security_group_id
}

output "instance_id" {
  description = "EC2 instance id (null when enable_ec2 = false)."
  value       = one(module.compute[*].instance_id)
}

output "data_volume_id" {
  description = "Additional EBS data volume id (null when enable_ec2 = false)."
  value       = one(module.compute[*].data_volume_id)
}

output "cloudops360_readonly_policy_arn" {
  description = "Least-privilege read-only policy CloudOps360 needs. Attach it to the identity the API runs as."
  value       = module.iam.readonly_policy_arn
}
