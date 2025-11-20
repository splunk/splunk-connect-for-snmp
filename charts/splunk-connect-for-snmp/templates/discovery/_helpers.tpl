{{/*
Expand the name of the chart.
*/}}
{{- define "splunk-connect-for-snmp.discovery.name" -}}
{{- default (printf "%s-%s" .Chart.Name "discovery")  .Values.discovery.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "splunk-connect-for-snmp.discovery.fullname" -}}
{{- if .Values.discovery.fullnameOverride }}
{{- .Values.discovery.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default (printf "%s-%s" .Chart.Name "discovery") .Values.discovery.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Not using it anywhere
*/}}
{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "splunk-connect-for-snmp.discovery.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "splunk-connect-for-snmp.discovery.selectorLabels" -}}
app.kubernetes.io/name: {{ include "splunk-connect-for-snmp.discovery.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "splunk-connect-for-snmp.discovery.labels" -}}
{{ include "splunk-connect-for-snmp.discovery.selectorLabels" . }}
{{ include "splunk-connect-for-snmp.labels" . }}
{{- end }}
