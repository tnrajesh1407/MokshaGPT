# ── AWS Secrets Manager ───────────────────────────────────────────────────────
# Stores all API keys. ECS task pulls them at runtime via IAM role — no secrets
# in environment variables or Docker images.

locals {
  secrets = {
    gemini_api_key       = var.gemini_api_key
    openai_api_key       = var.openai_api_key
    claude_api_key       = var.claude_api_key
    supabase_url         = var.supabase_url
    supabase_service_key = var.supabase_service_key
    langchain_api_key    = var.langchain_api_key
  }
}

resource "aws_secretsmanager_secret" "app" {
  for_each                = local.secrets
  name                    = "mokshagpt/${each.key}"
  recovery_window_in_days = 7 # 7-day safety window before permanent deletion
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "app" {
  for_each      = local.secrets
  secret_id     = aws_secretsmanager_secret.app[each.key].id
  secret_string = each.value
}
