#!/bin/bash

# Deploy and test TalkGPT on GCP

set -e

# Variables
PROJECT_ID="talkgpt-production"
REGION="us-central1"
CLUSTER_NAME="talkgpt-cluster"
NAMESPACE="talkgpt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting TalkGPT deployment and testing...${NC}"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for deployment
wait_for_deployment() {
    local deployment=$1
    local namespace=$2
    local timeout=${3:-300}
    
    echo -e "${BLUE}Waiting for deployment $deployment to be ready...${NC}"
    kubectl rollout status deployment/$deployment -n $namespace --timeout=${timeout}s
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Deployment $deployment is ready${NC}"
    else
        echo -e "${RED}✗ Deployment $deployment failed to become ready${NC}"
        return 1
    fi
}

# Function to run health checks
health_check() {
    local service=$1
    local port=$2
    local path=${3:-/health}
    
    echo -e "${BLUE}Running health check for $service...${NC}"
    
    # Port forward to test service
    kubectl port-forward service/$service $port:$port -n $NAMESPACE &
    local pf_pid=$!
    sleep 5
    
    # Test health endpoint
    local response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port$path || echo "000")
    kill $pf_pid 2>/dev/null || true
    
    if [ "$response" = "200" ]; then
        echo -e "${GREEN}✓ Health check passed for $service${NC}"
        return 0
    else
        echo -e "${RED}✗ Health check failed for $service (HTTP $response)${NC}"
        return 1
    fi
}

# Verify prerequisites
echo -e "${BLUE}Verifying prerequisites...${NC}"
for cmd in gcloud kubectl helm docker; do
    if ! command_exists $cmd; then
        echo -e "${RED}✗ $cmd is not installed${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓ All required tools are installed${NC}"

# Ensure we're connected to the correct cluster
echo -e "${BLUE}Connecting to GKE cluster...${NC}"
gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION --project=$PROJECT_ID

# Verify cluster connectivity
kubectl cluster-info || {
    echo -e "${RED}✗ Cannot connect to Kubernetes cluster${NC}"
    exit 1
}
echo -e "${GREEN}✓ Connected to Kubernetes cluster${NC}"

# Create namespace if it doesn't exist
echo -e "${BLUE}Ensuring namespace exists...${NC}"
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Deploy all components in order
echo -e "${BLUE}Deploying TalkGPT components...${NC}"

# 1. Deploy MCP server
echo -e "${BLUE}Deploying MCP server...${NC}"
kubectl apply -f k8s/mcp-deployment.yaml
wait_for_deployment "talkgpt-mcp" $NAMESPACE

# 2. Deploy workers
echo -e "${BLUE}Deploying workers...${NC}"
kubectl apply -f k8s/worker-deployment.yaml
wait_for_deployment "talkgpt-worker-cpu" $NAMESPACE

# 3. Deploy monitoring
echo -e "${BLUE}Deploying monitoring...${NC}"
kubectl apply -f k8s/monitoring.yaml
wait_for_deployment "talkgpt-prometheus" $NAMESPACE

# 4. Deploy ingress
echo -e "${BLUE}Deploying ingress...${NC}"
kubectl apply -f k8s/ingress.yaml

# Wait for all pods to be ready
echo -e "${BLUE}Waiting for all pods to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=talkgpt-mcp -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=ready pod -l app=talkgpt-worker -n $NAMESPACE --timeout=300s || echo "Some workers may still be starting"

# Run comprehensive tests
echo -e "${BLUE}Running deployment tests...${NC}"

# Test 1: Basic connectivity
echo -e "${BLUE}Test 1: Basic pod connectivity${NC}"
PODS_READY=$(kubectl get pods -n $NAMESPACE --no-headers | grep "Running" | wc -l)
TOTAL_PODS=$(kubectl get pods -n $NAMESPACE --no-headers | wc -l)
echo "Pods ready: $PODS_READY/$TOTAL_PODS"

if [ $PODS_READY -gt 0 ]; then
    echo -e "${GREEN}✓ Pods are running${NC}"
else
    echo -e "${RED}✗ No pods are running${NC}"
    kubectl get pods -n $NAMESPACE
    exit 1
fi

# Test 2: Service discovery
echo -e "${BLUE}Test 2: Service discovery${NC}"
SERVICES=$(kubectl get services -n $NAMESPACE --no-headers | wc -l)
if [ $SERVICES -gt 0 ]; then
    echo -e "${GREEN}✓ Services are created ($SERVICES found)${NC}"
    kubectl get services -n $NAMESPACE
