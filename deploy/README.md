# TalkGPT GCP Deployment Scripts

This directory contains all the scripts and configurations needed to deploy TalkGPT on Google Cloud Platform in a production-ready manner.

## Quick Deployment

Run these scripts in order for a complete deployment:

```bash
# 1. Initial setup
./gcp-setup.sh                 # Set up GCP project and APIs
./configure-registry.sh        # Configure Artifact Registry
./setup-storage.sh            # Create Cloud Storage buckets
./setup-redis.sh             # Deploy Redis instance

# 2. Infrastructure
./create-cluster.sh          # Create GKE cluster with GPU support
./build-images.sh           # Build and push Docker images

# 3. Application deployment  
./create-k8s-manifests.sh   # Deploy Kubernetes resources
./setup-secrets.sh          # Configure Secret Manager
./setup-monitoring.sh       # Set up monitoring stack
./setup-autoscaling.sh      # Configure autoscaling

# 4. Testing and CI/CD
./deploy-and-test.sh        # Deploy and run tests
./setup-cicd.sh            # Configure CI/CD pipeline
```

## Script Descriptions

### Core Infrastructure Scripts

| Script | Purpose | Dependencies |
|--------|---------|--------------|
| `gcp-setup.sh` | Enable GCP APIs, create service accounts | gcloud CLI |
| `configure-registry.sh` | Set up Artifact Registry for Docker images | gcp-setup.sh |
| `setup-storage.sh` | Create Cloud Storage buckets with lifecycle policies | gcp-setup.sh |
| `setup-redis.sh` | Deploy Memorystore Redis instance | gcp-setup.sh |
| `create-cluster.sh` | Create GKE cluster with CPU/GPU node pools | gcp-setup.sh |

### Application Deployment Scripts

| Script | Purpose | Dependencies |
|--------|---------|--------------|
| `build-images.sh` | Build and push Docker images | configure-registry.sh |
| `create-k8s-manifests.sh` | Deploy Kubernetes resources | create-cluster.sh, build-images.sh |
| `setup-secrets.sh` | Configure Secret Manager and K8s secrets | create-cluster.sh |

### Operations Scripts

| Script | Purpose | Dependencies |
|--------|---------|--------------|
| `setup-monitoring.sh` | Install Prometheus, Grafana, alerting | create-cluster.sh |
| `setup-autoscaling.sh` | Configure HPA, VPA, KEDA, cluster autoscaler | create-cluster.sh |
| `setup-cicd.sh` | Create Cloud Build triggers and pipelines | All core scripts |
| `deploy-and-test.sh` | Full deployment with comprehensive testing | All scripts |

### Utility Scripts

| Script | Purpose | Usage |
|--------|---------|--------|
| `deploy-production.sh` | Trigger production deployment | ./deploy-production.sh |
| `deploy-staging.sh` | Trigger staging deployment | ./deploy-staging.sh |
| `rollback.sh` | Rollback to previous version | ./rollback.sh \<image-tag\> |

## Configuration Files

### Docker Images
- `Dockerfile` - Core application image (CPU)
- `Dockerfile.mcp` - MCP server image  
- `Dockerfile.gpu` - GPU-enabled image (generated during build)

### Kubernetes Manifests
Located in `../k8s/`:
- `mcp-deployment.yaml` - MCP server deployment, service, HPA
- `worker-deployment.yaml` - CPU and GPU worker deployments
- `ingress.yaml` - Ingress with SSL termination
- `monitoring.yaml` - Prometheus and monitoring stack

### CI/CD Configuration
- `../cloudbuild.yaml` - Main production build pipeline
- `cloudbuild-staging.yaml` - Staging build pipeline (generated)
- `cloudbuild-hotfix.yaml` - Hotfix build pipeline (generated)

## Environment Variables

Update these variables in the scripts before deployment:

```bash
# Core settings
PROJECT_ID="talkgpt-production"          # Your GCP project ID
REGION="us-central1"                     # Preferred GCP region  
REPOSITORY_NAME="talkgpt-images"         # Artifact Registry repo
CLUSTER_NAME="talkgpt-cluster"           # GKE cluster name
NAMESPACE="talkgpt"                      # Kubernetes namespace

# GitHub settings (for CI/CD)
GITHUB_REPO="Alex-Zeo/TalkGPT"          # GitHub repository
```

