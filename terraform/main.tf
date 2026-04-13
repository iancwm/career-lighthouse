terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.aws_region }

# ---------------------------------------------------------------------------
# EFS — Qdrant persistent storage (encrypted)
# ---------------------------------------------------------------------------
resource "aws_efs_file_system" "qdrant" {
  encrypted = true
  tags = { Name = "${var.app_name}-qdrant" }
}

# EFS — Knowledge YAML and logs (encrypted)
resource "aws_efs_file_system" "knowledge" {
  encrypted = true
  tags = { Name = "${var.app_name}-knowledge" }
}

# ---------------------------------------------------------------------------
# ECS Cluster
# ---------------------------------------------------------------------------
resource "aws_ecs_cluster" "main" {
  name = var.app_name
}

# ---------------------------------------------------------------------------
# Secrets — SSM Parameter Store
# ---------------------------------------------------------------------------
resource "aws_ssm_parameter" "anthropic_key" {
  name  = "/${var.app_name}/anthropic_api_key"
  type  = "SecureString"
  value = var.anthropic_api_key
}

resource "aws_ssm_parameter" "admin_key" {
  name  = "/${var.app_name}/admin_key"
  type  = "SecureString"
  value = var.admin_key
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.app_name}"
  retention_in_days = 30
}

# ---------------------------------------------------------------------------
# Amplify — Next.js frontend
# ---------------------------------------------------------------------------
resource "aws_amplify_app" "web" {
  name = "${var.app_name}-web"
  environment_variables = {
    NEXT_PUBLIC_API_URL = "https://${aws_lb.api.dns_name}"
  }
}

# ---------------------------------------------------------------------------
# ECS Task Definition — API
# ---------------------------------------------------------------------------
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
      root_directory = "/qdrant"
    }
  }

  volume {
    name = "knowledge-data"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.knowledge.id
      root_directory = "/knowledge"
    }
  }

  volume {
    name = "logs-data"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.knowledge.id
      root_directory = "/logs"
    }
  }

  container_definitions = jsonencode([{
    name  = "api"
    image = var.ecr_image_api
    portMappings = [{ containerPort = 8000 }]
    environment = [
      { name = "DATA_PATH",              value = "/data/qdrant" },
      { name = "ALLOWED_ORIGINS",        value = "https://${aws_amplify_app.web.default_domain}" },
      { name = "QDRANT_URL",             value = "http://localhost:6333" },
      { name = "CAREER_PROFILES_DIR",    value = "/app/knowledge/career_profiles" },
      { name = "EMPLOYERS_DIR",          value = "/app/knowledge/employers" },
      { name = "QUERY_LOG_PATH",         value = "/app/logs/query_log.jsonl" },
      { name = "WEB_CONCURRENCY",        value = "1" },
      { name = "SENTENCE_TRANSFORMERS_HOME", value = "/app/.cache" },
    ]
    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_ssm_parameter.anthropic_key.arn },
      { name = "ADMIN_KEY",         valueFrom = aws_ssm_parameter.admin_key.arn },
    ]
    mountPoints = [
      { sourceVolume = "qdrant-data",    containerPath = "/data/qdrant",       readOnly = false },
      { sourceVolume = "knowledge-data", containerPath = "/app/knowledge",     readOnly = false },
      { sourceVolume = "logs-data",      containerPath = "/app/logs",          readOnly = false },
    ]
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" || exit 1"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 60
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
  }])
}

# ---------------------------------------------------------------------------
# ALB — Application Load Balancer (placeholder — extend with listener/TG)
# ---------------------------------------------------------------------------
resource "aws_lb" "api" {
  name               = "${var.app_name}-alb"
  internal           = false
  load_balancer_type = "application"
  # subnets and security_groups should be wired to your VPC resources
  subnets            = var.public_subnet_ids
  security_groups    = [var.alb_security_group_id]
}
