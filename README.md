# DevSecOps Pipeline - Complete Security Automation

A production-grade DevSecOps pipeline implementing security automation, GitOps continuous delivery, secrets management, runtime policy enforcement, and observability monitoring.

![Pipeline Status](https://img.shields.io/badge/pipeline-passing-brightgreen)
![Security](https://img.shields.io/badge/security-hardened-blue)
![Kubernetes](https://img.shields.io/badge/kubernetes-1.27+-326CE5?logo=kubernetes)
![License](https://img.shields.io/badge/license-MIT-green)

## 🎯 Project Overview

This project demonstrates a complete DevSecOps workflow from code commit to production deployment, incorporating security scanning at every stage, automated GitOps deployment, runtime policy enforcement, and comprehensive monitoring.

**Built for:** International job applications showcasing DevSecOps expertise  
**Tech Stack:** GitHub Actions, TruffleHog, Trivy, Checkov, ArgoCD, HashiCorp Vault, Kyverno, Prometheus, Grafana, Kubernetes  
**Deployment:** KIND (Kubernetes in Docker) cluster for local demonstration

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Developer pushes code to GitHub                        │
└────────────────┬────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 1-4: CI Pipeline (GitHub Actions)                │
│  ├─ Secret Scanning (TruffleHog)                        │
│  ├─ Container Vulnerability Scanning (Trivy)            │
│  ├─ Infrastructure as Code Scanning (Checkov)           │
│  └─ Notification (Discord Webhook)                      │
└────────────────┬────────────────────────────────────────┘
                 ↓ (All scans pass)
┌─────────────────────────────────────────────────────────┐
│  Phase 5: Continuous Deployment (ArgoCD)                │
│  ├─ GitOps: Monitors Git repository                     │
│  ├─ Auto-sync on changes detected                       │
│  └─ Rolling updates (zero downtime)                     │
└────────────────┬────────────────────────────────────────┘
                 ↓ (Deployment requested)
┌─────────────────────────────────────────────────────────┐
│  Phase 7: Admission Control (Kyverno)                   │
│  ├─ Validates resource limits                           │
│  ├─ Blocks root containers                              │
│  ├─ Enforces required labels                            │
│  └─ Rejects non-compliant resources                     │
└────────────────┬────────────────────────────────────────┘
                 ↓ (Policy validation passed)
┌─────────────────────────────────────────────────────────┐
│  Phase 6: Runtime (Application in Kubernetes)           │
│  ├─ Fetches secrets from Vault at runtime              │
│  ├─ Runs as non-root user (UID 1000)                   │
│  ├─ Resource limits enforced                            │
│  └─ Exposes /metrics for monitoring                     │
└────────────────┬────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 8: Observability (Prometheus + Grafana)          │
│  ├─ Prometheus scrapes metrics every 15s               │
│  ├─ Grafana visualizes request rates, latency          │
│  └─ Real-time monitoring dashboards                     │
└─────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Features

### Shift-Left Security (CI/CD Pipeline)

**1. Secret Scanning (TruffleHog)**
- Scans filesystem for leaked credentials, API keys, tokens
- Uses pattern matching and entropy detection
- Blocks commits containing verified secrets
- Configured to scan only application code (excludes `.git` metadata)

**2. Container Vulnerability Scanning (Trivy)**
- Scans Docker images for CVEs in OS packages and application dependencies
- Configured to fail on CRITICAL severity vulnerabilities
- Integrates with CVE databases (NVD, Red Hat, Debian, Alpine)
- Generates detailed vulnerability reports

**3. Infrastructure as Code Scanning (Checkov)**
- Validates Terraform configurations against CIS benchmarks
- Enforces critical policies: S3 bucket encryption, public access blocks
- Focused checks rather than exhaustive scanning (reduces noise)
- Policy-as-code approach for infrastructure security

### Runtime Security

**4. Admission Control (Kyverno)**
- Kubernetes-native policy engine
- Enforces security standards at API admission time
- Policies implemented:
  - **require-resource-limits**: Prevents resource exhaustion
  - **block-root-containers**: Requires runAsNonRoot=true
  - **require-labels**: Enforces app and env labels for tracking
- Namespace exclusions for infrastructure components

**5. Secrets Management (HashiCorp Vault)**
- Centralized secrets storage (KV v2 engine)
- Secrets fetched at runtime, never baked into images
- Environment variables provide connection info only
- Follows 12-factor app methodology

---

## 🚀 GitOps Continuous Delivery

**ArgoCD Implementation**
- Git repository as single source of truth
- Auto-sync enabled with 3-minute polling interval
- Self-healing: automatically corrects configuration drift
- Declarative Kubernetes manifests
- `imagePullPolicy: Always` ensures latest image pulls

**Deployment Strategy**
- Rolling updates with 2 replicas
- Zero-downtime deployments
- Health checks via liveness probes
- Kubernetes manages pod lifecycle automatically

---

## 📊 Observability Stack

**Prometheus Metrics Collection**
- ServiceMonitor for automatic target discovery
- Scrapes `/metrics` endpoint every 15 seconds
- Collects application and system metrics:
  - Request rate by endpoint
  - Response time histograms
  - HTTP status codes
  - Python process metrics (CPU, memory)

**Grafana Dashboards**
- Real-time visualization of application health
- Custom dashboards for:
  - Request throughput
  - Average response time
  - Error rates
  - Resource utilization

---

## 🛠️ Technologies Used

| Category | Technology | Purpose |
|----------|-----------|---------|
| **CI/CD** | GitHub Actions | Pipeline orchestration |
| **Secret Scanning** | TruffleHog | Detect leaked credentials |
| **Container Security** | Trivy | CVE scanning for Docker images |
| **IaC Security** | Checkov | Terraform policy enforcement |
| **GitOps** | ArgoCD | Kubernetes continuous delivery |
| **Secrets Management** | HashiCorp Vault | Runtime secret injection |
| **Policy Enforcement** | Kyverno | Kubernetes admission control |
| **Monitoring** | Prometheus | Metrics collection |
| **Visualization** | Grafana | Monitoring dashboards |
| **Orchestration** | Kubernetes (KIND) | Container orchestration |
| **Notifications** | Discord Webhooks | Pipeline status alerts |

---

## 📁 Project Structure

```
devsecops/
├── .github/
│   └── workflows/
│       └── security-scan.yml          # CI pipeline definition
├── devsecops/
│   ├── health-app/
│   │   ├── app.py                     # Flask application with Vault integration
│   │   ├── requirements.txt           # Python dependencies
│   │   └── Dockerfile                 # Multi-stage container build
│   ├── k8s/
│   │   ├── deployment.yaml            # Kubernetes deployment (Kyverno-compliant)
│   │   ├── service.yaml               # ClusterIP service
│   │   ├── servicemonitor.yaml        # Prometheus scraping config
│   │   └── namespace.yaml             # health-app namespace
│   ├── kyverno-policies/
│   │   ├── require-resource-limits.yaml
│   │   ├── block-root-containers.yaml
│   │   └── require-labels.yaml
│   ├── terraform/
│   │   └── main.tf                    # AWS S3 bucket (compliant)
│   └── scripts/
│       ├── notify.py                  # Discord notification script
│       └── requirements.txt           # Script dependencies
├── README.md
├── TECHNICAL_GUIDE.md
├── RESUME_BULLETS.md
└── ARCHITECTURE.md
```

---

## 🚦 CI/CD Pipeline Flow

**Trigger:** Push to `main` or Pull Request

**Jobs:**
1. **secret-scan**
   - Checks out code with full git history (`fetch-depth: 0`)
   - Runs TruffleHog filesystem scan
   - Fails on verified secrets found

2. **container-scan** (depends on: secret-scan)
   - Builds Docker image
   - Runs Trivy vulnerability scanner
   - Fails on CRITICAL vulnerabilities

3. **iac-scan** (depends on: container-scan)
   - Runs Checkov on Terraform files
   - Enforces critical policies (CKV2_AWS_6, CKV_AWS_93)
   - Fails on policy violations

4. **notify** (depends on: all, runs always)
   - Sends Discord notification with scan results
   - Color-coded embeds (green=success, red=failure)
   - Includes direct link to pipeline run

---

## 🔧 Local Setup

### Prerequisites
- Docker Desktop
- KIND (Kubernetes in Docker)
- kubectl
- Helm
- Git

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/bsrisruthi/devsecops-pipeline.git
cd devsecops-pipeline

# 2. Create KIND cluster
kind create cluster --name devsecops

# 3. Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 4. Install Kyverno
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno --namespace kyverno --create-namespace

# 5. Apply Kyverno policies
kubectl apply -f devsecops/kyverno-policies/

# 6. Install Prometheus stack
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false

# 7. Install Vault
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault --namespace vault --create-namespace \
  --set "server.dev.enabled=true"

# 8. Configure Vault secrets
kubectl exec -n vault vault-0 -- vault kv put secret/health-app/config \
  api_key="prod-api-key-12345" \
  db_password="secure-password-67890"

# 9. Deploy application via ArgoCD
kubectl apply -f argocd-app.yaml

# 10. Access services
kubectl port-forward -n health-app svc/health-app 5000:80
kubectl port-forward -n argocd svc/argocd-server 8080:443
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
```

---

## 🧪 Testing the Pipeline

### Test Secret Scanning
```bash
# This should FAIL (secret detected)
echo "aws_access_key_id = AKIAIOSFODNN7EXAMPLE" > test-secret.txt
git add test-secret.txt
git commit -m "Test secret detection"
git push
```

### Test Container Scanning
```bash
# Use a vulnerable base image (should FAIL)
FROM node:14.0.0  # Known vulnerabilities
```

### Test IaC Scanning
```bash
# Remove encryption (should FAIL)
resource "aws_s3_bucket" "app_data" {
  bucket = "my-bucket"
  # Missing: encryption, public access block
}
```

### Test Kyverno Policies
```bash
# This should be BLOCKED
kubectl run bad-pod --image=nginx --namespace=health-app
# Error: violates require-resource-limits and block-root-containers
```

### Test Vault Integration
```bash
kubectl port-forward -n health-app svc/health-app 5000:80
curl http://localhost:5000/secret
# Should return secrets from Vault (api_key visible, db_password hidden)
```

### Test Monitoring
```bash
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Login: admin / <password from secret>
# Dashboard: Health App Monitoring
```

---

## 📈 Key Metrics

**Security Scanning Coverage:**
- ✅ 100% of commits scanned for secrets
- ✅ 100% of container images scanned for vulnerabilities
- ✅ 100% of IaC changes validated against policies

**Policy Enforcement:**
- ✅ 3 Kyverno policies enforced cluster-wide
- ✅ 0 pods running as root in application namespaces
- ✅ 100% of workloads have resource limits

**Deployment Automation:**
- ✅ GitOps: Git as single source of truth
- ✅ Auto-sync enabled with 3-minute polling
- ✅ Zero-downtime rolling updates

**Observability:**
- ✅ Metrics scraped every 15 seconds
- ✅ Real-time dashboards for application health
- ✅ Historical data retention in Prometheus

---

## 🎓 Key Learnings

### Defense in Depth
Implemented multiple security layers rather than relying on a single tool. Checkov catches issues in CI/CD, Kyverno enforces at runtime—bypassing one doesn't bypass the other.

### Policy Tuning
Initial Checkov scans flagged 50+ issues. Focused on critical policies (S3 encryption, public access blocks) rather than creating noise with low-severity findings. Security tools require tuning for production use.

### Namespace Exclusions
Kyverno policies initially blocked infrastructure components (Prometheus, ArgoCD) that legitimately need elevated privileges. Added namespace exclusions for `kube-system`, `monitoring`, `kyverno` while maintaining strict enforcement for application namespaces.

### Image Caching
Kubernetes cached `:latest` tag images and didn't pull updates. Solution: `imagePullPolicy: Always` forces fresh pulls on pod creation.

### Secrets vs Configuration
Vault connection info (VAULT_ADDR, VAULT_TOKEN) lives in deployment manifests as configuration. Actual secrets (API keys, passwords) are fetched at runtime from Vault. This separation is critical for 12-factor apps.

### GitOps Discipline
Every change goes through Git → ArgoCD → Kubernetes. Direct `kubectl apply` bypasses audit trail and GitOps benefits. Exceptions only for debugging.

---

## 🔮 Future Enhancements

- [ ] Add SAST (Static Application Security Testing) with SonarQube
- [ ] Implement DAST (Dynamic Application Security Testing) with OWASP ZAP
- [ ] Add alerting rules to Prometheus/Alertmanager
- [ ] Implement network policies for pod-to-pod communication
- [ ] Add Falco for runtime threat detection
- [ ] Multi-environment setup (dev, staging, prod)
- [ ] Image signing and verification with Cosign
- [ ] SBOM generation with Syft
- [ ] Policy reporting dashboard (Kyverno Policy Reporter)

---

## 📝 License

MIT License - See LICENSE file for details

---

## 👤 Author

**Sri Sruthi**  
Building secure, automated infrastructure for cloud-native applications

- GitHub: [@bsrisruthi](https://github.com/bsrisruthi)
- LinkedIn: [Your LinkedIn Profile]

---

## 🙏 Acknowledgments

- Inspired by production DevSecOps practices at enterprise organizations
- Tool selection aligned with CNCF landscape and industry standards
- Security policies based on CIS Kubernetes Benchmark
- GitOps principles from Weaveworks and ArgoCD community

---

**⭐ If you found this project helpful, please consider giving it a star!**
