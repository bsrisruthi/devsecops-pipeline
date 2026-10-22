# Project Lessons Learned

Real-world challenges encountered and solved during the DevSecOps pipeline implementation.

---

## 🔥 Critical Issues and Solutions

### Issue 1: TruffleHog False Positive in Git Metadata

**Problem:**
```
TruffleHog detected a GitHub URL in .git/config as a potential secret:
url = https://github.com/bsrisruthi/devsecops-pipeline.git
```

**Why It Happened:**
- TruffleHog's pattern matching flagged the GitHub URL structure
- The `.git` directory contains repository metadata that looks like sensitive information
- Scanning the entire repository includes metadata that isn't actually application code

**Solutions Attempted:**
1. ❌ `--exclude-paths=/scan/.git` - Didn't work with the filesystem scanner
2. ✅ Scoped scan to `/scan/devsecops` only - Successfully excluded .git

**Final Solution:**
```yaml
run: |
  docker run --rm -v "$PWD:/scan" ghcr.io/trufflesecurity/trufflehog:latest \
    filesystem /scan/devsecops --fail --json
```

**Key Learning:**
> **Secret scanners should scan only application code directories, not entire repositories.** Git metadata, build artifacts, and dependency directories often trigger false positives.

**Application to Production:**
- Define explicit scan paths in CI/CD
- Exclude: `.git`, `node_modules`, `.venv`, `dist`, `build`
- Document why paths are excluded to prevent security gaps

---

### Issue 2: Kubernetes Image Caching with `:latest` Tag

**Problem:**
- Pushed new Docker image to GHCR with `:latest` tag
- Deleted pods to force recreation
- Pods came back up but showed **old code** (v3.0 instead of v5.0)

**Why It Happened:**
- Kubernetes caches images locally on nodes
- With `:latest` tag, kubelet checks: "Do I have 'latest'?" → "Yes" → Uses cached image
- Doesn't pull new image even though remote registry has updated content

**Evidence:**
```bash
curl http://localhost:5000/version
# Expected: v5.0 - Monitored by Prometheus!
# Actual: v3.0 - Auto-deployed by ArgoCD!
```

**Solutions Attempted:**
1. ❌ Delete and recreate pods - Still used cached image
2. ❌ Change timestamp annotation - Recreated pods but cached image persisted
3. ✅ Set `imagePullPolicy: Always` - Forces fresh pull

**Final Solution:**
```yaml
spec:
  containers:
  - name: health-app
    image: ghcr.io/bsrisruthi/health-app:latest
    imagePullPolicy: Always  # ← This line
```

**Key Learning:**
> **The `:latest` tag is convenient for development but requires `imagePullPolicy: Always` to work correctly.** Production should use specific version tags (`:v1.2.3`) with default pull policy.

**Best Practices:**
- **Development**: `:latest` + `imagePullPolicy: Always`
- **Production**: Semantic versions `:v1.2.3` + `imagePullPolicy: IfNotPresent`
- **Why?** Production needs reproducibility; development needs quick iteration

---

### Issue 3: Checkov Policy Explosion

**Problem:**
- Initial Checkov scan: 8 failures
- Fixed those 8, ran again: 12 new failures appeared
- Used `skip_check` for those: Even more appeared after Checkov updates
- Whack-a-mole situation with 50+ policies

**Policies That Kept Appearing:**
- CKV_AWS_21: Versioning
- CKV_AWS_144: Cross-region replication
- CKV2_AWS_62: Event notifications
- CKV_AWS_18: Access logging
- CKV_AWS_145: KMS encryption with customer keys

**Initial Approach (Failed):**
```yaml
skip_check: CKV_AWS_21,CKV_AWS_144,CKV2_AWS_62,CKV_AWS_18,CKV_AWS_145,...
# List kept growing with every Checkov update!
```

**Final Approach (Success):**
```yaml
check: CKV2_AWS_6,CKV_AWS_93
# Only enforce critical policies: public access block, encryption
```

**Key Learning:**
> **Security tools should be tuned based on risk, not exhaustiveness.** Focus on critical issues (data breaches, credential leaks) rather than every possible misconfiguration.

**Decision Framework:**

| Priority | What | Example | Action |
|----------|------|---------|--------|
| **P0 - Critical** | Data breaches | Public S3, no encryption | **Block** |
| **P1 - High** | Privilege escalation | Root containers | **Block** |
| **P2 - Medium** | Operational issues | No versioning, no logging | **Warn** |
| **P3 - Low** | Best practices | Tagging standards | **Optional** |

**Application to Production:**
- Start with P0 policies only
- Gradually add P1 after initial deployment
- P2/P3 policies become technical debt tickets, not blockers

---

### Issue 4: Kyverno Blocking Infrastructure Components

