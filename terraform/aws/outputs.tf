output "backend_url" {
  description = "ALB DNS name — point your domain CNAME here"
  value       = "https://${aws_lb.backend.dns_name}"
}

output "ecr_repository_url" {
  description = "ECR repository URL — used in GitHub Actions to push images"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name — used in GitHub Actions to trigger deploys"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name — used in GitHub Actions to trigger deploys"
  value       = aws_ecs_service.backend.name
}

output "github_actions_role_arn" {
  description = "IAM role ARN to paste into GitHub Actions secret AWS_ROLE_ARN"
  value       = aws_iam_role.github_actions.arn
}
