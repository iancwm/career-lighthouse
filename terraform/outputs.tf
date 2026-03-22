# terraform/outputs.tf
output "api_url" { value = "https://${aws_lb.api.dns_name}" }
output "web_url" { value = "https://${aws_amplify_app.web.default_domain}" }
output "efs_id"  { value = aws_efs_file_system.qdrant.id }
