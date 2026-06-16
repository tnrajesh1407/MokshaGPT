# ── Cloud Scheduler for Nifty 100 Precompute Jobs ────────────────────────────

# Enable Cloud Scheduler API
resource "google_project_service" "scheduler_api" {
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

# Service account for Cloud Run Jobs
resource "google_service_account" "precompute_sa" {
  account_id   = "precompute-job-sa"
  display_name = "Service Account for Precompute Jobs"
}

# Grant permissions to access secrets
resource "google_secret_manager_secret_iam_member" "precompute_gemini_access" {
  secret_id = google_secret_manager_secret.gemini_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.precompute_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "precompute_openai_access" {
  secret_id = google_secret_manager_secret.openai_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.precompute_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "precompute_claude_access" {
  secret_id = google_secret_manager_secret.claude_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.precompute_sa.email}"
}

# Add Supabase secrets
resource "google_secret_manager_secret" "supabase_url" {
  secret_id = "supabase-url"
  replication { auto {} }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "supabase_url" {
  secret      = google_secret_manager_secret.supabase_url.id
  secret_data = var.supabase_url
}

resource "google_secret_manager_secret" "supabase_service_key" {
  secret_id = "supabase-service-key"
  replication { auto {} }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "supabase_service_key" {
  secret      = google_secret_manager_secret.supabase_service_key.id
  secret_data = var.supabase_service_key
}

resource "google_secret_manager_secret_iam_member" "precompute_supabase_url_access" {
  secret_id = google_secret_manager_secret.supabase_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.precompute_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "precompute_supabase_key_access" {
  secret_id = google_secret_manager_secret.supabase_service_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.precompute_sa.email}"
}

# Cloud Run Job for 15-minute precompute (incremental)
resource "google_cloud_run_v2_job" "precompute_incremental" {
  name     = "precompute-nifty100-incremental"
  location = var.region

  template {
    template {
      service_account = google_service_account.precompute_sa.email

      containers {
        image = "gcr.io/${var.project_id}/mokshagpt-backend:latest"
        command = ["python"]
        args    = ["precompute_nifty100.py"]

        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
        }

        env {
          name = "SUPABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.supabase_url.secret_id
              version = "latest"
            }
          }
        }

        env {
          name = "SUPABASE_SERVICE_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.supabase_service_key.secret_id
              version = "latest"
            }
          }
        }
      }

      timeout = "900s" # 15 minutes max
    }
  }

  depends_on = [
    google_project_service.apis,
    google_service_account.precompute_sa
  ]
}

# Cloud Run Job for daily full precompute
resource "google_cloud_run_v2_job" "precompute_full" {
  name     = "precompute-nifty100-full"
  location = var.region

  template {
    template {
      service_account = google_service_account.precompute_sa.email

      containers {
        image = "gcr.io/${var.project_id}/mokshagpt-backend:latest"
        command = ["python"]
        args    = ["precompute_nifty100.py", "--full"]

        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
        }

        env {
          name = "SUPABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.supabase_url.secret_id
              version = "latest"
            }
          }
        }

        env {
          name = "SUPABASE_SERVICE_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.supabase_service_key.secret_id
              version = "latest"
            }
          }
        }
      }

      timeout = "1800s" # 30 minutes max
    }
  }

  depends_on = [
    google_project_service.apis,
    google_service_account.precompute_sa
  ]
}

# Cloud Scheduler: Every 15 minutes (incremental)
resource "google_cloud_scheduler_job" "precompute_15min" {
  name             = "precompute-nifty100-15min"
  description      = "Run incremental Nifty 100 precompute every 15 minutes"
  schedule         = "*/15 * * * *"
  time_zone        = "Asia/Kolkata"
  attempt_deadline = "900s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.precompute_incremental.name}:run"

    oauth_token {
      service_account_email = google_service_account.precompute_sa.email
    }
  }

  depends_on = [
    google_project_service.scheduler_api,
    google_cloud_run_v2_job.precompute_incremental
  ]
}

# Cloud Scheduler: Once daily at 6 AM IST (full refresh)
resource "google_cloud_scheduler_job" "precompute_daily" {
  name             = "precompute-nifty100-daily"
  description      = "Run full Nifty 100 precompute once daily"
  schedule         = "0 6 * * *"
  time_zone        = "Asia/Kolkata"
  attempt_deadline = "1800s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.precompute_full.name}:run"

    oauth_token {
      service_account_email = google_service_account.precompute_sa.email
    }
  }

  depends_on = [
    google_project_service.scheduler_api,
    google_cloud_run_v2_job.precompute_full
  ]
}

# Grant Cloud Run Jobs invoker role to the service account
resource "google_cloud_run_v2_job_iam_member" "precompute_incremental_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.precompute_incremental.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.precompute_sa.email}"
}

resource "google_cloud_run_v2_job_iam_member" "precompute_full_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.precompute_full.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.precompute_sa.email}"
}
