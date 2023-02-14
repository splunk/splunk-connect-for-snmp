{{/*
Expand the name of the chart.
*/}}
{{- define "splunk-connect-for-snmp.worker.name" -}}
{{- default (printf "%s-%s" .Chart.Name "worker") .Values.worker.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "splunk-connect-for-snmp.worker.fullname" -}}
{{- if .Values.worker.fullnameOverride }}
{{- .Values.worker.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default (printf "%s-%s" .Chart.Name "worker") .Values.worker.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "splunk-connect-for-snmp.worker.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
Selector labels
*/}}
{{- define "splunk-connect-for-snmp.worker.selectorLabels" -}}
app.kubernetes.io/name: {{ include "splunk-connect-for-snmp.worker.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "splunk-connect-for-snmp.worker.poller.selectorLabels" -}}
app.kubernetes.io/name: {{ include "splunk-connect-for-snmp.worker.name" . }}-poller
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "splunk-connect-for-snmp.worker.sender.selectorLabels" -}}
app.kubernetes.io/name: {{ include "splunk-connect-for-snmp.worker.name" . }}-sender
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "splunk-connect-for-snmp.worker.trap.selectorLabels" -}}
app.kubernetes.io/name: {{ include "splunk-connect-for-snmp.worker.name" . }}-trap
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}


{{/*
Common labels
*/}}
{{- define "splunk-connect-for-snmp.worker.poller.labels" -}}
{{ include "splunk-connect-for-snmp.worker.poller.selectorLabels" . }}
{{ include "splunk-connect-for-snmp.labels" . }}
{{- end }}

{{- define "splunk-connect-for-snmp.worker.trap.labels" -}}
{{ include "splunk-connect-for-snmp.worker.trap.selectorLabels" . }}
{{ include "splunk-connect-for-snmp.labels" . }}
{{- end }}

{{- define "splunk-connect-for-snmp.worker.sender.labels" -}}
{{ include "splunk-connect-for-snmp.worker.sender.selectorLabels" . }}
{{ include "splunk-connect-for-snmp.labels" . }}
{{- end }}

{{- define "splunk-connect-for-snmp.worker.labels" -}}
{{ include "splunk-connect-for-snmp.worker.selectorLabels" . }}
{{ include "splunk-connect-for-snmp.labels" . }}
{{- end }}

{{- define "environmental-variables" -}}
- name: CONFIG_PATH
  value: /app/config/config.yaml
- name: REDIS_URL
  value: {{ include "splunk-connect-for-snmp.redis_url" . }}
- name: SC4SNMP_VERSION
  value: {{ .Chart.Version | default "0.0.0" }}
- name: CELERY_BROKER_URL
  value: {{ include "splunk-connect-for-snmp.celery_url" . }}
- name: MONGO_URI
  value: {{ include "splunk-connect-for-snmp.mongo_uri" . }}
- name: WALK_RETRY_MAX_INTERVAL
  value: {{ .Values.worker.walkRetryMaxInterval | default "600" | quote }}
- name: METRICS_INDEXING_ENABLED
  value: {{ (.Values.poller).metricsIndexingEnabled | default "false" | quote }}
{{- if .Values.worker.ignoreNotIncreasingOid }}
- name: IGNORE_NOT_INCREASING_OIDS
  value: {{ join "," .Values.worker.ignoreNotIncreasingOid }}
{{- end}}
{{- if .Values.sim.enabled }}
- name: OTEL_METRICS_URL
  value: "http://{{ .Release.Name }}-{{ include "splunk-connect-for-snmp.name" . }}-sim:8882"
{{- end}}
- name: LOG_LEVEL
  value: {{ .Values.worker.logLevel | default "INFO" }}
- name: UDP_CONNECTION_TIMEOUT
  value: {{ .Values.worker.udpConnectionTimeout | default "3" | quote }}
- name: PROFILES_RELOAD_DELAY
  value: {{ .Values.worker.profilesReloadDelay | default "60" | quote }}
- name: MIB_SOURCES
  value: "http://{{ printf "%s-%s" .Release.Name "mibserver" }}/asn1/@mib@"
- name: MIB_INDEX
  value: "http://{{ printf "%s-%s" .Release.Name "mibserver" }}/index.csv"
- name: MIB_STANDARD
  value: "http://{{ printf "%s-%s" .Release.Name "mibserver" }}/standard.txt"
{{- if .Values.splunk.enabled }}
{{- if .Values.splunk.protocol }}
- name: SPLUNK_HEC_SCHEME
  value: {{ .Values.splunk.protocol | default "https" | quote }}
{{- end}}
- name: SPLUNK_HEC_HOST
  value: {{ .Values.splunk.host | quote }}
- name: IGNORE_EMPTY_VARBINDS
  value: {{ .Values.worker.ignoreEmptyVarbinds | default "false" | quote }}
{{- if .Values.splunk.port }}
- name: SPLUNK_HEC_PORT
  value: {{ .Values.splunk.port | default "" | quote }}
{{- end}}
{{- if .Values.splunk.path }}
- name: SPLUNK_HEC_PATH
  value: {{ .Values.splunk.path | default "/services/collector" | quote }}
{{- end}}
- name: SPLUNK_HEC_INSECURESSL
  value: {{ .Values.splunk.insecureSSL | default "false" | quote }}
- name: SPLUNK_HEC_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ include "splunk-connect-for-snmp.name" . }}-splunk
      key: hec_token
{{- if .Values.splunk.eventIndex }}
- name: SPLUNK_HEC_INDEX_EVENTS
  value: {{ .Values.splunk.eventIndex | default "netops" }}
{{- end}}
{{- if .Values.splunk.metricsIndex }}
- name: SPLUNK_HEC_INDEX_METRICS
  value: {{ .Values.splunk.metricsIndex | default "netmetrics" }}
{{- end}}
{{- end}}
{{- end }}

{{- define "environmental-variables-poller" -}}
- name: WORKER_CONCURRENCY
  value: {{ .Values.worker.poller.concurrency | default "2" | quote }}
- name: PREFETCH_COUNT
  value: {{ .Values.worker.poller.prefetch | default "1" | quote }}
{{- end }}

{{- define "environmental-variables-sender" -}}
- name: WORKER_CONCURRENCY
  value: {{ .Values.worker.sender.concurrency | default "2" | quote }}
- name: PREFETCH_COUNT
  value: {{ .Values.worker.sender.prefetch | default "1" | quote }}
{{- end }}

{{- define "environmental-variables-trap" -}}
- name: WORKER_CONCURRENCY
  value: {{ .Values.worker.trap.concurrency | default "2" | quote }}
- name: PREFETCH_COUNT
  value: {{ .Values.worker.trap.prefetch | default "1" | quote }}
{{- end }}