resource "google_storage_bucket" "this" {
  project                     = var.project_id
  name                        = var.name
  location                    = var.location
  storage_class               = "STANDARD"
  force_destroy               = var.force_destroy
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = var.labels

  versioning {
    enabled = var.versioning_enabled
  }

  dynamic "lifecycle_rule" {
    for_each = var.delete_after_days == null ? [] : [var.delete_after_days]
    content {
      condition {
        age = lifecycle_rule.value
      }
      action {
        type = "Delete"
      }
    }
  }
}