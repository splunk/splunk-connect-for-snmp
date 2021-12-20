{{/*
Expand the name of the chart.
*/}}
{{- define "splunk-connect-for-snmp.otel.name" -}}
{{- default (printf "%s-%s" .Chart.Name "otel")  .Values.otel.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "splunk-connect-for-snmp.otel.fullname" -}}
{{- if .Values.otel.fullnameOverride }}
{{- .Values.otel.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default (printf "%s-%s" .Chart.Name "otel") .Values.otel.nameOverride }}
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
{{- define "splunk-connect-for-snmp.otel.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "splunk-connect-for-snmp.otel.labels" -}}
helm.sh/chart: {{ include "splunk-connect-for-snmp.otel.chart" . }}
{{ include "splunk-connect-for-snmp.otel.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "splunk-connect-for-snmp.otel.selectorLabels" -}}
app.kubernetes.io/name: {{ include "splunk-connect-for-snmp.otel.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "splunk-connect-for-snmp.otel.serviceAccountName" -}}
{{- if .Values.otel.serviceAccount.create }}
{{- default (include "splunk-connect-for-snmp.otel.fullname" .) .Values.otel.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.otel.serviceAccount.name }}
{{- end }}
{{- end }}
