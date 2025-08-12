#!/bin/bash

# Set up comprehensive monitoring for TalkGPT on GCP

set -e

# Variables
PROJECT_ID="talkgpt-production"
REGION="us-central1"
NAMESPACE="talkgpt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up monitoring for TalkGPT...${NC}"

# Enable additional APIs for monitoring
echo -e "${BLUE}Enabling monitoring APIs...${NC}"
gcloud services enable \
  monitoring.googleapis.com \
  logging.googleapis.com \
  clouderrorreporting.googleapis.com \
  cloudtrace.googleapis.com \
  cloudprofiler.googleapis.com

# Create notification channels
echo -e "${BLUE}Creating notification channels...${NC}"

# Email notification channel (update with your email)
gcloud alpha monitoring channels create \
  --display-name="TalkGPT Alerts Email" \
  --type=email \
  --channel-labels=email_address=admin@yourdomain.com || echo "Notification channel already exists"

# Create custom metrics
echo -e "${BLUE}Creating custom metrics...${NC}"
cat <<'EOF' > /tmp/metrics.yaml
# Custom metrics for TalkGPT
resources:
- name: projects/talkgpt-production/metricDescriptors/custom.googleapis.com/talkgpt/transcription_requests
  type: custom.googleapis.com/talkgpt/transcription_requests
  labels:
  - key: service
  - key: status
  metricKind: COUNTER
  valueType: INT64
  displayName: "TalkGPT Transcription Requests"
  description: "Number of transcription requests processed"

- name: projects/talkgpt-production/metricDescriptors/custom.googleapis.com/talkgpt/processing_duration
  type: custom.googleapis.com/talkgpt/processing_duration
  labels:
  - key: service
  - key: model
  metricKind: GAUGE
  valueType: DOUBLE
  displayName: "TalkGPT Processing Duration"
  description: "Time taken to process transcription requests"
EOF

# Create alerting policies
echo -e "${BLUE}Creating alerting policies...${NC}"
cat <<EOF > /tmp/alerts.yaml
displayName: "TalkGPT High Error Rate"
documentation:
  content: "This alert fires when the error rate is above 5% for 5 minutes"
conditions:
- displayName: "High error rate condition"
  conditionThreshold:
    filter: 'resource.type="k8s_container" resource.label.namespace_name="talkgpt"'
    comparison: COMPARISON_GREATER_THAN
    thresholdValue: 0.05
    duration: 300s
    aggregations:
    - alignmentPeriod: 60s
      perSeriesAligner: ALIGN_RATE
      crossSeriesReducer: REDUCE_MEAN
      groupByFields:
      - resource.label.pod_name
alertStrategy:
  autoClose: 86400s
notificationChannels:
- $(gcloud alpha monitoring channels list --filter="displayName:TalkGPT" --format="value(name)" | head -1)
EOF

# Create dashboard
echo -e "${BLUE}Creating monitoring dashboard...${NC}"
cat <<'EOF' > /tmp/dashboard.json
{
  "displayName": "TalkGPT Monitoring Dashboard",
  "mosaicLayout": {
    "tiles": [
      {
        "width": 6,
        "height": 4,
        "widget": {
          "title": "Pod CPU Usage",
          "xyChart": {
            "dataSets": [{
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "resource.type=\"k8s_container\" resource.label.namespace_name=\"talkgpt\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE"
                  }
                }
              }
            }]
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "yPos": 0,
        "xPos": 6,
        "widget": {
          "title": "Pod Memory Usage",
          "xyChart": {
            "dataSets": [{
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "resource.type=\"k8s_container\" resource.label.namespace_name=\"talkgpt\" metric.type=\"kubernetes.io/container/memory/used_bytes\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_MEAN"
                  }
                }
              }
            }]
          }
        }
      },
      {
        "width": 12,
        "height": 4,
        "yPos": 4,
        "widget": {
          "title": "Request Rate",
          "xyChart": {
            "dataSets": [{
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "resource.type=\"k8s_container\" resource.label.namespace_name=\"talkgpt\" metric.type=\"logging.googleapis.com/user/http_requests\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM"
                  }
                }
              }
            }]
          }
        }
      }
    ]
  }
}
EOF

