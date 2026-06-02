{{- define "office.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "office.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "office.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "office.labels" -}}
app.kubernetes.io/name: {{ include "office.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "office.apiImage" -}}
{{ .Values.image.registry }}/{{ .Values.image.apiRepository }}:{{ .Values.image.tag }}
{{- end -}}

{{- define "office.frontendImage" -}}
{{ .Values.image.registry }}/{{ .Values.image.frontendRepository }}:{{ .Values.image.tag }}
{{- end -}}

{{/* Common env: config from ConfigMap + secrets from Secret. */}}
{{- define "office.envFrom" -}}
- configMapRef:
    name: {{ include "office.fullname" . }}-config
- secretRef:
    name: {{ include "office.fullname" . }}-secrets
{{- end -}}
