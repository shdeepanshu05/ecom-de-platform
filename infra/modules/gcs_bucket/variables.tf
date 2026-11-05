variable "project_id" {
    description = "GCP project which owns the project"
    type = string
}

variable "name" {
    description = "Globally unique bucket name"
}
variable "location" {
  description = "Bucket location. Keep equal to the BigQuery dataset location."
  type        = string
}

variable "force_destroy" {
  description = "Allow terraform destroy to delete a non-empty bucket. true only in dev."
  type        = bool
  default     = false
}

variable "versioning_enabled" {
  description = "Keep previous versions of overwritten or deleted objects."
  type        = bool
  default     = false
}

variable "delete_after_days" {
  description = "Delete objects older than N days. null = keep forever."
  type        = number
  default     = null
}

variable "labels" {
  description = "Extra labels for this bucket (merged with provider default labels)."
  type        = map(string)
  default     = {}
}