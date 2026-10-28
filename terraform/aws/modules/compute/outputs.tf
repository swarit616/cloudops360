output "instance_id" {
  description = "EC2 instance id."
  value       = aws_instance.this.id
}

output "data_volume_id" {
  description = "EBS data volume id."
  value       = aws_ebs_volume.data.id
}
