locals {
  common_labels = {
    project     = "ecom-de-platform"
    environment = var.environment
    managed_by  = "terraform"
  }

  required_apis = [
    "storage.googleapis.com",
    "bigquery.googleapis.com",
  ]

  buckets = {
    raw = {
      purpose           = "bronze-landing"
      delete_after_days = var.raw_retention_days
    }
    curated = {
      purpose           = "curated-parquet"
      delete_after_days = null
    }
    staging = {
      purpose           = "temp-staging"
      delete_after_days = 7
    }
  }

  datasets = {
    bronze = "Raw data as ingested: CDC tables, loaded files, malformed records"
    silver = "Cleaned, typed, deduplicated and validated entities"
    gold   = "Star schema facts/dimensions and business metrics"
  }
}