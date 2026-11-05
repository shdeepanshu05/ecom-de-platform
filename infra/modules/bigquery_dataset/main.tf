resource "google_bigquery_dataset" "this" {
  project                    = var.project_id
  dataset_id                 = var.dataset_id
  location                   = var.location
  description                = var.description
  delete_contents_on_destroy = var.delete_contents_on_destroy
  labels                     = var.labels
}