# Create the dashboard
gcloud monitoring dashboards create --config-from-file=/tmp/dashboard.json || echo "Dashboard already exists"

# Set up log-based metrics
echo -e "${BLUE}Creating log-based metrics...${NC}"
gcloud logging metrics create talkgpt_error_count \
  --description="Count of error logs from TalkGPT" \
  --log-filter='resource.type="k8s_container" resource.labels.namespace_name="talkgpt" severity>=ERROR' || echo "Metric already exists"

gcloud logging metrics create talkgpt_request_count \
  --description="Count of HTTP requests to TalkGPT" \
  --log-filter='resource.type="k8s_container" resource.labels.namespace_name="talkgpt" httpRequest.requestMethod!=""' || echo "Metric already exists"

# Set up log sinks for long-term storage
echo -e "${BLUE}Setting up log sinks...${NC}"
gsutil mb gs://$PROJECT_ID-logs || echo "Log bucket already exists"

gcloud logging sinks create talkgpt-logs-sink \
  gs://$PROJECT_ID-logs \
  --log-filter='resource.type="k8s_container" resource.labels.namespace_name="talkgpt"' || echo "Sink already exists"

# Install Prometheus and Grafana for additional monitoring
echo -e "${BLUE}Installing Prometheus and Grafana...${NC}"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts || true
helm repo add grafana https://grafana.github.io/helm-charts || true
helm repo update || true

# Install Prometheus
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.adminPassword=admin123 \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=50Gi || echo "Prometheus already installed"

# Create ServiceMonitor for TalkGPT
cat <<EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: talkgpt-metrics
  namespace: monitoring
  labels:
    app: talkgpt
    release: prometheus
spec:
  selector:
    matchLabels:
      app: talkgpt-mcp
  namespaceSelector:
    matchNames:
    - talkgpt
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
EOF

# Create PrometheusRule for alerts
cat <<EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: talkgpt-alerts
  namespace: monitoring
  labels:
    app: talkgpt
    release: prometheus
spec:
  groups:
  - name: talkgpt
    rules:
    - alert: TalkGPTHighErrorRate
      expr: rate(http_requests_total{job="talkgpt-mcp",status=~"5.*"}[5m]) > 0.05
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High error rate detected in TalkGPT"
        description: "Error rate is {{ \$value }} errors per second"
    
    - alert: TalkGPTHighMemoryUsage
      expr: container_memory_usage_bytes{namespace="talkgpt"} / container_spec_memory_limit_bytes > 0.9
      for: 10m
      labels:
        severity: critical
      annotations:
        summary: "High memory usage in TalkGPT pod"
        description: "Memory usage is above 90% in pod {{ \$labels.pod }}"
        
    - alert: TalkGPTHighCPUUsage
      expr: rate(container_cpu_usage_seconds_total{namespace="talkgpt"}[5m]) > 0.8
      for: 10m
      labels:
        severity: warning
      annotations:
        summary: "High CPU usage in TalkGPT pod"
        description: "CPU usage is above 80% in pod {{ \$labels.pod }}"
EOF

# Clean up temp files
rm -f /tmp/metrics.yaml /tmp/alerts.yaml /tmp/dashboard.json

# Output monitoring endpoints
echo -e "${GREEN}✓ Monitoring setup completed!${NC}"
echo -e "${BLUE}Monitoring endpoints:${NC}"
echo "  - Cloud Monitoring: https://console.cloud.google.com/monitoring"
echo "  - Cloud Logging: https://console.cloud.google.com/logs"
echo "  - Prometheus: kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090"
echo "  - Grafana: kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80"
echo ""
echo -e "${BLUE}Grafana credentials:${NC}"
echo "  - Username: admin"
echo "  - Password: admin123"
echo ""
echo -e "${BLUE}Next: Set up CI/CD pipeline with setup-cicd.sh${NC}"