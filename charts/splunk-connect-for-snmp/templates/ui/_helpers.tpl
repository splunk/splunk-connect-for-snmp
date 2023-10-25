{{/*
Create a job config template which will be included in configMap for UI backend.
*/}}
{{- define "splunk-connect-for-snmp.job-config" -}}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "splunk-connect-for-snmp.inventory.fullname" . }}
  labels:
    {{- include "splunk-connect-for-snmp.inventory.labels" . | nindent 4 }}
spec:
  ttlSecondsAfterFinished: 300
  template:
    metadata:
      {{- with .Values.inventory.podAnnotations }}
      annotations:
        {{- toYaml . | nindent 8 }}
      {{- end }}

      labels:
        {{- include "splunk-connect-for-snmp.inventory.selectorLabels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: {{ .Chart.Name }}-inventory
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          args:
              ["inventory"]
          env:
          - name: CONFIG_PATH
            value: /app/config/config.yaml
          - name: REDIS_URL
            value: {{ include "splunk-connect-for-snmp.redis_url" . }}
          - name: INVENTORY_PATH
            value: /app/inventory/inventory.csv
          - name: CELERY_BROKER_URL
            value: {{ include "splunk-connect-for-snmp.celery_url" . }}
          - name: MONGO_URI
            value: {{ include "splunk-connect-for-snmp.mongo_uri" . }}
          - name: MIB_SOURCES
            value: "http://{{ printf "%s-%s" .Release.Name "mibserver" }}/asn1/@mib@"
          - name: MIB_INDEX
            value: "http://{{ printf "%s-%s" .Release.Name "mibserver" }}/index.csv"
          - name: MIB_STANDARD
            value: "http://{{ printf "%s-%s" .Release.Name "mibserver" }}/standard.txt"
          - name: LOG_LEVEL
            value: {{ .Values.scheduler.logLevel | default "INFO" }}
          - name: CONFIG_FROM_MONGO
            value: {{ quote .Values.UI.enable | default "false" }}
          volumeMounts:
            - name: config
              mountPath: "/app/config"
              readOnly: true
            - name: inventory
              mountPath: "/app/inventory"
              readOnly: true
            - name: pysnmp-cache-volume
              mountPath: "/.pysnmp/"
              readOnly: false
            - name: tmp
              mountPath: "/tmp/"
              readOnly: false

      volumes:
        # You set volumes at the Pod level, then mount them into containers inside that Pod
        - name: config
          configMap:
            # Provide the name of the ConfigMap you want to mount.
            name: {{ include "splunk-connect-for-snmp.name" . }}-config
            # An array of keys from the ConfigMap to create as files
            items:
              - key: "config.yaml"
                path: "config.yaml"
        - name: inventory
          configMap:
            # Provide the name of the ConfigMap you want to mount.
            name: {{ include "splunk-connect-for-snmp.name" . }}-inventory
            # An array of keys from the ConfigMap to create as files
            items:
              - key: "inventory.csv"
                path: "inventory.csv"
        - name: pysnmp-cache-volume
          emptyDir: {}
        - name: tmp
          emptyDir: {}
      restartPolicy: OnFailure
{{- end }}

{{/*
Return full image for thr UI front end.
*/}}
{{- define "splunk-connect-for-snmp.uiFrontImage" -}}
{{ .Values.UI.frontEnd.repository }}:{{ .Values.UI.frontEnd.tag | default "latest" }}
{{- end }}

{{/*
Return full image for thr UI back end.
*/}}
{{- define "splunk-connect-for-snmp.uiBackImage" -}}
{{ .Values.UI.backEnd.repository }}:{{ .Values.UI.backEnd.tag | default "latest" }}
{{- end }}

{{- define "splunk-connect-for-snmp-ui.celery_url" -}}
{{- printf "redis://%s-redis-headless:6379/2" .Release.Name }}
{{- end }}

{{- define "splunk-connect-for-snmp-ui.redis_url" -}}
{{- printf "redis://%s-redis-headless:6379/3" .Release.Name }}
{{- end }}

{{- define "splunk-connect-for-snmp-ui.hostMountPath" -}}
/var/values_dir
{{- end }}