**Problem:**
```
Error: INSTALLATION FAILED
Job/monitoring/prometheus-kube-prometheus-admission-create was blocked:
- require-labels: missing 'env' label
- block-root-containers: needs runAsNonRoot=true
- require-resource-limits: no CPU/memory limits
```

**Why It Happened:**
- Kyverno policies applied cluster-wide (all namespaces)
- Prometheus operator admission webhook jobs don't have custom labels
- These jobs legitimately need root access (to generate TLS certificates)
- Infrastructure components have different security requirements than applications

**Initial Response (Failed):**
- Tried setting policies to `Audit` mode temporarily
- Policies no longer blocked, but defeated the purpose

**Final Solution:**
Added namespace exclusions to all policies:
```yaml
exclude:
  any:
  - resources:
      namespaces:
      - kube-system      # Core Kubernetes components
      - monitoring       # Prometheus, Grafana
      - kyverno          # Policy engine itself
      - argocd           # GitOps controller
      - vault            # Secrets management
```

**Key Learning:**
> **Policy enforcement requires pragmatic exceptions for trusted infrastructure.** Blanket policies that block critical infrastructure components are worse than no policies—they erode trust in security tooling.

**Design Pattern:**
```
Application Namespaces (health-app, api, web)
  ├─ Strict policies (non-root, limits, labels)
  └─ No exceptions

Infrastructure Namespaces (kube-system, monitoring)
  ├─ Trusted components
  └─ Relaxed policies (namespace exclusions)
```

**Alternative Approaches:**
- Separate clusters for apps vs infrastructure (expensive)
- Per-policy namespace targeting (complex maintenance)
- Custom policies for infrastructure (duplicate work)

---

### Issue 5: Nginx Container Passed Kyverno but Failed to Start

**Problem:**
```yaml
# This pod passed ALL Kyverno policies
apiVersion: v1
kind: Pod
metadata:
  name: compliant-pod
  labels:
    app: test
    env: dev
spec:
  containers:
  - name: nginx
    image: nginx:latest
    securityContext:
      runAsNonRoot: true
      runAsUser: 1000
    resources:
      limits:
        memory: "128Mi"
        cpu: "100m"
```

```bash
kubectl get pod compliant-pod
NAME            READY   STATUS             RESTARTS   AGE
compliant-pod   0/1     CrashLoopBackOff   5          3m
```

**Logs showed:**
```
nginx: [emerg] bind() to 0.0.0.0:80 failed (13: Permission denied)
```

**Why It Happened:**
- Nginx binds to port 80 by default
- Ports below 1024 require root privileges
- Kyverno validated the YAML structure (correct securityContext)
- But couldn't predict runtime behavior (nginx needing root)

**Solution:**
Used busybox instead of nginx:
```yaml
containers:
- name: test
  image: busybox:latest
  command: ["sleep", "3600"]
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
```

**Key Learning:**
> **Admission control validates configuration, not runtime behavior.** A policy can confirm a pod *asks* to run as non-root, but can't guarantee the container image will *work* as non-root.

**Production Implications:**
- **Test workloads** with security constraints before enforcing policies
- **Choose appropriate base images**: Many official images assume root access
- **Configure images properly**: Nginx can run as non-root with `listen 8080;` in config
- **Security vs Compatibility**: Sometimes you need custom base images

**Non-Root Nginx Example:**
```dockerfile
FROM nginx:latest
# Change ownership to non-root user
RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx /etc/nginx/conf.d
# Configure nginx to listen on 8080
RUN sed -i 's/listen       80;/listen       8080;/' /etc/nginx/conf.d/default.conf
USER nginx
EXPOSE 8080
```

---

### Issue 6: Vault Secret Confusion

**Problem:**
User question: "How did the secrets get stored in Vault? I don't see a `vault kv put` in my deployment.yaml"

**Confusion:**
```yaml
# In deployment.yaml
env:
- name: VAULT_ADDR
  value: "http://host.docker.internal:8200"
- name: VAULT_TOKEN
  value: "myroot"
```

"Are VAULT_ADDR and VAULT_TOKEN the secrets?"

**Clarification:**

| Item | What It Is | Where It Lives | Why |
|------|-----------|----------------|-----|
| **VAULT_ADDR** | Configuration | deployment.yaml | Tells app WHERE Vault is |
| **VAULT_TOKEN** | Credential | deployment.yaml | Tells app HOW to authenticate |
| **api_key** | Secret | Inside Vault | The actual sensitive data |
| **db_password** | Secret | Inside Vault | The actual sensitive data |

**Analogy:**
```
VAULT_ADDR + VAULT_TOKEN = "Database connection string"
api_key + db_password = "Data inside the database"
```

