variable "project_id" {
  description = "GCP project that owns the dataset."
  type        = string
}

variable "dataset_id" {
  description = "Dataset ID (letters, digits, underscores)."
  type        = string
}

variable "location" {
  description = "Dataset location. Must match the GCS bucket location for load jobs."
  type        = string
}

variable "description" {
  description = "What this dataset contains."
  type        = string
  default     = ""
}

variable "delete_contents_on_destroy" {
  description = "Allow destroy to drop a dataset that still contains tables. true only in dev."
  type        = bool
  default     = false
}

variable "labels" {
  description = "Extra labels for this dataset."
  type        = map(string)
  default     = {}
}