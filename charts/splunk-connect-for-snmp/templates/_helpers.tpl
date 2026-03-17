{{- define "splunk-connect-for-snmp.mongo_uri" -}}
{{- if eq .Values.mongodb.architecture "replicaset" }}
{{- printf "mongodb+srv://%s-mongodb-headless.%s.svc.%s/?tls=false&ssl=false&replicaSet=rs0" .Release.Name .Release.Namespace .Values.mongodb.clusterDomain}}
{{- else }}
{{- printf "mongodb://%s-mongodb:27017" .Release.Name }}
{{- end }}  
{{- end }}  

{{- define "splunk-connect-for-snmp.mongodbHost" -}}
{{- if .Values.mongodbHost }}
{{- .Values.mongodbHost | quote }}
{{- else }}
{{- printf "%s-mongodb.%s.svc.cluster.local" .Release.Name .Release.Namespace }}
{{- end }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "splunk-connect-for-snmp.fullname" -}}
{{- if .Values.worker.fullnameOverride }}
{{- .Values.worker.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default (printf "%s-%s" .Chart.Name "user") .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "splunk-connect-for-snmp.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "splunk-connect-for-snmp.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "splunk-connect-for-snmp.labels" -}}
helm.sh/chart: {{ include "splunk-connect-for-snmp.chart" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "splunk-connect-for-snmp.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "splunk-connect-for-snmp.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "splunk-connect-for-snmp.name" -}}
{{- default (printf "%s" .Chart.Name ) .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Name of the secret containing the Splunk HEC token. Uses tokenSecretRef.name
when set, otherwise the chart-created secret (requires splunk.token to be set).
*/}}
{{- define "splunk-connect-for-snmp.splunkHecTokenSecretName" -}}
{{- if .Values.splunk.tokenSecretRef.name -}}
{{- .Values.splunk.tokenSecretRef.name -}}
{{- else -}}
{{- printf "%s-splunk" (include "splunk-connect-for-snmp.name" .) -}}
{{- end -}}
{{- end }}

{{/*
Key within the secret for the Splunk HEC token. Uses tokenSecretRef.key when
tokenSecretRef.name is set, otherwise "hec_token".
*/}}
{{- define "splunk-connect-for-snmp.splunkHecTokenSecretKey" -}}
{{- if .Values.splunk.tokenSecretRef.name -}}
{{- .Values.splunk.tokenSecretRef.key | default "hec_token" -}}
{{- else -}}
hec_token
{{- end -}}
{{- end }}

{{/*
Whether the HEC token is provided via a file (tokenFilePath set).
When true, set SPLUNK_HEC_TOKEN_FILE and do not set SPLUNK_HEC_TOKEN from secretKeyRef.
*/}}
{{- define "splunk-connect-for-snmp.splunkHecTokenFromFile" -}}
{{- if .Values.splunk.tokenFilePath -}}
true
{{- end -}}
{{- end }}

{{/*
Whether enable traps
*/}}
{{- define "splunk-connect-for-snmp.traps.enable" -}}
{{- if or (and (eq .Values.traps.service.type "LoadBalancer") .Values.traps.loadBalancerIP ) (and (eq .Values.traps.service.type "NodePort") .Values.traps.service.nodePort ) ( not .Values.traps.service.usemetallb) }}
{{- printf "true" }}
{{- else }}
{{- printf "false" }}
{{- end -}}
{{- end }}

{{/*
Whether enable polling
*/}}
{{- define "splunk-connect-for-snmp.polling.enable" -}}
{{- if .Values.poller.inventory }}
{{- printf "true" }}
{{- else }}
{{- printf "false" }}
{{- end -}}
{{- end }}

{{- /*
Generate Redis environment variables for application pods
*/ -}}
{{- define "splunk-connect-for-snmp.redis-env" -}}
{{- if eq .Values.redis.architecture "replication" -}}
- name: REDIS_MODE
  value: "replication"
- name: REDIS_SENTINEL_SERVICE
  value: {{ .Release.Name }}-redis-sentinel
- name: REDIS_HEADLESS_SERVICE
  value: {{ .Release.Name }}-redis-headless
- name: NAMESPACE
  value: {{ .Release.Namespace }}
- name: REDIS_SENTINEL_REPLICAS
  value: {{ .Values.redis.sentinel.replicas | quote }}
- name: REDIS_SENTINEL_PORT
  value: "26379"
- name: REDIS_MASTER_NAME
  value: mymaster
{{- else -}}
- name: REDIS_MODE
  value: "standalone"
- name: REDIS_HOST
  value: {{ .Release.Name }}-redis
- name: REDIS_PORT
  value: "6379"
{{- end }}
- name: REDIS_DB
  value: "1"
- name: CELERY_DB
  value: "0"
{{- if .Values.redis.auth.enabled }}
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      {{- if .Values.redis.auth.existingSecret }}
      name: {{ .Values.redis.auth.existingSecret }}
      key: {{ .Values.redis.auth.existingSecretPasswordKey | default "password" }}
      {{- else }}
      name: {{ .Release.Name }}-redis-secret
      key: password
      {{- end }}
{{- end -}}
{{- end -}}

{{- /*
Generate Redis environment variables for application pods
*/ -}}
{{- define "splunk-connect-for-snmp.redis-annotations" -}}
{{- if eq .Values.redis.architecture "replication" -}}
checksum/redis-config: {{ include (print $.Template.BasePath "/redis/redis-ha-config.yaml") . | sha256sum }}
{{- else -}}
checksum/redis-config: {{ include (print $.Template.BasePath "/redis/redis-config.yaml") . | sha256sum }}
{{- end -}}
{{- if .Values.redis.auth.enabled }}
checksum/redis-secret: {{ include (print $.Template.BasePath "/redis/redis-secret.yaml") . | sha256sum }}
{{- end -}}
{{- end -}}