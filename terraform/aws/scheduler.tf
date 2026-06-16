# ── ECS Scheduled Tasks (Nifty 100 Precompute) ───────────────────────────────
# Replaces GCP Cloud Scheduler + Cloud Run Jobs.
# EventBridge Scheduler triggers ECS tasks on a cron schedule.

resource "aws_scheduler_schedule_group" "precompute" {
  name = "mokshagpt-precompute"
  tags = local.tags
}

# IAM role for EventBridge Scheduler to launch ECS tasks
resource "aws_iam_role" "scheduler" {
  name = "${local.name}-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "scheduler" {
  name = "${local.name}-scheduler-policy"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["ecs:RunTask"]
      Resource = [aws_ecs_task_definition.backend.arn]
    }, {
      Effect   = "Allow"
      Action   = "iam:PassRole"
      Resource = [
        aws_iam_role.ecs_execution.arn,
        aws_iam_role.ecs_task.arn
      ]
    }]
  })
}

# ── 15-minute incremental refresh ────────────────────────────────────────────

resource "aws_scheduler_schedule" "precompute_incremental" {
  name       = "precompute-nifty100-15min"
  group_name = aws_scheduler_schedule_group.precompute.name

  flexible_time_window { mode = "OFF" }

  # Every 15 minutes during Indian market hours (Mon–Fri, 3:45–10:00 UTC = 9:15–15:30 IST)
  schedule_expression          = "cron(0/15 3-10 ? * MON-FRI *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.backend.arn
      launch_type         = "FARGATE"
      task_count          = 1

      network_configuration {
        assign_public_ip = true
        subnets          = aws_subnet.public[*].id
        security_groups  = [aws_security_group.ecs.id]
      }

      # Override the default CMD to run the precompute script
      overrides {
        container_overrides {
          name    = "backend"
          command = ["python", "precompute_nifty100.py"]
        }
      }
    }

    retry_policy {
      maximum_retry_attempts = 1
    }
  }
}

# ── Daily full refresh (6:00 AM IST = 00:30 UTC) ─────────────────────────────

resource "aws_scheduler_schedule" "precompute_daily" {
  name       = "precompute-nifty100-daily"
  group_name = aws_scheduler_schedule_group.precompute.name

  flexible_time_window { mode = "OFF" }

  schedule_expression          = "cron(30 0 ? * MON-FRI *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.backend.arn
      launch_type         = "FARGATE"
      task_count          = 1

      network_configuration {
        assign_public_ip = true
        subnets          = aws_subnet.public[*].id
        security_groups  = [aws_security_group.ecs.id]
      }

      overrides {
        container_overrides {
          name    = "backend"
          command = ["python", "precompute_nifty100.py", "--full"]
        }
      }
    }

    retry_policy {
      maximum_retry_attempts = 1
    }
  }
}
