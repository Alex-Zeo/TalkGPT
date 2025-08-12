#!/bin/bash

# Set up comprehensive autoscaling for TalkGPT on GCP

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
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up autoscaling for TalkGPT...${NC}"

# Ensure we're connected to the cluster
gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION

# Enable cluster autoscaling on existing node pools
echo -e "${BLUE}Enabling cluster autoscaling...${NC}"
gcloud container clusters update $CLUSTER_NAME \
  --region=$REGION \
  --enable-autoscaling \
  --node-pool=cpu-pool \
  --min-nodes=1 \
  --max-nodes=10 || echo "CPU pool autoscaling already configured"

gcloud container clusters update $CLUSTER_NAME \
  --region=$REGION \
  --enable-autoscaling \
  --node-pool=gpu-pool \
  --min-nodes=0 \
  --max-nodes=5 || echo "GPU pool autoscaling already configured"

# Install Metrics Server (required for HPA)
echo -e "${BLUE}Installing Metrics Server...${NC}"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml || echo "Metrics Server already installed"

# Wait for Metrics Server to be ready
echo -e "${BLUE}Waiting for Metrics Server to be ready...${NC}"
kubectl wait --for=condition=ready pod -l k8s-app=metrics-server -n kube-system --timeout=120s || true

# Create comprehensive HPA configurations
echo -e "${BLUE}Creating advanced HPA configurations...${NC}"

# MCP Server HPA with custom metrics
cat <<EOF | kubectl apply -f -
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: talkgpt-mcp-hpa-advanced
  namespace: $NAMESPACE
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: talkgpt-mcp
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 70
  # Scale based on concurrent connections (requires custom metrics)
  - type: Pods
    pods:
      metric:
        name: concurrent_connections
      target:
        type: AverageValue
        averageValue: "30"
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
      - type: Pods
        value: 2
        periodSeconds: 60
      selectPolicy: Min
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
      - type: Pods
        value: 4
        periodSeconds: 60
      selectPolicy: Max
EOF

# CPU Worker HPA
cat <<EOF | kubectl apply -f -
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: talkgpt-worker-cpu-hpa-advanced
  namespace: $NAMESPACE
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: talkgpt-worker-cpu
  minReplicas: 1
  maxReplicas: 15
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 75
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  # Scale based on queue depth (requires custom metrics)
  - type: Object
    object:
      metric:
        name: redis_queue_depth
      target:
        type: Value
        value: "10"
      describedObject:
        apiVersion: v1
        kind: Service
        name: redis-service
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 600
      policies:
      - type: Percent
        value: 20
        periodSeconds: 120
      selectPolicy: Min
    scaleUp:
      stabilizationWindowSeconds: 120
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
      - type: Pods
        value: 3
        periodSeconds: 60
      selectPolicy: Max
EOF

# GPU Worker HPA (more conservative)
cat <<EOF | kubectl apply -f -
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: talkgpt-worker-gpu-hpa
  namespace: $NAMESPACE
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: talkgpt-worker-gpu
  minReplicas: 0
  maxReplicas: 3
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: nvidia.com/gpu
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 900
      policies:
      - type: Pods
        value: 1
        periodSeconds: 180
    scaleUp:
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 1
        periodSeconds: 120
EOF

# Create Vertical Pod Autoscaler configurations
echo -e "${BLUE}Setting up Vertical Pod Autoscaler...${NC}"

# Install VPA if not already installed
kubectl apply -f https://github.com/kubernetes/autoscaler/releases/latest/download/vpa-crd.yaml || echo "VPA CRDs already exist"
kubectl apply -f https://github.com/kubernetes/autoscaler/releases/latest/download/vpa-rbac.yaml || echo "VPA RBAC already exists"

# VPA for MCP server (recommendation mode)
cat <<EOF | kubectl apply -f -
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: talkgpt-mcp-vpa
  namespace: $NAMESPACE
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: talkgpt-mcp
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: mcp-server
      maxAllowed:
        cpu: 1
        memory: 2Gi
      minAllowed:
        cpu: 100m
        memory: 256Mi
      controlledResources: ["cpu", "memory"]
EOF

# VPA for CPU workers
cat <<EOF | kubectl apply -f -
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: talkgpt-worker-cpu-vpa
  namespace: $NAMESPACE
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: talkgpt-worker-cpu
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: celery-worker
      maxAllowed:
        cpu: 4
        memory: 8Gi
      minAllowed:
        cpu: 500m
        memory: 1Gi
      controlledResources: ["cpu", "memory"]
EOF

# Create custom metrics for queue-based scaling
echo -e "${BLUE}Setting up custom metrics...${NC}"

# Install Prometheus Adapter for custom metrics
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts || true
helm repo update || true

helm upgrade --install prometheus-adapter prometheus-community/prometheus-adapter \
  --namespace monitoring \
  --create-namespace \
  --set-file config.custom=- <<EOF
rules:
- seriesQuery: 'redis_queue_length{namespace="$NAMESPACE"}'
  resources:
    overrides:
      namespace: {resource: "namespace"}
      service: {resource: "service", group: "", version: "v1"}
  name:
    matches: "^redis_queue_(.+)"
    as: "redis_queue_depth"
  metricsQuery: 'avg(<<.Series>>{<<.LabelMatchers>>}) by (<<.GroupBy>>)'

- seriesQuery: 'http_requests_per_second{namespace="$NAMESPACE"}'
  resources:
    overrides:
      namespace: {resource: "namespace"}
      pod: {resource: "pod", group: "", version: "v1"}
  name:
    matches: "^http_requests_(.+)"
    as: "concurrent_connections"
  metricsQuery: 'avg(<<.Series>>{<<.LabelMatchers>>}) by (<<.GroupBy>>)'
EOF

