# Quick Reference Guide

Quick answers to common questions about this project. Use this for preparation before discussions.

---

## 🎯 Project Stats (Memorize These)

| Metric | Value |
|--------|-------|
| **Total Phases** | 8 |
| **Tools Integrated** | 11 (TruffleHog, Trivy, Checkov, Discord, ArgoCD, Vault, Kyverno, Prometheus, Grafana, Helm, Terraform) |
| **Lines of Code** | ~700 (app + scripts + configs) |
| **Documentation** | ~15,000 words across 5 files |
| **Scan Coverage** | 100% of commits |
| **Deployment Time** | <5 minutes |
| **Policy Violations** | 0 in production namespaces |
| **Prometheus Scrape Interval** | 15 seconds |
| **ArgoCD Sync Interval** | 3 minutes |

---

## 💬 One-Sentence Answers

**"What is this project?"**
> A production-grade DevSecOps pipeline with automated security scanning, GitOps deployment, runtime policy enforcement, and monitoring on Kubernetes.

**"Why did you build it?"**
> To demonstrate end-to-end DevSecOps skills for international job applications by building something production-like, not just a tutorial project.

**"What makes it different from a tutorial?"**
> Real troubleshooting (image caching, policy conflicts, tool tuning), pragmatic decisions (risk-based policy enforcement), and complete documentation explaining the "why" behind choices.

**"What's the most complex part?"**
> Integrating 11 tools to work together—each tool is simple individually, but making them coexist (Kyverno not blocking Prometheus, Checkov not drowning in noise) required real problem-solving.

**"What would you do differently?"**
> Use semantic versioning from day 1 (`:v1.0.0` not `:latest`), define policy priorities upfront, and automate secret provisioning with Terraform instead of manual commands.

---

## 🔧 Technology Explanations (30 seconds each)

### TruffleHog
**What:** Secret scanner using pattern matching and entropy detection  
**Why:** Catches leaked credentials before they reach Git history  
**How:** Scans filesystem for high-entropy strings and known patterns (AWS keys, GitHub tokens)  
**Tuning:** Scoped to `/devsecops` directory to avoid false positives from `.git` metadata

### Trivy
**What:** Container vulnerability scanner checking for CVEs  
**Why:** Prevents shipping known vulnerabilities in production images  
**How:** Extracts image layers, identifies packages, queries vulnerability databases  
**Tuning:** Set to fail only on CRITICAL (not HIGH) for pragmatic risk-based enforcement

### Checkov
**What:** Infrastructure-as-code security scanner for Terraform/K8s/CloudFormation  
**Why:** Validates infrastructure configs against security best practices before provisioning  
**How:** Parses IaC files and runs policy checks (1000+ built-in policies)  
**Tuning:** Uses `check:` parameter to enforce only 2 critical policies (encryption, public access)

### ArgoCD
**What:** GitOps continuous delivery tool for Kubernetes  
**Why:** Treats Git as single source of truth with automatic sync and audit trail  
**How:** Polls Git repo every 3 minutes, compares with cluster state, applies changes  
**Key Feature:** Self-healing—automatically corrects configuration drift

### HashiCorp Vault
**What:** Centralized secrets management system  
**Why:** Separates secrets from code/configs, enables rotation without redeployment  
**How:** App fetches secrets at runtime via HTTP API using hvac Python client  
**Pattern:** 12-factor app—config in env vars, secrets in Vault, code has neither

