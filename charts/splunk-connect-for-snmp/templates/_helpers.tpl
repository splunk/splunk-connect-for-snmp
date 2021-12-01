{{- define "splunk-connect-for-snmp.mongo_uri" -}}
{{- if eq .Values.mongodb.architecture "replicaset" }}
{{- printf "mongodb+srv://%s-mongodb-headless.%s.svc.%s/?tls=false&ssl=false&replicaSet=rs0" .Release.Namespace .Release.Namespace .Values.mongodb.clusterDomain}}
{{- else }}
{{- printf "mongodb://%s-mongodb:27017" .Release.Namespace }}
{{- end }}  
{{- end }}  

{{- define "splunk-connect-for-snmp.celery_url" -}}
{{- printf "amqp://%s:%s@%s-rabbitmq:5672/" .Values.rabbitmq.auth.username .Values.rabbitmq.auth.password .Release.Namespace }}
{{- end }}  


{{- define "splunk-connect-for-snmp.name" -}}
{{- default (printf "%s" .Chart.Name ) .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}