else
    echo -e "${RED}✗ No services found${NC}"
    exit 1
fi

# Test 3: MCP server health check (if health endpoint exists)
echo -e "${BLUE}Test 3: MCP server response${NC}"
MCP_POD=$(kubectl get pods -n $NAMESPACE -l app=talkgpt-mcp -o jsonpath='{.items[0].metadata.name}')
if [ -n "$MCP_POD" ]; then
    # Test if MCP server responds
    kubectl exec $MCP_POD -n $NAMESPACE -- curl -s http://localhost:8000/ > /tmp/mcp_response.txt || echo "MCP endpoint test failed"
    if [ -s /tmp/mcp_response.txt ]; then
        echo -e "${GREEN}✓ MCP server responds to requests${NC}"
    else
        echo -e "${YELLOW}⚠ MCP server response unclear, checking logs...${NC}"
        kubectl logs $MCP_POD -n $NAMESPACE --tail=10
    fi
    rm -f /tmp/mcp_response.txt
else
    echo -e "${RED}✗ No MCP pods found${NC}"
fi

# Test 4: Worker functionality
echo -e "${BLUE}Test 4: Worker readiness${NC}"
WORKER_PODS=$(kubectl get pods -n $NAMESPACE -l app=talkgpt-worker --no-headers | grep "Running" | wc -l)
if [ $WORKER_PODS -gt 0 ]; then
    echo -e "${GREEN}✓ Workers are running ($WORKER_PODS pods)${NC}"
else
    echo -e "${YELLOW}⚠ No worker pods running${NC}"
fi

