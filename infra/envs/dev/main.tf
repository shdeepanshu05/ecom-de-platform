# 1. Enable the APIs this phase needs ------------------------------------------
resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# 2. Data lake buckets (raw / curated / staging) -------------------------------
module "buckets" {
  source   = "../../modules/gcs_bucket"
  for_each = local.buckets

  project_id        = var.project_id
  name              = "${var.project_id}-${each.key}"
  location          = var.region
  force_destroy     = var.force_destroy
  delete_after_days = each.value.delete_after_days
  labels            = { purpose = each.value.purpose }

  depends_on = [google_project_service.apis]
}

# 3. Medallion datasets (bronze / silver / gold) -------------------------------
module "datasets" {
  source   = "../../modules/bigquery_dataset"
  for_each = local.datasets

  project_id                 = var.project_id
  dataset_id                 = each.key
  description                = each.value
  location                   = var.region
  delete_contents_on_destroy = var.force_destroy
  labels                     = { layer = each.key }

  depends_on = [google_project_service.apis]
}