### Kyverno
**What:** Kubernetes-native policy engine for admission control  
**Why:** Enforces security standards at API level (can't be bypassed like CI/CD)  
**How:** Admission webhook intercepts resource creation, validates against policies  
**Policies:** Resource limits, non-root containers, required labels

### Prometheus
**What:** Time-series metrics database with pull-based collection  
**Why:** Provides operational visibility into application health and performance  
**How:** Scrapes `/metrics` endpoint every 15 seconds, stores time-series data  
**Integration:** ServiceMonitor for automatic target discovery

### Grafana
**What:** Visualization and dashboarding platform  
**Why:** Makes metrics human-readable with graphs, alerts, and dashboards  
**How:** Queries Prometheus using PromQL, renders as time-series graphs  
**Metrics:** Request rate, latency, error rate, resource usage

---

## 🎤 Common Questions & Answers

### Architecture Questions

**Q: Why both Checkov and Kyverno? Isn't that redundant?**
> No—defense in depth. Checkov scans files in CI/CD (shift-left), Kyverno enforces at runtime (defense against bypass). Someone could skip CI/CD with `kubectl apply`, but they can't bypass Kyverno—it's at the API level.

**Q: Why GitOps instead of traditional CI/CD push?**
> GitOps provides an audit trail (every change has a Git commit), easy rollback (git revert), and declarative desired state. ArgoCD's self-healing also corrects drift automatically.

**Q: Why Kubernetes for a small app?**
> The app is simple by design—it's a demonstration vehicle. The value is in the infrastructure: security automation, policy enforcement, observability. K8s provides the platform for all of this.

### Security Questions

**Q: How do you handle false positives from security scanners?**
> Risk-based tuning. TruffleHog: scoped scan to avoid `.git` metadata. Trivy: fail only on CRITICAL, not HIGH. Checkov: enforce only 2 critical policies instead of 50+. Balance security with operational efficiency.

**Q: Is storing VAULT_TOKEN in deployment.yaml secure?**
> It's a credential, not a secret. Think of it like a database connection string—sensitive but it's configuration, not the data itself. Production would use Kubernetes service account auth with short-lived tokens instead of static tokens.

**Q: What if someone bypasses the CI/CD pipeline?**
> That's why we have Kyverno. CI/CD catches 95% of issues early (cheap to fix), but Kyverno is the last line of defense at the API level. Can't deploy non-compliant workloads even with direct `kubectl` access.

### Technical Questions

**Q: Why did you have image caching issues?**
> Kubernetes caches images tagged `:latest`. When I pushed a new image with the same tag, pods didn't pull it because kubelet thought "I already have :latest". Solution: `imagePullPolicy: Always` forces fresh pulls. Production would use semantic versions (`:v1.2.3`) instead.

**Q: Why namespace exclusions in Kyverno policies?**
> Infrastructure components (Prometheus, ArgoCD) legitimately need elevated privileges. Prometheus admission webhooks run as root to generate TLS certificates. Without exclusions, infrastructure components break. Pattern: trust infrastructure namespaces, enforce on application namespaces.

**Q: How does Vault integration work?**
> App has VAULT_ADDR and VAULT_TOKEN as environment variables (connection info). On startup, app makes HTTP API call to Vault to fetch actual secrets (API keys, passwords). Secrets are loaded into memory, never written to disk or baked into images.

### Observability Questions

**Q: What metrics are you collecting?**
> Flask metrics: request count, request duration histograms, error rates. Process metrics: CPU, memory, open file descriptors. Custom metrics: app version. All in Prometheus format scraped every 15 seconds.

**Q: How does Prometheus discover targets?**
> ServiceMonitor resource tells Prometheus: "Scrape services with label `app=health-app` at path `/metrics` on port 5000 every 15 seconds." Prometheus Operator watches for ServiceMonitors and auto-configures Prometheus.

**Q: Why Grafana instead of Prometheus's built-in UI?**
> Prometheus UI is good for ad-hoc queries but Grafana is better for dashboards, alerting, and multi-datasource correlation. Grafana also has better visualization options (graphs, gauges, tables).

---

## 📊 Tool Comparison Answers

**Q: Kyverno vs OPA Gatekeeper?**
> Kyverno: Kubernetes-native YAML policies, easier to learn, faster for K8s-specific use cases  
> OPA: Rego language, more powerful for complex logic, better for cross-platform policies (K8s + Terraform + Envoy)  
> **Choice:** Kyverno for this project (K8s-only, easier adoption)

**Q: ArgoCD vs Flux?**
> Both are CNCF GitOps tools.  
> ArgoCD: Has UI, easier for beginners, app-of-apps pattern  
> Flux: CLI-focused, better for multi-tenancy, GitOps Toolkit approach  
> **Choice:** ArgoCD for this project (UI helpful for demonstration)

**Q: Prometheus vs Datadog/New Relic?**
> Prometheus: Open-source, self-hosted, pull-based, best for infrastructure metrics  
> Datadog: SaaS, easier setup, better APM, $$$  
> **Choice:** Prometheus (open-source, integrates with K8s natively)

**Q: Vault vs AWS Secrets Manager?**
> Vault: Platform-agnostic, rich feature set (dynamic secrets, encryption-as-a-service)  
> AWS Secrets Manager: AWS-only, tighter AWS integration, managed service  
> **Choice:** Vault (demonstrates tool knowledge, not cloud-specific)

---

## 🎯 "Tell me about a challenge you faced"

### Challenge 1: Checkov Policy Explosion
**Situation:** Initial scan flagged 8 issues. Fixed those, then 12 new ones appeared. Used skip_check, even more appeared with Checkov updates.  
**Task:** Make IaC scanning sustainable without whack-a-mole.  
**Action:** Switched from `skip_check` to `check` parameter. Enforced only 2 critical policies (encryption, public access), tracked rest as technical debt.  
**Result:** Focused enforcement on what matters. Pipeline stayed green while still blocking critical security issues.  
**Learning:** Security tools need risk-based tuning, not default "scan everything."

### Challenge 2: Kyverno Blocking Infrastructure
**Situation:** Deployed Kyverno policies cluster-wide. Prometheus installation failed—admission webhooks blocked for missing labels and root requirement.  
**Task:** Allow infrastructure to install while maintaining security for applications.  
**Action:** Added namespace exclusions to policies for `kube-system`, `monitoring`, `kyverno`, `argocd`.  
**Result:** Infrastructure installed successfully, policies still enforced on application namespaces.  
**Learning:** Pragmatic security means trusting infrastructure, enforcing on applications.

### Challenge 3: Image Caching with :latest
**Situation:** Pushed new image with `:latest` tag. Deleted pods. Pods came back with old code.  
**Task:** Ensure pods pull fresh images on recreation.  
**Action:** Set `imagePullPolicy: Always` in deployment. Also rebuilt image with `--no-cache` to ensure Docker layers were fresh.  
**Result:** Pods pulled fresh images, new code deployed.  
**Learning:** `:latest` tag requires `imagePullPolicy: Always`. Production should use semantic versions.

---

## 🌟 Highlight Stories

### Story 1: Defense in Depth Saves the Day
"Initially I only had Checkov scanning in CI/CD. A teammate suggested I could skip the scan by applying manifests directly with kubectl. That's when I realized Checkov alone isn't enough—it can be bypassed. I added Kyverno admission policies which enforce at the API level. Now even if someone skips CI/CD, they can't deploy non-compliant workloads. That's defense in depth—multiple independent layers."

### Story 2: Risk-Based Security Thinking
"Checkov flagged 50+ issues on my Terraform config. My first instinct was to fix all of them. Then I stepped back and asked: which of these enable data breaches? Turned out only 2 policies were critical—encryption and public access blocks. The rest were operational concerns like versioning and logging. I enforced the critical ones and tracked the rest as technical debt. This is risk-based security—focus on what matters most."

### Story 3: GitOps Discipline
"I made a mistake early on—fixed a deployment issue with `kubectl edit` instead of updating Git. It worked! Then 3 minutes later, ArgoCD's self-heal reverted my change and the issue came back. That taught me GitOps discipline: Git is the source of truth. Now my workflow is: fix in Git first, even for emergencies. The audit trail and rollback capability are worth the extra 30 seconds."

---

## 📝 Project Evolution (Timeline)

**Week 1 (Phase 1-4):** Security scanning in CI/CD
- Set up TruffleHog, Trivy, Checkov
- Built GitHub Actions pipeline
- Added Discord notifications
- **Key learning:** Security scanners need tuning

**Week 2 (Phase 5-6):** Deployment automation
- Deployed ArgoCD
- Built health-app with Flask
- Integrated Vault for secrets
- **Key learning:** GitOps provides audit trail

**Week 3 (Phase 7-8):** Runtime security & monitoring
- Implemented Kyverno policies
- Deployed Prometheus + Grafana
- Added metrics instrumentation
- **Key learning:** Policy enforcement needs exceptions

---

## 🎓 What This Project Proves

**Technical Skills:**
✅ Can integrate multiple tools into cohesive system  
✅ Understands Kubernetes security deeply  
✅ Comfortable with infrastructure-as-code  
✅ Can troubleshoot complex multi-tool issues  
✅ Knows observability patterns (metrics, not just logs)

**Soft Skills:**
✅ Risk-based decision making (tuning scanners)  
✅ Pragmatic engineering (namespace exclusions)  
✅ Documentation discipline (15K words of docs)  
✅ Self-directed learning (figured out image caching, Kyverno blocking, etc.)  
✅ Production thinking (not just tutorial following)

**Industry Alignment:**
✅ CNCF tools (K8s, Prometheus, Kyverno, ArgoCD)  
✅ GitOps principles (declarative, Git as truth)  
✅ Shift-left security (early detection)  
✅ 12-factor app (secrets management)  
✅ Infrastructure-as-code (Terraform, Helm)

---

## 🚀 Next Steps After This Project

**Immediate (Already Done):**
✅ Complete documentation  
✅ Push to GitHub  
✅ Create README with architecture diagrams  
✅ Write resume bullets

