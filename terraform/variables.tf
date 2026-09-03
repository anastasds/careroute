variable "project_id" {
  description = "The Google Cloud Project ID"
  type        = string
  default     = "careroute-prod"
}

variable "region" {
  description = "The GCP region to deploy Cloud Run"
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "The Firestore database location"
  type        = string
  default     = "nam5"
}

variable "container_image" {
  description = "The container image URI for CareRoute"
  type        = string
  default     = "gcr.io/careroute-prod/careroute-agent:latest"
}

