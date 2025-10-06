{{- define "splunk-connect-for-snmp.mongo_uri" -}}

{{- if or (not (empty .Values.mongodb.auth.existingSecret)) (not (empty .Values.mongodb.auth.rootPassword)) }}
    {{- $mongoPassword := "" }}

    {{- if (not (empty .Values.mongodb.auth.existingSecret)) }}
        {{- $mongoSecretName := .Values.mongodb.auth.existingSecret }}
        {{- $mongoSecret := lookup "v1" "Secret" .Release.Namespace $mongoSecretName }}

        {{- if not $mongoSecret }}
            {{- fail (printf "Secret '%s' not found in namespace '%s'. Please create it before deploying." $mongoSecretName .Release.Namespace) }}
        {{- end }}

        {{- $mongoPassword = get $mongoSecret.data "mongodb-root-password" | b64dec }}
    {{- else }}
        {{- $mongoPassword = .Values.mongodb.auth.rootPassword }}
    {{- end }}

    {{- if eq .Values.mongodb.architecture "replicaset" }}
        {{- printf "mongodb+srv://root:%s@%s-mongodb-headless.%s.svc.%s/?tls=false&ssl=false&replicaSet=rs0"  $mongoPassword .Release.Name .Release.Namespace .Values.mongodb.clusterDomain}}
    {{- else }}
        {{- printf "mongodb://root:%s@%s-mongodb:27017" $mongoPassword  .Release.Name }}
    {{- end }}
{{- else }}

{{- if eq .Values.mongodb.architecture "replicaset" }}
{{- printf "mongodb+srv://%s-mongodb-headless.%s.svc.%s/?tls=false&ssl=false&replicaSet=rs0" .Release.Name .Release.Namespace .Values.mongodb.clusterDomain}}
{{- else }}
{{- printf "mongodb://%s-mongodb:27017" .Release.Name }}
{{- end }}

{{- end }}
{{- end }}

{{- define "splunk-connect-for-snmp.mongodbHost" -}}
{{- if .Values.mongodbHost }}
{{- .Values.mongodbHost | quote }}
{{- else }}
{{- printf "%s-mongodb.%s.svc.cluster.local" .Release.Name .Release.Namespace }}
{{- end }}
{{- end }}

{{- define "splunk-connect-for-snmp.celery_url" -}}

{{- if or (not (empty .Values.redis.auth.existingSecret)) (not (empty .Values.redis.auth.password)) }}

    {{- $redisPassword := "" }}

    {{- if (not (empty .Values.redis.auth.existingSecret)) }}
        {{- $redisSecretName := .Values.redis.auth.existingSecret }}
        {{- $redisSecret := lookup "v1" "Secret" .Release.Namespace $redisSecretName }}

        {{- if not $redisSecret }}
            {{- fail (printf "Secret '%s' not found in namespace '%s'. Please create it before deploying." $redisSecretName .Release.Namespace) }}
        {{- end }}

        {{- $redisPassword = get $redisSecret.data "redis-password" | b64dec }}
    {{- else }}
        {{- $redisPassword = .Values.redis.auth.password }}
    {{- end }}

    {{- if and ( eq .Values.redis.architecture "replication" ) .Values.redis.sentinel.enabled  }}
        {{- printf "redis://:%s@%s-redis:6379/0" $redisPassword .Release.Name }}
    {{- else }}
        {{- printf "redis://:%s@%s-redis-master:6379/0" $redisPassword .Release.Name }}
    {{- end }}
{{- else }}


{{- if and ( eq .Values.redis.architecture "replication" ) .Values.redis.sentinel.enabled  }}
{{- printf "redis://%s-redis:6379/0" .Release.Name }}
{{- else }}
{{- printf "redis://%s-redis-master:6379/0" .Release.Name }}
{{- end }}

{{- end }}
{{- end }}

{{- define "splunk-connect-for-snmp.redis_url" -}}

{{- if or (not (empty .Values.redis.auth.existingSecret)) (not (empty .Values.redis.auth.password)) }}

    {{- $redisPassword := "" }}

    {{- if (not (empty .Values.redis.auth.existingSecret)) }}
        {{- $redisSecretName := .Values.redis.auth.existingSecret }}
        {{- $redisSecret := lookup "v1" "Secret" .Release.Namespace $redisSecretName }}

        {{- if not $redisSecret }}
            {{- fail (printf "Secret '%s' not found in namespace '%s'. Please create it before deploying." $redisSecretName .Release.Namespace) }}
        {{- end }}

        {{- $redisPassword = get $redisSecret.data "redis-password" | b64dec }}
    {{- else }}
        {{- $redisPassword = .Values.redis.auth.password }}
    {{- end }}

    {{- if and ( eq .Values.redis.architecture "replication" ) .Values.redis.sentinel.enabled  }}
        {{- printf "redis://:%s@%s-redis:6379/1" $redisPassword .Release.Name }}
    {{- else }}
        {{- printf "redis://:%s@%s-redis-master:6379/1" $redisPassword .Release.Name }}
    {{- end }}
{{- else }}

{{- if and ( eq .Values.redis.architecture "replication" ) .Values.redis.sentinel.enabled  }}
{{- printf "redis://%s-redis:6379/1" .Release.Name }}
{{- else }}
{{- printf "redis://%s-redis-master:6379/1" .Release.Name }}
{{- end }}

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
app.kubernetes.io/name: {{ include "splunk-connect-for-snmp.name" . }}
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
Whether enable traps
*/}}
{{- define "splunk-connect-for-snmp.traps.enable" -}}
{{- if or (and (eq .Values.traps.service.type "LoadBalancer") .Values.traps.loadBalancerIP ) (and (eq .Values.traps.service.type "NodePort") .Values.traps.service.nodePort) }}
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