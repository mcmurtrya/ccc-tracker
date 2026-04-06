variable "aws_region" {
  description = "AWS region for the EKS cluster (control plane runs across 3 AZs — equivalent to HA masters)."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "citycouncil-prod"
}

variable "cluster_version" {
  description = "Kubernetes version (1.28+)."
  type        = string
  default     = "1.28"
}

variable "worker_desired_size" {
  description = "Target worker node count (ticket: 6 workers)."
  type        = number
  default     = 6
}

variable "worker_instance_types" {
  description = "EC2 instance types for managed node group."
  type        = list(string)
  default     = ["m5.large"]
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "tags" {
  description = "Tags applied to supported resources."
  type        = map(string)
  default     = {}
}
