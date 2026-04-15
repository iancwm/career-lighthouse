terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.aws_region }

# ---------------------------------------------------------------------------
# EFS — API writable data (encrypted)
# ---------------------------------------------------------------------------
resource "aws_efs_file_system" "api_data" {
  encrypted = true
  tags = { Name = "${var.app_name}-api-data" }
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
    name = "api-data"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.api_data.id
      root_directory = "/api-data"
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
      { name = "ALLOWED_ORIGINS",        value = "https://${aws_amplify_app.web.default_domain}" },
      { name = "QDRANT_URL",             value = var.qdrant_url },
      { name = "DATA_PATH",              value = "/app/data/qdrant" },
      { name = "SESSIONS_DIR",           value = "/app/data/sessions" },
      { name = "CAREER_PROFILES_DIR",    value = "/app/knowledge/career_profiles" },
      { name = "EMPLOYERS_DIR",          value = "/app/knowledge/employers" },
      { name = "DRAFT_TRACKS_DIR",       value = "/app/knowledge/draft_tracks" },
      { name = "CAREER_TRACKS_REGISTRY_PATH", value = "/app/knowledge/career_tracks.yaml" },
      { name = "CAREER_PROFILE_HISTORY_DIR", value = "/app/knowledge/career_profiles_history" },
      { name = "QUERY_LOG_PATH",         value = "/app/logs/query_log.jsonl" },
      { name = "TRACK_PUBLISH_JOURNAL_PATH", value = "/app/logs/track_publish_journal.jsonl" },
      { name = "TRACK_PUBLISH_LOG_PATH", value = "/app/logs/track_publish_log.jsonl" },
      { name = "TRACKS_VERSION_PATH",    value = "/app/knowledge/.tracks-version" },
      { name = "WEB_CONCURRENCY",        value = "1" },
      { name = "SENTENCE_TRANSFORMERS_HOME", value = "/app/.cache" },
      { name = "UV_CACHE_DIR",           value = "/home/appuser/.cache/uv" },
    ]
    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_ssm_parameter.anthropic_key.arn },
      { name = "ADMIN_KEY",         valueFrom = aws_ssm_parameter.admin_key.arn },
    ]
    mountPoints = [
      { sourceVolume = "api-data",       containerPath = "/app/data",          readOnly = false },
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
