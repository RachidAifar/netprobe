variable "cluster_name" {
  description = "Name of the local kind cluster."
  type        = string
  default     = "netprobe"
}

variable "kubernetes_version" {
  description = "kindest/node image tag, i.e. the Kubernetes version of the cluster."
  type        = string
  default     = "v1.33.1"
}

variable "repo_url" {
  description = "Git repository Argo CD watches."
  type        = string
  default     = "https://github.com/RachidAifar/netprobe.git"
}

variable "overlay_path" {
  description = "Kustomize overlay Argo CD deploys."
  type        = string
  default     = "deploy/k8s/overlays/dev"

  validation {
    condition     = can(regex("^deploy/k8s/overlays/[a-z]+$", var.overlay_path))
    error_message = "overlay_path must point to one of the overlays in deploy/k8s/overlays."
  }
}

variable "grafana_admin_password" {
  description = "Grafana admin password for the local cluster."
  type        = string
  default     = "netprobe-local"
  sensitive   = true
}
