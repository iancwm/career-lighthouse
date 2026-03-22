# terraform/main.tf
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.aws_region }

# EFS for Qdrant persistent volume
resource "aws_efs_file_system" "qdrant" {
  encrypted = true
  tags = { Name = "${var.app_name}-qdrant" }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = var.app_name
}

# SSM Parameter for API key
resource "aws_ssm_parameter" "anthropic_key" {
  name  = "/${var.app_name}/anthropic_api_key"
  type  = "SecureString"
  value = var.anthropic_api_key
}

# Amplify for Next.js frontend
resource "aws_amplify_app" "web" {
  name = "${var.app_name}-web"
  environment_variables = {
    NEXT_PUBLIC_API_URL = "https://${aws_lb.api.dns_name}"
  }
}

# ECS Task Definition — API
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.app_name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"

  volume {
    name = "qdrant-data"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.qdrant.id
      root_directory = "/"
    }
  }

  container_definitions = jsonencode([{
    name  = "api"
    image = var.ecr_image_api
    portMappings = [{ containerPort = 8000 }]
    environment = [
      { name = "DATA_PATH", value = "/data/qdrant" },
      { name = "ALLOWED_ORIGINS", value = "https://${aws_amplify_app.web.default_domain}" }
    ]
    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_ssm_parameter.anthropic_key.arn }
    ]
    mountPoints = [{ sourceVolume = "qdrant-data", containerPath = "/data/qdrant" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/${var.app_name}"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
  }])
}