## Prerequisites

### Required Tools
- `gcloud` - Google Cloud CLI
- `kubectl` - Kubernetes CLI
- `docker` - Container runtime
- `helm` - Kubernetes package manager

### Permissions
Your GCP account needs the following roles:
- Project Owner (for initial setup) OR
- Project Editor + Security Admin + Kubernetes Engine Admin

### Installation Commands
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
gcloud init

# Install kubectl
gcloud components install kubectl

# Install helm
curl https://get.helm.sh/helm-v3.12.0-linux-amd64.tar.gz | tar -xz
sudo mv linux-amd64/helm /usr/local/bin/

# Install docker (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install docker.io
sudo usermod -aG docker $USER
```

## Cost Estimation

### Monthly Costs (Approximate)
- **GKE Cluster**: $150-300/month (CPU nodes)
- **GPU Nodes**: $200-400/month when running (Tesla T4)
- **Redis Memorystore**: $50-100/month (4GB instance)
- **Cloud Storage**: $10-50/month (depending on usage)
- **Load Balancer**: $20/month
- **Monitoring**: $20-50/month
- **Total**: $450-920/month for moderate usage

### Cost Optimization Tips
- Use preemptible instances for development
- Scale GPU nodes to zero when not in use
- Use lifecycle policies for storage
- Monitor and right-size resources regularly

## Monitoring & Health Checks

### After Deployment
```bash
# Check overall health
kubectl get pods -n talkgpt
kubectl get services -n talkgpt  
kubectl get ingress -n talkgpt

# Monitor autoscaling
kubectl get hpa -n talkgpt
kubectl top pods -n talkgpt

# Check logs
kubectl logs -n talkgpt -l app=talkgpt-mcp -f
```

### Key Metrics to Monitor
- Pod CPU/Memory utilization
- Request rate and latency
- Queue depth in Redis
- Node utilization
- Cost and resource usage

## Troubleshooting

### Common Issues

1. **Permission Denied Errors**
   ```bash
   # Ensure proper authentication
   gcloud auth login
   gcloud config set project $PROJECT_ID
   ```

2. **Docker Build Failures**
   ```bash
   # Check Docker daemon is running
   sudo systemctl start docker
   docker info
   ```

3. **Kubernetes Connection Issues**  
   ```bash
   # Re-authenticate to cluster
   gcloud container clusters get-credentials talkgpt-cluster --region=us-central1
   ```

4. **Resource Quota Exceeded**
   ```bash
   # Check quotas in GCP Console
   gcloud compute project-info describe --project=$PROJECT_ID
   ```

### Getting Help

1. Check script output for specific error messages
2. Review GCP Console for service status
3. Check Kubernetes events: `kubectl get events -n talkgpt`
4. Review detailed deployment guide: `../docs/GCP_DEPLOYMENT_GUIDE.md`
5. Check application logs for runtime issues

## Security Notes

### Secrets Management
- Never commit secrets to version control
- Use Secret Manager for sensitive values
- Rotate secrets regularly
- Follow principle of least privilege

### Network Security
- Configure firewall rules appropriately
- Use private GKE clusters for production
- Enable network policies
- Consider Cloud Armor for DDoS protection

### Container Security
- Scan images for vulnerabilities
- Use minimal base images
- Run containers as non-root
- Keep dependencies updated

## Next Steps After Deployment

1. **Configure Domain & SSL**
   - Point your domain to the external IP
   - Update ingress.yaml with your domain
   - Configure SSL certificate

2. **Update Secrets**
   - Replace placeholder API keys
   - Configure webhook secrets
   - Set up proper authentication

3. **Customize Configuration**
   - Adjust resource limits based on usage
   - Fine-tune autoscaling parameters
   - Configure monitoring alerts

4. **Set Up Backup Strategy**
   - Configure regular backups
   - Test restore procedures
   - Document recovery processes

5. **Production Hardening**
   - Review security settings
   - Enable audit logging
   - Set up compliance monitoring

For detailed information, see the [GCP Deployment Guide](../docs/GCP_DEPLOYMENT_GUIDE.md).