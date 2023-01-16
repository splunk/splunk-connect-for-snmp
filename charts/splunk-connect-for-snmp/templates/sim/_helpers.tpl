{{/*
Expand the name of the chart.
*/}}
{{- define "splunk-connect-for-snmp.sim.name" -}}
{{- default (printf "%s-%s" .Chart.Name "sim")  .Values.sim.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "splunk-connect-for-snmp.sim.fullname" -}}
{{- if .Values.sim.fullnameOverride }}
{{- .Values.sim.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default (printf "%s-%s" .Chart.Name "sim") .Values.sim.nameOverride }}
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
{{- define "splunk-connect-for-snmp.sim.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "splunk-connect-for-snmp.sim.labels" -}}
helm.sh/chart: {{ include "splunk-connect-for-snmp.sim.chart" . }}
{{ include "splunk-connect-for-snmp.sim.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "splunk-connect-for-snmp.sim.selectorLabels" -}}
app.kubernetes.io/name: {{ include "splunk-connect-for-snmp.sim.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Define name for the Splunk Secret
*/}}
{{- define "splunk-connect-for-snmp.sim.secret" -}}
{{- if .Values.sim.secret.name -}}
{{- printf "%s" .Values.sim.secret.name -}}
{{- else -}}
{{ include "splunk-connect-for-snmp.name" . }}-sim
{{- end -}}
{{- end -}}