**How Secrets Got Into Vault:**
```bash
# Manual command (one-time setup)
kubectl exec -n vault vault-0 -- vault kv put secret/health-app/config \
  api_key="prod-api-key-12345" \
  db_password="secure-password-67890"
```

**In production, this would be:**
- Terraform with Vault provider
- Automated provisioning script
- Integration with external secret store (AWS Secrets Manager)

**Key Learning:**
> **Distinguish between secrets (sensitive data) and credentials (how to access secrets).** VAULT_TOKEN is sensitive but it's not the application secret—it's the key to fetch application secrets.

**12-Factor App Principle:**
- **Config goes in environment variables** (VAULT_ADDR, VAULT_TOKEN)
- **Secrets go in secret store** (Vault)
- **Code has neither** (references environment variables)

---

### Issue 7: ArgoCD OutOfSync After Manual Fixes

**Problem:**
- Made changes directly with `kubectl edit deployment health-app`
- Fixed the issue, pods working
- ArgoCD shows "OutOfSync" status
- A few minutes later, ArgoCD reverted my changes!

**Why It Happened:**
- ArgoCD's `selfHeal: true` setting
- Git says: "deployment should have 2 replicas"
- Cluster says: "deployment has 3 replicas"
- ArgoCD: "Drift detected! Fixing..."
- Reverts to Git state (2 replicas)

**Correct Workflow:**
```
1. Identify issue (pods not starting)
2. Fix it LOCALLY (edit deployment.yaml in Git)
3. Git commit + push
4. ArgoCD auto-syncs
5. Changes deployed
```

**Wrong Workflow:**
```
1. Identify issue
2. kubectl edit deployment (direct change)
3. ✅ Fixed immediately
4. ❌ ArgoCD reverts it 3 minutes later
5. Issue returns!
```

**Key Learning:**
> **GitOps means Git is the source of truth. Direct cluster changes are temporary at best, reverted at worst.** Emergency fixes should be followed immediately by Git updates.

**Emergency Procedure:**
1. **Immediate fix**: `kubectl edit` (gets system working)
2. **Permanent fix**: Update Git within same incident
3. **Document**: Git commit message explains emergency and permanent fix

**When to Break GitOps:**
- Never for changes (always use Git)
- Only for debugging (kubectl logs, kubectl describe)
- Only for emergencies, with follow-up Git commit

---

## 🎓 Production Patterns Learned

### Pattern 1: Shift-Left + Runtime Enforcement

**Don't choose between CI/CD scanning and runtime policies—do both.**

| Layer | Tool | What It Catches | Can Be Bypassed? |
|-------|------|-----------------|------------------|
| **CI/CD** | Checkov | IaC misconfigurations | Yes (kubectl apply) |
| **Runtime** | Kyverno | Non-compliant resources | No (API-level) |

**Why both?**
- Shift-left catches 95% of issues early (cheap to fix)
- Runtime enforcement catches the 5% that slip through (kubectl, manual changes)
- Defense in depth

---

### Pattern 2: Risk-Based Tuning

**Security tools generate noise. Tune based on actual risk, not tool defaults.**

**Initial Approach:**
- "Scanner flagged 50 issues, must fix all 50!"
- Spends weeks fixing low-priority items
- Delays deployment

**Mature Approach:**
- "50 issues flagged. Which ones enable data breaches?"
- Fix P0/P1 immediately (encryption, public access)
- Track P2/P3 as technical debt
- Ship on time with acceptable risk

**Decision Framework:**
```
Critical (Block): Data breach, credential leak, privilege escalation
High (Block): Resource exhaustion, DoS, known CVEs
Medium (Warn): Operational issues (logging, versioning)
Low (Optional): Best practices (tagging, naming)
```

---

### Pattern 3: Separation of Secrets and Configuration

**Configuration is "how to connect." Secrets are "what to protect."**

| Type | Example | Storage | Public? |
|------|---------|---------|---------|
| **Config** | `VAULT_ADDR=http://vault:8200` | deployment.yaml | Yes |
| **Credential** | `VAULT_TOKEN=myroot` | Kubernetes Secret | Sensitive |
| **Secret** | `db_password=prod123` | Vault | No |