# Test 5: Redis connectivity
echo -e "${BLUE}Test 5: Redis connectivity${NC}"
if [ -n "$MCP_POD" ]; then
    REDIS_TEST=$(kubectl exec $MCP_POD -n $NAMESPACE -- python -c "
import redis
import os
try:
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    r = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
    r.ping()
    print('SUCCESS')
except Exception as e:
    print(f'FAILED: {e}')
" 2>/dev/null || echo "FAILED")
    
    if echo "$REDIS_TEST" | grep -q "SUCCESS"; then
        echo -e "${GREEN}✓ Redis connection successful${NC}"
    else
        echo -e "${RED}✗ Redis connection failed: $REDIS_TEST${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Cannot test Redis (no MCP pod available)${NC}"
fi

# Test 6: Storage access
echo -e "${BLUE}Test 6: Cloud Storage access${NC}"
if [ -n "$MCP_POD" ]; then
    STORAGE_TEST=$(kubectl exec $MCP_POD -n $NAMESPACE -- python -c "
from google.cloud import storage
import os
try:
    project_id = os.environ.get('GCP_PROJECT_ID', '$PROJECT_ID')
    client = storage.Client(project=project_id)
    buckets = list(client.list_buckets(max_results=1))
    print('SUCCESS')
except Exception as e:
    print(f'FAILED: {e}')
" 2>/dev/null || echo "FAILED")
    
    if echo "$STORAGE_TEST" | grep -q "SUCCESS"; then
        echo -e "${GREEN}✓ Cloud Storage access successful${NC}"
    else
        echo -e "${YELLOW}⚠ Cloud Storage access issue: $STORAGE_TEST${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Cannot test storage (no MCP pod available)${NC}"
fi

# Test 7: External IP and ingress
echo -e "${BLUE}Test 7: External access${NC}"
EXTERNAL_IP=$(kubectl get ingress talkgpt-ingress -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
if [ -n "$EXTERNAL_IP" ] && [ "$EXTERNAL_IP" != "null" ]; then
    echo -e "${GREEN}✓ External IP assigned: $EXTERNAL_IP${NC}"
    
    # Test if external endpoint responds
    HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 http://$EXTERNAL_IP || echo "000")
    if [ "$HTTP_RESPONSE" != "000" ]; then
        echo -e "${GREEN}✓ External endpoint responds (HTTP $HTTP_RESPONSE)${NC}"
    else
        echo -e "${YELLOW}⚠ External endpoint not responding yet${NC}"
    fi
else
    echo -e "${YELLOW}⚠ External IP not yet assigned${NC}"
fi

# Test 8: Autoscaling configuration
echo -e "${BLUE}Test 8: Autoscaling status${NC}"
HPA_COUNT=$(kubectl get hpa -n $NAMESPACE --no-headers | wc -l)
if [ $HPA_COUNT -gt 0 ]; then
    echo -e "${GREEN}✓ Horizontal Pod Autoscalers configured ($HPA_COUNT)${NC}"
    kubectl get hpa -n $NAMESPACE
else
    echo -e "${YELLOW}⚠ No HPAs found${NC}"
fi

# Generate test report
echo -e "${BLUE}Generating test report...${NC}"
cat > test-report.txt << EOF
TalkGPT GCP Deployment Test Report
Generated: $(date)
Project: $PROJECT_ID
Cluster: $CLUSTER_NAME
Namespace: $NAMESPACE

=== Deployment Status ===
Pods Running: $PODS_READY/$TOTAL_PODS
Services: $SERVICES
Worker Pods: $WORKER_PODS
HPAs: $HPA_COUNT

=== External Access ===
External IP: ${EXTERNAL_IP:-"Not assigned"}

=== Pod Details ===
$(kubectl get pods -n $NAMESPACE -o wide)

=== Service Details ===
$(kubectl get services -n $NAMESPACE)

=== Ingress Details ===
$(kubectl get ingress -n $NAMESPACE)

=== Recent Events ===
$(kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -10)
EOF

echo -e "${GREEN}✓ Test report generated: test-report.txt${NC}"

# Create post-deployment checklist
cat > post-deployment-checklist.md << 'EOF'
# TalkGPT Post-Deployment Checklist

## Immediate Tasks
- [ ] Verify all pods are running: `kubectl get pods -n talkgpt`
- [ ] Check service endpoints: `kubectl get services -n talkgpt`
- [ ] Validate ingress configuration: `kubectl get ingress -n talkgpt`
- [ ] Test MCP server endpoint health
- [ ] Verify worker pods can access Redis and Cloud Storage

## Configuration Updates
- [ ] Update ingress.yaml with your actual domain name
- [ ] Configure SSL certificate for your domain
- [ ] Update Secret Manager with real API keys
- [ ] Configure monitoring alerts for your notification channels
- [ ] Set up log forwarding to your preferred destination

## Security Hardening
- [ ] Review and update network policies
- [ ] Audit service account permissions
- [ ] Enable Pod Security Standards
- [ ] Configure backup strategies for persistent data
- [ ] Review secrets and ensure no hardcoded credentials

## Performance Optimization
- [ ] Monitor resource usage and adjust requests/limits
- [ ] Fine-tune autoscaling parameters based on real workload
- [ ] Optimize container images for size and performance
- [ ] Set up cache warming strategies
- [ ] Configure appropriate resource quotas

## Monitoring & Observability
- [ ] Set up custom dashboards in Grafana
- [ ] Configure alerting rules in Prometheus
- [ ] Enable distributed tracing if needed
- [ ] Set up log aggregation and analysis
- [ ] Create runbooks for common operational tasks

## Backup & Disaster Recovery
- [ ] Configure automated backups for persistent storage
- [ ] Test backup restoration procedures
- [ ] Document disaster recovery procedures
- [ ] Set up multi-region deployment (if required)
- [ ] Create infrastructure as code for rapid recovery
EOF

# Summary
echo -e "${BLUE}=== Deployment Summary ===${NC}"
if [ $PODS_READY -gt 0 ] && [ $SERVICES -gt 0 ]; then
    echo -e "${GREEN}✓ Deployment appears successful!${NC}"
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Review test-report.txt for detailed status"
    echo "2. Complete items in post-deployment-checklist.md"
    echo "3. Update configuration with your domain and credentials"
    echo "4. Monitor the deployment and adjust resources as needed"
    
    if [ -n "$EXTERNAL_IP" ] && [ "$EXTERNAL_IP" != "null" ]; then
        echo -e "${BLUE}External IP: $EXTERNAL_IP${NC}"
        echo "Configure your DNS to point to this IP address"
    fi
else
    echo -e "${YELLOW}⚠ Deployment needs attention${NC}"
    echo "Review test-report.txt and check pod logs:"
    echo "kubectl logs -n $NAMESPACE -l app=talkgpt-mcp"
    echo "kubectl describe pods -n $NAMESPACE"
fi

echo -e "${BLUE}Useful commands:${NC}"
echo "kubectl get pods -n $NAMESPACE -w"
echo "kubectl logs -n $NAMESPACE -l app=talkgpt-mcp -f"
echo "kubectl port-forward -n $NAMESPACE service/talkgpt-mcp-service 8000:8000"

echo -e "${GREEN}✓ Deployment and testing completed!${NC}"