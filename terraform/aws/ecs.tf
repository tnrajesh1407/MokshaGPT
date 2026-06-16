# ── ECS Cluster ───────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled" # CloudWatch Container Insights for metrics
  }

  tags = local.tags
}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${local.name}"
  retention_in_days = 30
  tags              = local.tags
}

# ── ECS Task Definition ───────────────────────────────────────────────────────
# Defines the container spec. GitHub Actions registers a new revision on each
# deploy (with the new image tag), then updates the service to use it.

resource "aws_ecs_task_definition" "backend" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = "${aws_ecr_repository.backend.repository_url}:latest"
    essential = true

    portMappings = [{
      containerPort = 8080
      protocol      = "tcp"
    }]

    # Secrets injected from AWS Secrets Manager at container start
    # The app reads them as environment variables — no code changes needed
    secrets = [
      { name = "GEMINI_API_KEY",       valueFrom = aws_secretsmanager_secret.app["gemini_api_key"].arn },
      { name = "OPENAI_API_KEY",       valueFrom = aws_secretsmanager_secret.app["openai_api_key"].arn },
      { name = "CLAUDE_API_KEY",       valueFrom = aws_secretsmanager_secret.app["claude_api_key"].arn },
      { name = "SUPABASE_URL",         valueFrom = aws_secretsmanager_secret.app["supabase_url"].arn },
      { name = "SUPABASE_SERVICE_KEY", valueFrom = aws_secretsmanager_secret.app["supabase_service_key"].arn },
      { name = "LANGCHAIN_API_KEY",    valueFrom = aws_secretsmanager_secret.app["langchain_api_key"].arn },
    ]

    # Non-sensitive config as plain env vars
    environment = [
      { name = "LLM_PROVIDER",           value = var.llm_provider },
      { name = "LANGCHAIN_TRACING_V2",   value = "true" },
      { name = "LANGCHAIN_PROJECT",      value = "mokshagpt" },
      { name = "PORT",                   value = "8080" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.backend.name
        "awslogs-region"        = local.region
        "awslogs-stream-prefix" = "ecs"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60 # give the app time to start (vectorbt import is slow)
    }
  }])

  tags = local.tags
}

# ── ECS Service ───────────────────────────────────────────────────────────────
# Keeps desired_count tasks running. On deploy, does a rolling update:
# starts new task → waits for health check → stops old task.

resource "aws_ecs_service" "backend" {
  name            = local.name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  # Rolling deploy — always keep at least 1 task running during updates
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true # needed for Fargate to pull ECR images in public subnet
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8080
  }

  # Ignore task_definition changes from Terraform after initial deploy —
  # GitHub Actions manages image updates via aws ecs update-service
  lifecycle {
    ignore_changes = [task_definition]
  }

  depends_on = [aws_lb_listener.https]

  tags = local.tags
}

# ── Application Load Balancer ─────────────────────────────────────────────────

resource "aws_lb" "backend" {
  name               = local.name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  tags               = local.tags
}

resource "aws_lb_target_group" "backend" {
  name        = local.name
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip" # required for Fargate awsvpc networking

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
  }

  tags = local.tags
}

# HTTP → HTTPS redirect
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.backend.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# HTTPS listener — requires an ACM certificate (see variables)
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.backend.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}
