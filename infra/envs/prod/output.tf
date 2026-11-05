output "bucket_names" {
  description = "Data lake bucket names by purpose."
  value       = { for key, bucket in module.buckets : key => bucket.name }
}

output "dataset_ids" {
  description = "Medallion dataset IDs."
  value       = { for key, dataset in module.datasets : key => dataset.dataset_id }
}