#!/bin/bash

# Master deployment script for TalkGPT on GCP
# Runs all deployment scripts in the correct order

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="talkgpt-production"
REGION="us-central1"

# Function to print step header
print_step() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Step $1: $2${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Function to check if script exists and is executable
check_script() {
    local script=$1
    if [ ! -f "$script" ]; then
        echo -e "${RED}✗ Script not found: $script${NC}"
        exit 1
    fi
    if [ ! -x "$script" ]; then
        chmod +x "$script"
    fi
}

# Function to run script with error handling
run_script() {
    local script=$1
    local description=$2
    
    echo -e "${BLUE}Running: $script${NC}"
    if ./$script; then
        echo -e "${GREEN}✓ $description completed successfully${NC}"
    else
        echo -e "${RED}✗ $description failed${NC}"
        echo -e "${YELLOW}You can continue manually from the next step or investigate the error${NC}"
        read -p "Continue with deployment? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Verify prerequisites
echo -e "${BLUE}TalkGPT GCP Deployment${NC}"
echo -e "${BLUE}======================${NC}"
echo ""
echo "This script will deploy TalkGPT to Google Cloud Platform."
echo "Estimated deployment time: 30-45 minutes"
echo "Estimated monthly cost: \$450-920 (moderate usage)"
echo ""

# Confirm project and settings
echo -e "${YELLOW}Configuration:${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Cluster: talkgpt-cluster"
echo "  Namespace: talkgpt"
echo ""

read -p "Continue with this configuration? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please edit this script to update configuration variables"
    exit 0
fi

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"
for cmd in gcloud kubectl docker helm; do
    if ! command -v $cmd >/dev/null 2>&1; then
        echo -e "${RED}✗ $cmd is not installed${NC}"
        echo "Please install required tools. See README.md for instructions."
        exit 1
    fi
done
echo -e "${GREEN}✓ All required tools are installed${NC}"

# Verify gcloud authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 >/dev/null; then
    echo -e "${RED}✗ Not authenticated with gcloud${NC}"
    echo "Please run: gcloud auth login"
    exit 1
fi
echo -e "${GREEN}✓ Authenticated with gcloud${NC}"

# Start deployment
echo ""
echo -e "${GREEN}Starting TalkGPT deployment...${NC}"
START_TIME=$(date +%s)

# Step 1: Core infrastructure setup
print_step "1" "GCP Project Setup"
check_script "gcp-setup.sh"
run_script "gcp-setup.sh" "GCP project setup"

print_step "2" "Artifact Registry Configuration"
check_script "configure-registry.sh"
run_script "configure-registry.sh" "Artifact Registry configuration"

print_step "3" "Cloud Storage Setup"
check_script "setup-storage.sh"
run_script "setup-storage.sh" "Cloud Storage setup"

print_step "4" "Redis Deployment"
check_script "setup-redis.sh"
run_script "setup-redis.sh" "Redis deployment"

print_step "5" "GKE Cluster Creation"
check_script "create-cluster.sh"
run_script "create-cluster.sh" "GKE cluster creation"

# Step 2: Application deployment
print_step "6" "Docker Image Build"
check_script "build-images.sh"
run_script "build-images.sh" "Docker image build and push"

print_step "7" "Kubernetes Deployment"
check_script "create-k8s-manifests.sh"
run_script "create-k8s-manifests.sh" "Kubernetes deployment"

print_step "8" "Secrets Configuration"
check_script "setup-secrets.sh"
run_script "setup-secrets.sh" "Secrets configuration"

# Step 3: Operations setup
print_step "9" "Monitoring Setup"
check_script "setup-monitoring.sh"
run_script "setup-monitoring.sh" "Monitoring setup"

print_step "10" "Autoscaling Configuration"
check_script "setup-autoscaling.sh"
run_script "setup-autoscaling.sh" "Autoscaling configuration"

print_step "11" "CI/CD Pipeline"
check_script "setup-cicd.sh"
run_script "setup-cicd.sh" "CI/CD pipeline setup"

# Step 4: Final testing
print_step "12" "Deployment Testing"
check_script "deploy-and-test.sh"
run_script "deploy-and-test.sh" "Deployment testing"

# Calculate deployment time
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

# Final summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 DEPLOYMENT COMPLETED! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Deployment Summary:${NC}"
echo "  Duration: ${MINUTES}m ${SECONDS}s"
echo "  Project: $PROJECT_ID"
echo "  Region: $REGION"
echo ""

# Get external IP
EXTERNAL_IP=$(gcloud compute addresses describe talkgpt-ip --global --format="value(address)" 2>/dev/null || echo "Not assigned")
echo -e "${BLUE}External Access:${NC}"
echo "  IP Address: $EXTERNAL_IP"
if [ "$EXTERNAL_IP" != "Not assigned" ]; then
    echo "  URL: http://$EXTERNAL_IP"
else
    echo "  Note: External IP will be assigned shortly"
fi

echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Update DNS to point your domain to $EXTERNAL_IP"
echo "2. Update k8s/ingress.yaml with your domain name"
echo "3. Apply ingress: kubectl apply -f k8s/ingress.yaml"
echo "4. Update secrets with real API keys:"
echo "   gcloud secrets versions add talkgpt-openai-key --data-file=<your-key-file>"
echo "5. Review test-report.txt for detailed status"
echo "6. Complete post-deployment-checklist.md"

echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "  # Check pod status"
echo "  kubectl get pods -n talkgpt"
echo ""
echo "  # View logs"
echo "  kubectl logs -n talkgpt -l app=talkgpt-mcp -f"
echo ""
echo "  # Access MCP server locally"
echo "  kubectl port-forward -n talkgpt service/talkgpt-mcp-service 8000:8000"
echo ""
echo "  # Monitor autoscaling"
echo "  kubectl get hpa -n talkgpt"
echo ""
echo "  # Check external access"
echo "  curl -I http://$EXTERNAL_IP"

echo ""
echo -e "${BLUE}Monitoring Dashboards:${NC}"
echo "  - GCP Console: https://console.cloud.google.com/kubernetes/workload?project=$PROJECT_ID"
echo "  - Prometheus: kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090"
echo "  - Grafana: kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80 (admin/admin123)"

echo ""
echo -e "${BLUE}Documentation:${NC}"
echo "  - Full guide: docs/GCP_DEPLOYMENT_GUIDE.md"
echo "  - Operations: deploy/README.md"
echo "  - Test report: test-report.txt"
echo "  - Checklist: post-deployment-checklist.md"

echo ""
echo -e "${GREEN}Deployment completed successfully! 🚀${NC}"

# Create deployment summary file
cat > deployment-summary.txt << EOF
TalkGPT GCP Deployment Summary
Generated: $(date)
Duration: ${MINUTES}m ${SECONDS}s

Project: $PROJECT_ID
Region: $REGION
External IP: $EXTERNAL_IP

Services Deployed:
- GKE Cluster: talkgpt-cluster
- Redis: talkgpt-redis  
- Storage Buckets: 3 buckets created
- Docker Images: 4 images pushed to Artifact Registry
- Kubernetes Services: MCP server + Workers deployed
- Monitoring: Prometheus + Grafana installed
- Autoscaling: HPA, VPA, KEDA configured
- CI/CD: Cloud Build triggers created

Next Steps:
1. Configure DNS for your domain
2. Update secrets with real API keys  
3. Review and complete post-deployment checklist
4. Monitor system health and adjust resources as needed

For detailed information, see:
- docs/GCP_DEPLOYMENT_GUIDE.md
- deploy/README.md
- test-report.txt
EOF

echo "Summary saved to: deployment-summary.txt"