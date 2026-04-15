# terraform/variables.tf
variable "aws_region" { default = "ap-southeast-1" }
variable "anthropic_api_key" { sensitive = true }
variable "app_name" { default = "career-lighthouse" }
variable "qdrant_url" {
  description = "External Qdrant endpoint for production deployments"
  type        = string

  validation {
    condition     = length(trimspace(var.qdrant_url)) > 0
    error_message = "qdrant_url must be set to a reachable Qdrant endpoint."
  }
}
variable "ecr_image_api" { description = "ECR image URI for API service" }
variable "ecr_image_web" { description = "ECR image URI for web service" }
