# Terraform Infrastructure as Code for CareRoute on Google Cloud Platform
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Enable Required GCP APIs
resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "firestore.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudtrace.googleapis.com",
    "logging.googleapis.com",
    "aiplatform.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# 2. Secret Manager for Secure Gemini API Key Management
resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "careroute-gemini-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.services]
}

# 3. Google Cloud Firestore Database for Persistent Agent Memory & Sessions
resource "google_firestore_database" "careroute_db" {
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.services]
}

# 4. Service Account for CareRoute Agent Runtime
resource "google_service_account" "agent_sa" {
  account_id   = "careroute-agent-runner"
  display_name = "CareRoute AI Agent Service Account"
}

# Grant Secret Manager Access
resource "google_secret_manager_secret_iam_member" "secret_access" {
  secret_id = google_secret_manager_secret.gemini_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent_sa.email}"
}

# Grant Firestore Access
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

# Grant Cloud Trace & Logging Access for OpenTelemetry
resource "google_project_iam_member" "cloud_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

# 5. Cloud Run Service for CareRoute Agent
resource "google_cloud_run_v2_service" "careroute_service" {
  name     = "careroute-agent"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.agent_sa.email

    containers {
      image = var.container_image

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "CAREROUTE_STORAGE_BACKEND"
        value = "firestore"
      }
      env {
        name  = "GCP_SECRET_NAME"
        value = google_secret_manager_secret.gemini_api_key.secret_id
      }
      env {
        name  = "OTEL_SERVICE_NAME"
        value = "careroute-agent-cloudrun"
      }
    }
  }

  depends_on = [
    google_project_service.services,
    google_firestore_database.careroute_db
  ]
}

# Allow Unauthenticated / Clinician Access
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.careroute_service.name
  location = google_cloud_run_v2_service.careroute_service.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

