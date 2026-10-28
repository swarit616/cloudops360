output "vpc_id" {
  description = "VPC id."
  value       = aws_vpc.this.id
}

output "subnet_id" {
  description = "Subnet id."
  value       = aws_subnet.public.id
}

output "security_group_id" {
  description = "Instance security group id."
  value       = aws_security_group.instance.id
}
