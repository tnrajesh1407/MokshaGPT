# Extra variables referenced in ecs.tf and iam.tf

variable "acm_certificate_arn" {
  description = "ARN of ACM TLS certificate for the ALB HTTPS listener. Create in AWS Console → Certificate Manager first."
  type        = string
}

variable "github_repo" {
  description = "GitHub repo in org/repo format e.g. myorg/mokshagpt"
  type        = string
}
