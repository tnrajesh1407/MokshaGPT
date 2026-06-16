variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "ap-south-1" # Mumbai — closest to India
}

variable "environment" {
  description = "Deployment environment (prod, staging)"
  type        = string
  default     = "prod"
}

# ── Secrets (passed via terraform.tfvars or CI env vars) ─────────────────────

variable "gemini_api_key" {
  description = "Google Gemini API key"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "claude_api_key" {
  description = "Anthropic Claude API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "supabase_url" {
  description = "Supabase project URL"
  type        = string
  sensitive   = true
}

variable "supabase_service_key" {
  description = "Supabase service role key"
  type        = string
  sensitive   = true
}

variable "langchain_api_key" {
  description = "LangSmith API key (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

# ── App config ────────────────────────────────────────────────────────────────

variable "llm_provider" {
  description = "Default LLM provider (gemini/claude/openai)"
  type        = string
  default     = "gemini"
}

variable "task_cpu" {
  description = "Fargate task CPU units (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Fargate task memory in MB"
  type        = number
  default     = 2048
}

variable "desired_count" {
  description = "Number of running ECS tasks"
  type        = number
  default     = 1
}
