# ── ECR Repository ────────────────────────────────────────────────────────────
# Stores Docker images. GitHub Actions pushes here; ECS pulls from here.

resource "aws_ecr_repository" "backend" {
  name                 = local.name
  image_tag_mutability = "MUTABLE" # allows :latest tag to be overwritten

  image_scanning_configuration {
    scan_on_push = true # free vulnerability scan on every push
  }

  tags = local.tags
}

# Lifecycle policy — keep only the 10 most recent images to control storage cost
resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
