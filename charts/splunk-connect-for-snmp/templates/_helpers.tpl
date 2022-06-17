{{- define "splunk-connect-for-snmp.mongo_uri" -}}
{{- if eq .Values.mongodb.architecture "replicaset" }}
{{- printf "mongodb+srv://%s-mongodb-headless.%s.svc.%s/?tls=false&ssl=false&replicaSet=rs0" .Release.Name .Release.Namespace .Values.mongodb.clusterDomain}}
{{- else }}
{{- printf "mongodb://%s-mongodb:27017" .Release.Name }}
{{- end }}  
{{- end }}  

{{- define "splunk-connect-for-snmp.celery_url" -}}
{{- printf "redis://%s-redis-headless:6379/0" .Release.Name }}
{{- end }}

{{- define "splunk-connect-for-snmp.redis_url" -}}
{{- printf "redis://%s-redis-headless:6379/1" .Release.Name }}
{{- end }}

{{- define "splunk-connect-for-snmp.name" -}}
{{- default (printf "%s" .Chart.Name ) .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "environmental-variables" -}}
env:
  - name: CONFIG_PATH
    value: /app/config/config.yaml
  - name: REDIS_URL
    value: {{ include "splunk-connect-for-snmp.redis_url" . }}
  - name: SC4SNMP_VERSION
    value: {{ .Chart.Version | default "0.0.0" }}
  - name: WORKER_CONCURRENCY
    value: {{ .Values.worker.poller.concurrency | default "2" | quote }}
  - name: PREFETCH_COUNT
    value: {{ .Values.worker.poller.prefetch | default "1" | quote }}
  - name: CELERY_BROKER_URL
    value: {{ include "splunk-connect-for-snmp.celery_url" . }}
  - name: MONGO_URI
    value: {{ include "splunk-connect-for-snmp.mongo_uri" . }}
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
    value: {{ .Values.worker.profilesReloadDelay | default "300" | quote }}
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