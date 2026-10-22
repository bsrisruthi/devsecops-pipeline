# Technical Deep Dive - DevSecOps Pipeline

This document provides detailed technical explanations for each component of the DevSecOps pipeline. Use this to prepare for technical discussions and to understand the "why" behind each design decision.

---

## Table of Contents

1. [Phase 1: Secret Scanning](#phase-1-secret-scanning)
2. [Phase 2: Container Vulnerability Scanning](#phase-2-container-vulnerability-scanning)
3. [Phase 3: Infrastructure as Code Scanning](#phase-3-infrastructure-as-code-scanning)
4. [Phase 4: Notification Automation](#phase-4-notification-automation)
5. [Phase 5: GitOps Continuous Delivery](#phase-5-gitops-continuous-delivery)
6. [Phase 6: Secrets Management](#phase-6-secrets-management)
7. [Phase 7: Runtime Policy Enforcement](#phase-7-runtime-policy-enforcement)
8. [Phase 8: Observability & Monitoring](#phase-8-observability--monitoring)
9. [Architecture Decisions](#architecture-decisions)
10. [Security Model](#security-model)

---

## Phase 1: Secret Scanning

### Technology: TruffleHog

**What it does:**
Scans filesystems and git repositories for leaked credentials using pattern matching and entropy detection.

**How it works:**
1. **Pattern Matching**: Uses regex patterns to detect API keys, tokens, passwords
2. **Entropy Detection**: Identifies high-entropy strings that look like secrets
3. **Verification**: Attempts to verify secrets with actual services (GitHub tokens, AWS keys)
4. **Categorization**: Marks findings as "Verified" (confirmed real) or "Unverified" (possible false positive)

**Implementation Details:**

```yaml
- name: Run TruffleHog
  run: |
    docker run --rm -v "$PWD:/scan" ghcr.io/trufflesecurity/trufflehog:latest \
      filesystem /scan/devsecops --fail --json
```

**Key Configuration Choices:**

- `filesystem` scan (not `git`): Avoids "BASE and HEAD commits are the same" error
- Scans only `/scan/devsecops` directory: Excludes `.git` metadata which contains GitHub URLs that trigger false positives
- `--fail` flag: Returns non-zero exit code when secrets found (fails the pipeline)
- `--json` output: Machine-readable format for potential future processing

**Common Issues Solved:**

**Problem:** TruffleHog detected GitHub URL in `.git/config` as a secret  
**Solution:** Scoped scan to only application code directory, not entire repo

**Problem:** "flag 'fail' cannot be repeated" error  
**Solution:** Used direct docker run command instead of GitHub Action with `extra_args`

**Technical Talking Points:**

- "TruffleHog uses both pattern matching and entropy analysis. Pattern matching catches known formats like AWS keys (AKIA...), while entropy detection finds high-randomness strings that might be custom secrets."
- "I configured it for filesystem scanning rather than git diff scanning to ensure every file is checked, not just changed files. This provides complete coverage even on the first scan."
- "The verification feature is powerful—it actually tests GitHub tokens against the API to confirm they're real, reducing false positive fatigue."

---

## Phase 2: Container Vulnerability Scanning

### Technology: Trivy

**What it does:**
Scans container images for known vulnerabilities (CVEs) in OS packages and application dependencies.

**How it works:**
1. **Layer Analysis**: Extracts each layer of the Docker image
2. **Package Detection**: Identifies installed packages (apt, apk, pip, npm, etc.)
3. **CVE Database Lookup**: Queries NVD, Red Hat, Debian, Alpine security databases
4. **Severity Scoring**: Uses CVSS scores to classify vulnerabilities (LOW/MEDIUM/HIGH/CRITICAL)
5. **Report Generation**: Outputs findings in various formats (table, JSON, SARIF)

**Implementation Details:**

```yaml
- name: Build Docker image
  run: docker build -t health-app:test ./devsecops/health-app

- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: 'health-app:test'
    format: 'table'
    exit-code: '1'
    severity: 'CRITICAL'
```

**Key Configuration Choices:**

- **severity: 'CRITICAL'**: Only fails on critical vulnerabilities
  - **Why?** Initial scan showed 44 HIGH vulnerabilities. Fixing all would delay deployment for months.
  - **Risk-based approach**: Focus on critical issues first, track others in backlog
  - Production would likely be 'CRITICAL,HIGH' after initial hardening

- **format: 'table'**: Human-readable output in pipeline logs
  - Alternative: JSON for automated processing

- **exit-code: '1'**: Fails pipeline when vulnerabilities found
  - Enforces "don't ship vulnerable code" policy

**Technical Talking Points:**

- "Trivy checks multiple sources—not just NVD, but also vendor-specific databases like Red Hat and Alpine. This gives better coverage than tools that only use NVD."
- "I tuned it to fail only on CRITICAL vulnerabilities. In the initial scan, we had 44 HIGH and 0 CRITICAL. Blocking on HIGH would have required fixing dependencies that might not have patches available yet. This is risk-based prioritization—critical issues are true security emergencies, while high issues can be tracked and fixed in sprint work."
- "Trivy scans both OS packages (from the base image) and application dependencies (from pip, npm, etc.). This means updating Python packages in requirements.txt also gets scanned, not just the base OS layer."

---

## Phase 3: Infrastructure as Code Scanning

### Technology: Checkov

**What it does:**
Scans Terraform, CloudFormation, Kubernetes YAML, and other IaC files for security misconfigurations and compliance violations.

**How it works:**
1. **Policy Library**: Maintains 1000+ built-in policies based on CIS benchmarks, compliance standards
2. **Graph Analysis**: Builds a resource graph to check cross-resource relationships
3. **Policy Evaluation**: Runs policies against the parsed configuration
4. **Severity Classification**: Tags findings as LOW/MEDIUM/HIGH/CRITICAL

**Implementation Details:**

```yaml
- name: Run Checkov IaC scanner
  uses: bridgecrewio/checkov-action@master
  with:
    directory: devsecops/terraform
    framework: terraform
    soft_fail: false
    output_format: cli
    check: CKV2_AWS_6,CKV_AWS_93
```

**Key Configuration Choices:**

- **check parameter (not skip_check)**: 
  - **Initial approach**: Used `skip_check` to ignore low-priority findings
  - **Problem**: New policies kept appearing (CKV2_AWS_62, CKV_AWS_144, etc.)
  - **Solution**: Switched to `check` to only enforce critical policies
  - **Allows**: Focus on what matters (encryption, public access)

- **Policies Enforced**:
  - **CKV2_AWS_6**: S3 bucket must have public access block configured
  - **CKV_AWS_93**: S3 bucket must have encryption enabled

- **soft_fail: false**: Pipeline fails on policy violations

**Technical Talking Points:**

- "Checkov initially flagged 50+ issues including versioning, lifecycle policies, logging, MFA delete, and more. Many were 'nice to have' rather than critical security issues. I focused enforcement on the two policies that prevent data breaches: encryption at rest and blocking public access."
- "The switch from skip_check to check was important. With skip_check, I was playing whack-a-mole—every Checkov update added new policies I had to explicitly skip. With check, I'm explicitly allowing only the policies I care about, which is more maintainable."
- "Checkov does graph analysis, not just individual resource checks. For example, CKV2_AWS_6 checks that the public access block resource exists AND is correctly associated with the S3 bucket. Single-resource scanners would miss that relationship."

---

## Phase 4: Notification Automation

### Technology: Discord Webhooks

**What it does:**
Sends pipeline status notifications to a Discord channel with rich formatting and direct links to pipeline runs.

**How it works:**
1. **Job Dependencies**: Uses `needs` to depend on all scan jobs
2. **Conditional Execution**: `if: always()` ensures notification runs even on failure
3. **Status Collection**: Reads `${{ needs.job-name.result }}` for each job
4. **Discord Embed**: Formats message with color coding and structured fields
5. **HTTP POST**: Sends JSON payload to Discord webhook URL

**Implementation Details:**

```python
def create_discord_message(status_summary, repo, run_id, actor, ref):
    # Determine overall color (green/red/yellow)
    if all(s == "success" for s in status_summary.values()):
        color = 0x00FF00  # Green
    elif any(s == "failure" for s in status_summary.values()):
        color = 0xFF0000  # Red
    else:
        color = 0xFFA500  # Yellow (warnings)
    
    # Build embed with fields
    fields = [
        {"name": "Secret Scan", "value": f"{emoji} {status}", "inline": True},
        {"name": "Container Scan", "value": f"{emoji} {status}", "inline": True},
        {"name": "IaC Scan", "value": f"{emoji} {status}", "inline": True},
    ]
    
    # Add action link
    embed["fields"].append({
        "name": "Pipeline Run",
        "value": f"[View Details](https://github.com/{repo}/actions/runs/{run_id})"
    })
```

**Technical Talking Points:**

- "The notification runs with `if: always()` which means it executes even when previous jobs fail. This is critical—you need to know when the pipeline breaks, not just when it succeeds."
- "I used Discord instead of email or Slack because Discord webhooks don't require authentication or complex setup. In production, this would be Slack with proper workspace integration."
- "The color coding provides instant visual feedback—green means all scans passed, red means something failed. The embed format is more useful than plain text because it structures the information: which scan failed, who triggered it, direct link to logs."

---

## Phase 5: GitOps Continuous Delivery

### Technology: ArgoCD

**What it does:**
Continuously monitors a Git repository and automatically synchronizes Kubernetes cluster state with the desired state defined in Git.

**How it works:**
1. **Git Polling**: Checks repository every 3 minutes for changes
2. **State Comparison**: Compares live cluster state with Git definitions
3. **Drift Detection**: Identifies resources that don't match Git
4. **Automated Sync**: Applies changes to bring cluster in sync
5. **Health Assessment**: Monitors resource health (Running, Healthy, Degraded)

**Implementation Details:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: health-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/bsrisruthi/devsecops-pipeline.git
    targetRevision: HEAD
    path: devsecops/k8s
  destination:
    server: https://kubernetes.default.svc
    namespace: health-app
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

**Key Configuration Choices:**

- **automated.selfHeal: true**: Automatically corrects drift
  - If someone runs `kubectl delete pod`, ArgoCD recreates it
  - Enforces "Git is the source of truth"

- **automated.prune: true**: Deletes resources removed from Git
  - Prevents orphaned resources

- **imagePullPolicy: Always** in deployment:
  - Kubernetes caches images tagged with `:latest`
  - Without this, pods wouldn't pull updated images
  - **Issue discovered**: Pushed new image, pods showed old code
  - **Solution**: Added `imagePullPolicy: Always` to force fresh pulls

**GitOps Benefits:**

1. **Audit Trail**: Every change has a Git commit (who, what, when, why)
2. **Rollback**: `git revert` to undo deployments
3. **Consistency**: Dev/staging/prod use same deployment method
4. **Disaster Recovery**: Rebuild entire cluster from Git

**Technical Talking Points:**

- "GitOps means Git is the single source of truth. Every deployment goes through a Git commit, which provides an audit trail and rollback capability. Direct kubectl apply bypasses this and should only be used for debugging."
- "The selfHeal feature is powerful. If someone accidentally deletes a pod or modifies a ConfigMap, ArgoCD detects the drift within 3 minutes and automatically corrects it. This prevents configuration drift where live state diverges from documented state."
- "I hit an interesting issue with imagePullPolicy. Kubernetes caches images tagged 'latest', so even after pushing a new image with the same tag, pods didn't pull it. Setting imagePullPolicy to Always forces the kubelet to always pull, which is necessary for the :latest tag pattern."
- "ArgoCD's health assessment is more sophisticated than just checking if pods are Running. It waits for liveness probes to succeed and checks that the Deployment has reached the desired replica count. This prevents marking a deployment as successful when pods are crash-looping."

---

## Phase 6: Secrets Management

### Technology: HashiCorp Vault

**What it does:**
Centralized secrets storage with versioning, access control, and audit logging. Secrets are fetched at runtime rather than being baked into images or configuration files.

**How it works:**
1. **Secret Storage**: KV v2 engine stores key-value pairs with versioning
2. **Authentication**: Application authenticates with token (or K8s service account in production)
3. **Runtime Fetch**: App makes HTTP API call to Vault on startup
4. **Secret Injection**: Values loaded into memory, never written to disk

**Implementation Details:**

**Vault Setup:**
```bash
# Store secrets in Vault
kubectl exec -n vault vault-0 -- vault kv put secret/health-app/config \
  api_key="prod-api-key-12345" \
  db_password="secure-password-67890"
```

**Application Code:**
```python
import hvac
import os

VAULT_ADDR = os.getenv('VAULT_ADDR', 'http://host.docker.internal:8200')
VAULT_TOKEN = os.getenv('VAULT_TOKEN', 'myroot')

def get_secret_from_vault():
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    secret = client.secrets.kv.v2.read_secret_version(
        path='health-app/config',
        mount_point='secret'
    )
    return secret['data']['data']
```

**Deployment Configuration:**
```yaml
env:
- name: VAULT_ADDR
  value: "http://host.docker.internal:8200"
- name: VAULT_TOKEN
  value: "myroot"
```

**Key Separation:**

| What | Where | Why |
|------|-------|-----|
| **Secrets** (API keys, passwords) | Vault | Sensitive, needs rotation, audit |
| **Configuration** (Vault address, token) | deployment.yaml | Connection info, not secret itself |
| **Application Code** | Docker image | Logic, no sensitive data |

**Technical Talking Points:**

- "The key distinction is between secrets and configuration. The deployment.yaml has VAULT_ADDR and VAULT_TOKEN, which are connection credentials. The actual secrets—API keys and database passwords—live only in Vault. This follows the 12-factor app principle of separating config from code."
- "Secrets are fetched at runtime, not build time. This means I can rotate a database password in Vault, restart the pod, and it picks up the new value—without rebuilding the Docker image or updating any Git files."
- "In production, we wouldn't use a static VAULT_TOKEN. We'd use Kubernetes service account authentication where Vault issues short-lived tokens based on the pod's identity. But for demonstration, static token shows the integration pattern."
- "Vault's KV v2 engine provides versioning. If I accidentally overwrite a secret, I can retrieve an older version. It also provides audit logs showing who accessed which secrets and when."

**Common Confusion:**

**Q: "How did the secret get into Vault?"**  
**A:** Manual `vault kv put` command. In production, this would be:
- Automated via Terraform with Vault provider
- Or, provisioned by a secrets management team
- Or, integrated with external secret stores (AWS Secrets Manager, Azure Key Vault)

**Q: "Isn't VAULT_TOKEN a secret?"**  
**A:** Yes, but it's a *credential* not an *application secret*. Think of it like a username/password to access a database—it's sensitive but it's connection info, not the data itself. Production uses short-lived tokens.

---

## Phase 7: Runtime Policy Enforcement

### Technology: Kyverno

**What it does:**
Kubernetes-native policy engine that validates, mutates, and generates Kubernetes resources at admission time.

**How it works:**
1. **Admission Webhook**: Intercepts API requests before resources are persisted to etcd
2. **Policy Evaluation**: Runs policies against the requested resource
3. **Validation**: Checks if resource matches or violates policy patterns
4. **Action**: Either allows creation (compliant) or blocks with error message (non-compliant)

**Implementation Details:**

**Policy 1: Require Resource Limits**
```yaml
validate:
  message: "All containers must have CPU and memory limits defined."
  pattern:
    spec:
      containers:
      - resources:
          limits:
            memory: "?*"  # ?* means "must exist, any value"
            cpu: "?*"
```

**Why this matters:**
- Without limits, a single pod can exhaust node resources
- Causes cluster instability and impacts other workloads
- Limits enable the scheduler to make intelligent placement decisions

**Policy 2: Block Root Containers**
```yaml
validate:
  message: "Containers must run as non-root user."
  pattern:
    spec:
      containers:
      - securityContext:
          runAsNonRoot: true
```

**Why this matters:**
- Root in container = root on host (with kernel exploits)
- Limits blast radius of container escape vulnerabilities
- Defense-in-depth: even if app is compromised, attacker has limited privileges

**Policy 3: Require Labels**
```yaml
validate:
  message: "Resources must have 'app' and 'env' labels."
  pattern:
    metadata:
      labels:
        app: "?*"
        env: "?*"
```

**Why this matters:**
- Labels enable monitoring, cost tracking, RBAC policies
- `app` label: Which application does this belong to?
- `env` label: Is this dev, staging, or prod?

**Namespace Exclusions:**
```yaml
exclude:
  any:
  - resources:
      namespaces:
      - kube-system
      - monitoring
      - kyverno
```

**Why needed:**
- Infrastructure components legitimately need elevated privileges
- Prometheus admission webhooks run as root to generate certificates
- Node exporters need host access for metrics collection
- Policy enforcement is for application workloads, not trusted infrastructure

**Technical Talking Points:**

- "Kyverno runs at the Kubernetes admission control layer, which means it validates resources before they're created. This is different from Checkov which scans files in CI/CD. Someone could bypass the CI/CD pipeline and run kubectl apply directly, but they can't bypass Kyverno—it's enforced at the API level."
- "The namespace exclusions are a pragmatic decision. Infrastructure components like Prometheus need elevated privileges for legitimate reasons—generating TLS certificates, collecting node metrics, etc. The alternative would be creating exception policies for every infrastructure component, which is maintenance-heavy and error-prone. Instead, we trust infrastructure namespaces and enforce strict policies on application namespaces."
- "One interesting learning: Kyverno validates the YAML structure, not runtime behavior. I created a pod with nginx that passed all policies—non-root user, resource limits, required labels—but it crashed because nginx needs root to bind to port 80. Kyverno said 'this YAML is compliant' but the container couldn't actually start. This shows the difference between admission-time validation and runtime enforcement."
- "The pattern matching uses ?* which means 'must exist with any value'. This validates that a limit is set, but doesn't enforce what the limit should be. For more strict policies, you could set ranges like memory: '>64Mi & <2Gi'."

---

## Phase 8: Observability & Monitoring

### Technology: Prometheus + Grafana

**What it does:**
- **Prometheus**: Time-series database that scrapes metrics from targets at regular intervals
- **Grafana**: Visualization platform for creating dashboards and alerts

**How it works:**

**1. Metric Instrumentation (Application Side)**
```python
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
metrics = PrometheusMetrics(app)
```

This automatically creates metrics:
- `flask_http_request_total` - Total requests
- `flask_http_request_duration_seconds` - Response time histogram
- `flask_exporter_info` - Exporter version

**2. Metric Exposure**
Application exposes `/metrics` endpoint in Prometheus format:
```
# HELP flask_http_request_total Total number of HTTP requests
# TYPE flask_http_request_total counter
flask_http_request_total{method="GET",status="200"} 36.0

# HELP flask_http_request_duration_seconds Flask HTTP request duration in seconds
# TYPE flask_http_request_duration_seconds histogram
flask_http_request_duration_seconds_bucket{le="0.005",method="GET",path="/health",status="200"} 34.0
```

**3. Target Discovery (ServiceMonitor)**
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: health-app-monitor
  namespace: health-app
spec:
  selector:
    matchLabels:
      app: health-app
  endpoints:
  - port: metrics
    path: /metrics
    interval: 15s
```

ServiceMonitor tells Prometheus:
- **Where**: Look for services with label `app=health-app`
- **How**: Scrape the `metrics` port at path `/metrics`
- **When**: Every 15 seconds

**4. Scraping (Prometheus)**
- Prometheus discovers targets via ServiceMonitors
- Makes HTTP GET requests to `/metrics` every 15 seconds
- Parses Prometheus text format
- Stores time-series data with timestamps

**5. Querying (PromQL)**
```promql
# Request rate (requests per second)
rate(flask_http_request_total[5m])

# Average response time
rate(flask_http_request_duration_seconds_sum[5m]) / 
rate(flask_http_request_duration_seconds_count[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(flask_http_request_duration_seconds_bucket[5m]))
```

**6. Visualization (Grafana)**
- Connects to Prometheus as data source
- Queries metrics using PromQL
- Renders as time-series graphs, gauges, tables
- Supports alerts based on thresholds

**Technical Talking Points:**

- "Prometheus uses a pull model, not push. The application doesn't send metrics to Prometheus; Prometheus scrapes the /metrics endpoint. This is more reliable because Prometheus controls the scraping schedule and can detect when targets are down."
- "The histogram metric type is important for latency. Instead of just an average response time (which hides outliers), histograms let you calculate percentiles—like the 95th percentile latency, which shows what most users experience, not just the average."
- "ServiceMonitor is part of the Prometheus Operator pattern. Instead of manually configuring Prometheus scrape targets, I create a ServiceMonitor and Prometheus automatically discovers it. This is infrastructure-as-code for monitoring—add a ServiceMonitor via GitOps and monitoring is automatically configured."
- "The 15-second scrape interval is configurable. More frequent scraping (5s) gives better granularity for debugging but increases storage and CPU usage. Less frequent (60s) reduces overhead but you might miss short-lived issues. 15s is a good balance."

**Metrics vs Logs vs Traces:**

| Type | Use Case | Example |
|------|----------|---------|
| **Metrics** | Aggregated numbers | Requests/sec, error rate, latency |
| **Logs** | Discrete events | "User X logged in", "Database query failed" |
| **Traces** | Request flows | Request → API → Database → Cache → Response |

This project implements metrics. Full observability would add:
- **Logs**: Structured logging with Loki or ELK stack
- **Traces**: Distributed tracing with Jaeger or Zipkin

---

## Architecture Decisions

### Why KIND Instead of Minikube or Cloud?

**Chosen: KIND (Kubernetes in Docker)**

**Advantages:**
- ✅ Fast startup (seconds, not minutes)
- ✅ Lightweight (single Docker container)
- ✅ Runs on Mac, Windows, Linux
- ✅ Identical to production Kubernetes (not a simplified version)
- ✅ Free

**Alternatives:**
- **Minikube**: Heavier (full VM), slower startup
- **Cloud (EKS/GKE/AKS)**: Costs money, requires cloud account, network latency
- **Docker Desktop K8s**: Good alternative, but less portable (requires Docker Desktop)

---

### Why GitHub Actions Instead of Jenkins/GitLab CI?

**Chosen: GitHub Actions**

**Advantages:**
- ✅ Native GitHub integration (no webhook setup)
- ✅ Marketplace of pre-built actions (trivy-action, checkov-action)
- ✅ Free for public repositories
- ✅ YAML configuration (easy to read/modify)
- ✅ Matrix builds, reusable workflows, caching built-in

**When Jenkins is Better:**
- Self-hosted requirement (air-gapped environments)
- Complex pipeline logic (Groovy scripting)
- Heavy customization needs
- Existing Jenkins infrastructure

---

### Why Discord Instead of Slack/Email?

**Chosen: Discord Webhooks**

**Advantages:**
- ✅ No authentication required (webhook URL is the credential)
- ✅ Rich embed support (colors, fields, images)
- ✅ Free, unlimited webhooks
- ✅ Easy to test (no corporate approval needed)

**Production Would Use:**
- Slack (enterprise standard)
- PagerDuty (on-call alerts)
- OpsGenie (incident management)

---

### Why Kyverno Instead of OPA Gatekeeper?

**Chosen: Kyverno**

**Advantages:**
- ✅ Kubernetes-native (YAML policies, not Rego)
- ✅ Easier to learn (no new language)
- ✅ Built-in policies library
- ✅ Faster to implement for Kubernetes-specific policies

**OPA Gatekeeper Better For:**
- Cross-platform policies (Kubernetes + Terraform + Envoy)
- Complex logic requiring Rego's expressiveness
- Need for unit testing policies

---

## Security Model

### Shift-Left Security

**Concept:** Catch security issues as early as possible in the development lifecycle.

```
Earlier Detection = Cheaper Fix + Less Risk

Git Commit → CI/CD Scans (Minutes, $0) ✅
    vs
Production Incident → SOC Response (Hours, $$$) ❌
```

**Implementation:**
- Phase 1-3: Security scans in CI/CD (shift-left)
- Phase 7: Runtime enforcement (defense in depth)

---

### Defense in Depth

**Concept:** Multiple independent security layers so that failure of one doesn't compromise the system.

**Layers in This Project:**

1. **Secret Scanning (TruffleHog)**: Prevents leaked credentials in code
2. **Container Scanning (Trivy)**: Prevents vulnerable dependencies from being packaged
3. **IaC Scanning (Checkov)**: Prevents misconfigured infrastructure from being provisioned
4. **Admission Control (Kyverno)**: Prevents non-compliant workloads from running
5. **Runtime Security (securityContext)**: Limits blast radius of compromised containers
6. **Secrets Management (Vault)**: Prevents secrets from existing in code/images/configs
7. **Network Policies (Not Implemented)**: Would prevent pod-to-pod lateral movement

**Why Both Checkov and Kyverno?**
- Checkov: Scans files in Git (shift-left, can be bypassed with kubectl)
- Kyverno: Enforces at API level (runtime, cannot be bypassed)
- **Together**: Defense in depth

---

### Least Privilege

**Concept:** Give only the minimum permissions required to function.

**Implementation:**

**Container Level:**
```yaml
securityContext:
  runAsNonRoot: true        # Can't run as UID 0
  runAsUser: 1000           # Specific non-root UID
  allowPrivilegeEscalation: false  # Can't gain more privileges
  capabilities:
    drop:
    - ALL                   # Drop all Linux capabilities
```

**Namespace Level:**
- Application workloads in `health-app` namespace
- Infrastructure in separate namespaces (monitoring, argocd, vault)
- Kyverno policies enforce separation

---

## Key Takeaways

### What This Project Demonstrates

✅ **End-to-End Automation**: From code commit to production deployment, fully automated  
✅ **Security at Every Stage**: Scanning, policy enforcement, secrets management  
✅ **GitOps Principles**: Git as source of truth, declarative configuration  
✅ **Cloud-Native Patterns**: Kubernetes, microservices, observability  
✅ **Production Practices**: Health checks, rolling updates, monitoring  
✅ **Tool Integration**: 8 different tools working together seamlessly  

### What's Missing (Production Considerations)

- **Multi-environment setup**: Separate dev/staging/prod clusters
- **RBAC**: Role-based access control for developers
- **Network policies**: Pod-to-pod traffic restrictions
- **Image signing**: Cosign/Notary for supply chain security
- **SBOM generation**: Software bill of materials for compliance
- **Log aggregation**: Centralized logging with Loki/ELK
- **Distributed tracing**: Jaeger/Zipkin for request flows
- **Chaos engineering**: Simulate failures to test resilience
- **Backup/DR**: Velero for cluster backups

---

**This is a learning project demonstrating DevSecOps principles. Real production systems would have additional layers of security, redundancy, and operational tooling.**
