output "kubeconfig_path" {
  description = "Use with: export KUBECONFIG=<path>"
  value       = kind_cluster.this.kubeconfig_path
}

output "next_steps" {
  description = "How to reach the tools."
  value       = <<-EOT
    export KUBECONFIG=${kind_cluster.this.kubeconfig_path}
    kubectl -n argocd get applications
    kubectl -n argocd port-forward svc/argocd-server 8081:443          # https://localhost:8081
    kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
    kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80   # admin / grafana_admin_password
    kubectl -n netprobe port-forward svc/netprobe 8080:80
  EOT
}
