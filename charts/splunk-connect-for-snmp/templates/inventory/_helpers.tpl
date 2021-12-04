{{/*
Expand the name of the chart.
*/}}
{{- define "splunk-connect-for-snmp.inventory.name" -}}
{{- default (printf "%s-%s" .Chart.Name "inventory")  .Values.inventory.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "splunk-connect-for-snmp.inventory.fullname" -}}
{{- if .Values.inventory.fullnameOverride }}
{{- .Values.inventory.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default (printf "%s-%s" .Chart.Name "inventory") .Values.inventory.nameOverride }}
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
{{- define "splunk-connect-for-snmp.inventory.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "splunk-connect-for-snmp.inventory.labels" -}}
helm.sh/chart: {{ include "splunk-connect-for-snmp.inventory.chart" . }}
{{ include "splunk-connect-for-snmp.inventory.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "splunk-connect-for-snmp.inventory.selectorLabels" -}}
app.kubernetes.io/name: {{ include "splunk-connect-for-snmp.inventory.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "splunk-connect-for-snmp.inventory.serviceAccountName" -}}
{{- if .Values.inventory.serviceAccount.create }}
{{- default (include "splunk-connect-for-snmp.inventory.fullname" .) .Values.inventory.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.inventory.serviceAccount.name }}
{{- end }}
{{- end }}