# Create KEDA (Kubernetes Event-driven Autoscaler) configuration for advanced scaling
echo -e "${BLUE}Installing KEDA for event-driven autoscaling...${NC}"
helm repo add kedacore https://kedacore.github.io/charts || true
helm repo update || true

helm upgrade --install keda kedacore/keda \
  --namespace keda-system \
  --create-namespace || echo "KEDA already installed"

# Create KEDA ScaledObject for Redis queue-based scaling
cat <<EOF | kubectl apply -f -
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: talkgpt-worker-cpu-scaler
  namespace: $NAMESPACE
spec:
  scaleTargetRef:
    name: talkgpt-worker-cpu
  minReplicaCount: 1
  maxReplicaCount: 20
  pollingInterval: 30
  cooldownPeriod: 300
  triggers:
  - type: redis
    metadata:
      address: $(kubectl get secret talkgpt-secrets -o jsonpath='{.data.redis-url}' | base64 -d)
      listName: celery
      listLength: '5'
      enableTLS: 'false'
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: talkgpt-worker-gpu-scaler
  namespace: $NAMESPACE
spec:
  scaleTargetRef:
    name: talkgpt-worker-gpu
  minReplicaCount: 0
  maxReplicaCount: 3
  pollingInterval: 60
  cooldownPeriod: 600
  triggers:
  - type: redis
    metadata:
      address: $(kubectl get secret talkgpt-secrets -o jsonpath='{.data.redis-url}' | base64 -d)
      listName: gpu_queue
      listLength: '2'
      enableTLS: 'false'
EOF

# Create cluster autoscaler configuration
echo -e "${BLUE}Configuring cluster autoscaler settings...${NC}"
kubectl patch deployment cluster-autoscaler \
  -n kube-system \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"cluster-autoscaler","command":["./cluster-autoscaler","--v=4","--stderrthreshold=info","--cloud-provider=gce","--skip-nodes-with-local-storage=false","--expander=least-waste","--node-group-auto-discovery=mig:name=gke-talkgpt-cluster-cpu-pool-.*,mig:name=gke-talkgpt-cluster-gpu-pool-.*","--balance-similar-node-groups","--skip-nodes-with-system-pods=false","--scale-down-delay-after-add=10m","--scale-down-unneeded-time=10m","--scale-down-utilization-threshold=0.5","--max-node-provision-time=15m"]}]}}}}' || echo "Cluster autoscaler already configured"

# Create monitoring for autoscaling
echo -e "${BLUE}Creating autoscaling monitoring dashboard...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: autoscaling-dashboard
  namespace: monitoring
data:
  dashboard.json: |
    {
      "dashboard": {
        "title": "TalkGPT Autoscaling",
        "panels": [
          {
            "title": "HPA Status",
            "type": "stat",
            "targets": [{
              "expr": "kube_horizontalpodautoscaler_status_current_replicas{namespace=\"$NAMESPACE\"}"
            }]
          },
          {
            "title": "Node Count",
            "type": "stat",
            "targets": [{
              "expr": "count(kube_node_info)"
            }]
          },
          {
            "title": "Pod Resource Usage",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(container_cpu_usage_seconds_total{namespace=\"$NAMESPACE\"}[5m])"
              },
              {
                "expr": "container_memory_usage_bytes{namespace=\"$NAMESPACE\"}"
              }
            ]
          }
        ]
      }
    }
EOF

# Create alerting rules for autoscaling
cat <<EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: talkgpt-autoscaling-alerts
  namespace: monitoring
  labels:
    prometheus: kube-prometheus
    role: alert-rules
spec:
  groups:
  - name: talkgpt.autoscaling
    rules:
    - alert: HPAMaxReplicas
      expr: kube_horizontalpodautoscaler_status_current_replicas{namespace="$NAMESPACE"} >= kube_horizontalpodautoscaler_spec_max_replicas{namespace="$NAMESPACE"}
      for: 10m
      labels:
        severity: warning
      annotations:
        summary: "HPA has reached maximum replicas"
        description: "HPA {{ \$labels.horizontalpodautoscaler }} has been at maximum replicas for more than 10 minutes"
    
    - alert: ClusterAutoscalerErrors
      expr: increase(cluster_autoscaler_errors_total[10m]) > 5
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "Cluster autoscaler is experiencing errors"
        description: "Cluster autoscaler has encountered {{ \$value }} errors in the last 10 minutes"
    
    - alert: NodeUtilizationHigh
      expr: (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))) > 0.8
      for: 15m
      labels:
        severity: warning
      annotations:
        summary: "High node CPU utilization"
        description: "Cluster CPU utilization has been above 80% for 15 minutes"
EOF

echo -e "${GREEN}✓ Autoscaling setup completed!${NC}"
echo -e "${BLUE}Autoscaling Components:${NC}"
echo "  - Horizontal Pod Autoscaler (HPA) - CPU/Memory based"
echo "  - Vertical Pod Autoscaler (VPA) - Resource optimization"
echo "  - KEDA - Event-driven autoscaling"
echo "  - Cluster Autoscaler - Node scaling"
echo ""
echo -e "${BLUE}Scaling Behavior:${NC}"
echo "  - MCP Server: 2-20 replicas"
echo "  - CPU Workers: 1-15 replicas"
echo "  - GPU Workers: 0-3 replicas"
echo "  - CPU Nodes: 1-10 nodes"
echo "  - GPU Nodes: 0-5 nodes"
echo ""
echo -e "${BLUE}Monitoring:${NC}"
echo "  kubectl get hpa -n $NAMESPACE"
echo "  kubectl get vpa -n $NAMESPACE"
echo "  kubectl describe scaledobject -n $NAMESPACE"
echo ""
echo -e "${BLUE}Next: Test deployment with deploy-and-test.sh${NC}"