**Why this matters:**
- Config can be in Git (it's not sensitive)
- Credentials should be in Kubernetes Secrets (platform-managed)
- Secrets should be in Vault (runtime fetch, audit logs)

---

### Pattern 4: Pragmatic Policy Exceptions

**Strict policies need smart exceptions, or they'll be disabled entirely.**

**Bad:**
- Apply policy to ALL namespaces
- Infrastructure breaks
- Disable policy entirely

**Good:**
- Apply policy to application namespaces
- Exclude trusted infrastructure namespaces
- Policy stays enforced where it matters

**The Rule:**
> **Trust infrastructure, enforce on applications.** Infrastructure components (monitoring, logging, GitOps controllers) are operated by the platform team and have different security requirements.

---

## 📊 Metrics That Matter

### Pipeline Metrics
- **Scan Time**: 2-3 minutes for all three security scans
- **False Positive Rate**: ~5% (mainly from TruffleHog pattern matching)
- **Deployment Frequency**: Automated on every commit
- **Rollback Time**: <30 seconds (git revert + ArgoCD sync)

### Security Metrics
- **Secret Scan Coverage**: 100% of commits
- **Container Vulnerability Gate**: Block on CRITICAL CVEs
- **IaC Policy Compliance**: 2 enforced policies (encryption, public access)
- **Runtime Policy Violations**: 0 (Kyverno blocks non-compliant pods)

### Operational Metrics
- **Deployment Success Rate**: ~95% (failures due to policy violations)
- **MTTR (Mean Time To Recovery)**: <5 minutes (git revert)
- **Image Pull Time**: ~15 seconds with imagePullPolicy: Always
- **GitOps Sync Time**: 3 minutes (ArgoCD polling interval)

---

## 🚀 What I Would Do Differently

### If Starting Over

1. **Use semantic versioning from day 1**
   - Tags like `:v1.0.0`, `:v1.1.0` instead of `:latest`
   - Eliminates image caching issues
   - Provides clear deployment history

2. **Define policy priorities upfront**
   - Decide: "We only enforce P0/P1 policies"
   - Document exceptions in policy files
   - Avoids whack-a-mole with security scanners

3. **Namespace strategy first**
   - Plan: Which namespaces are "trusted infrastructure" vs "applications"
   - Configure policies with exclusions from the start
   - Prevents breaking infrastructure components

4. **Automated secret provisioning**
   - Don't rely on manual `vault kv put` commands
   - Use Terraform + Vault provider
   - Secrets provisioned as code

5. **Test policies before enforcement**
   - Run in Audit mode first
   - Collect data on what would be blocked
   - Switch to Enforce mode with confidence

---

### If Extending This Project

**Next priorities:**
1. **Network Policies** - Restrict pod-to-pod traffic
2. **RBAC** - Role-based access control for developers
3. **Multi-environment** - dev/staging/prod with separate configs
4. **Log aggregation** - Centralized logging with Loki
5. **Alerting** - Prometheus Alertmanager for on-call notifications

---

## 💡 Key Insights

### Technical Insights

1. **Tooling integration is harder than tool selection**
   - Each tool is easy individually
   - Making them work together is the challenge
   - Example: Kyverno blocking Prometheus installation

2. **Default configurations are rarely production-ready**
   - Trivy: Initial severity was too strict (blocked on HIGH)
   - Checkov: Default policies were too exhaustive
   - ArgoCD: Needed imagePullPolicy tuning
   - Tuning is part of implementation, not an afterthought

3. **Git is a powerful audit trail**
   - Every deployment has a commit SHA
   - Rollback = git revert
   - Compliance teams can see: who changed what, when, why

4. **Policy enforcement works best with education**
   - Developers need to understand WHY policies exist
   - Just blocking deployments breeds resentment
   - Pair policy enforcement with documentation

### Process Insights

1. **Start simple, add complexity gradually**
   - Phase 1-4 (scanning) first
   - Then Phase 5 (deployment automation)
   - Then Phase 6-8 (security + monitoring)
   - Each phase validates before adding the next

2. **Documentation is part of the deliverable**
   - Working pipeline is 50%
   - Documentation is 50%
   - Future you (or teammates) need to understand decisions

3. **Learning by breaking things is valuable**
   - nginx crash taught admission vs runtime validation
   - Kyverno blocking Prometheus taught namespace strategy
   - Image caching taught Kubernetes image pull policies

---

## 🎯 Applying This to Real Work

### Relevant to DevSecOps Roles

**What this project proves:**
- ✅ Can integrate multiple security tools
- ✅ Understands shift-left security
- ✅ Can tune tools based on risk (not just defaults)
- ✅ Knows Kubernetes security patterns
- ✅ Comfortable with GitOps workflows
- ✅ Can troubleshoot complex multi-tool issues

### Relevant to SRE Roles

**What this project proves:**
- ✅ Can deploy observable systems (Prometheus/Grafana)
- ✅ Understands infrastructure-as-code
- ✅ Implements automated deployment pipelines
- ✅ Knows how to design for reliability (health checks, rolling updates)
- ✅ Can work with Kubernetes at depth

### Relevant to Security Engineering

**What this project proves:**
- ✅ Defense-in-depth architecture
- ✅ Policy-as-code implementation
- ✅ Secrets management best practices
- ✅ Security tool evaluation and tuning
- ✅ Risk-based decision making

---

**The most valuable learning: Building this end-to-end taught me how production systems actually work, not just how individual tools work in isolation.**
