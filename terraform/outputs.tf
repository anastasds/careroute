output "cloud_run_service_url" {
  description = "The deployed URL of the CareRoute Cloud Run service"
  value       = google_cloud_run_v2_service.careroute_service.uri
}

output "firestore_database_name" {
  description = "The ID of the provisioned Firestore database"
  value       = google_firestore_database.careroute_db.name
}

output "service_account_email" {
  description = "The service account email used by CareRoute"
  value       = google_service_account.agent_sa.email
}

