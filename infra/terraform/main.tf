# Local GitOps platform: a kind cluster with Argo CD and kube-prometheus-stack.
# Argo CD then deploys NetProbe from this repository and keeps it in sync.

resource "kind_cluster" "this" {
  name            = var.cluster_name
  node_image      = "kindest/node:${var.kubernetes_version}"
  wait_for_ready  = true
  kubeconfig_path = pathexpand("~/.kube/kind-${var.cluster_name}")

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    node {
      role = "control-plane"
    }
    node {
      role = "worker"
    }
  }
}

provider "helm" {
  kubernetes {
    host                   = kind_cluster.this.endpoint
    client_certificate     = kind_cluster.this.client_certificate
    client_key             = kind_cluster.this.client_key
    cluster_ca_certificate = kind_cluster.this.cluster_ca_certificate
  }
}

resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  version          = "92.16.2"
  namespace        = "monitoring"
  create_namespace = true
  timeout          = 600

  values = [yamlencode({
    grafana = {
      adminPassword = var.grafana_admin_password
    }
    prometheus = {
      prometheusSpec = {
        # Pick up ServiceMonitors and rules from every namespace, not only this release.
        serviceMonitorSelectorNilUsesHelmValues = false
        ruleSelectorNilUsesHelmValues           = false
      }
    }
  })]
}

resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "10.9.6"
  namespace        = "argocd"
  create_namespace = true
  timeout          = 600
}

# The Argo CD Application, installed through the argocd-apps chart so it is created
# only after the Argo CD CRDs exist.
resource "helm_release" "netprobe_app" {
  name       = "netprobe-app"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argocd-apps"
  version    = "2.0.6"
  namespace  = "argocd"

  values = [yamlencode({
    applications = {
      netprobe = {
        namespace = "argocd"
        project   = "default"
        source = {
          repoURL        = var.repo_url
          targetRevision = "main"
          path           = var.overlay_path
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "netprobe"
        }
        syncPolicy = {
          automated   = { prune = true, selfHeal = true }
          syncOptions = ["CreateNamespace=true"]
        }
      }
    }
  })]

  depends_on = [helm_release.argocd, helm_release.kube_prometheus_stack]
}
