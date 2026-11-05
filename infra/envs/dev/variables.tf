variable "project_id" {
  description = "GCP project ID for this environment."
  type        = string
}

variable "region" {
  description = "Single region for all regional resources."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "force_destroy" {
  description = "Allow destroying non-empty buckets/datasets. true only in dev."
  type        = bool
  default     = false
}

variable "raw_retention_days" {
  description = "Auto-delete raw files after N days. null = keep forever."
  type        = number
  default     = null
}