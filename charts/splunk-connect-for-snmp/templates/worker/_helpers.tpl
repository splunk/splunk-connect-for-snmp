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
Common labels
*/}}
{{- define "splunk-connect-for-snmp.worker.labels" -}}
helm.sh/chart: {{ include "splunk-connect-for-snmp.worker.chart" . }}
{{ include "splunk-connect-for-snmp.worker.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
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

{{- define "splunk-connect-for-snmp.worker.trap.labels" -}}
helm.sh/chart: {{ include "splunk-connect-for-snmp.worker.chart" . }}
{{ include "splunk-connect-for-snmp.worker.trap.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "splunk-connect-for-snmp.worker.poller.labels" -}}
helm.sh/chart: {{ include "splunk-connect-for-snmp.worker.chart" . }}
{{ include "splunk-connect-for-snmp.worker.poller.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "splunk-connect-for-snmp.worker.sender.labels" -}}
helm.sh/chart: {{ include "splunk-connect-for-snmp.worker.chart" . }}
{{ include "splunk-connect-for-snmp.worker.sender.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
{{/*
Create the name of the service account to use
*/}}
{{- define "splunk-connect-for-snmp.worker.serviceAccountName" -}}
{{- if .Values.worker.serviceAccount.create }}
{{- default (include "splunk-connect-for-snmp.worker.fullname" .) .Values.worker.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.worker.serviceAccount.name }}
{{- end }}
{{- end }}