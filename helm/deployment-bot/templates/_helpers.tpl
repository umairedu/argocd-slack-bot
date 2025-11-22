{{/*
Expand the name of the chart.
*/}}
{{- define "deployment-bot.name" -}}
{{- printf "%s-%s" .Values.nameOverride .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "deployment-bot.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" $name .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "deployment-bot.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "deployment-bot.labels" -}}
helm.sh/chart: {{ include "deployment-bot.chart" . }}
{{ include "deployment-bot.selectorLabels" . }}
{{- if .Values.tag_version }}
app.kubernetes.io/version: {{ .Values.tag_version | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "deployment-bot.selectorLabels" -}}
app.kubernetes.io/name: {{ include "deployment-bot.name" . }}
app.kubernetes.io/app: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "deployment-bot.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "deployment-bot.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}


{{- define "helpers.list-env-variables"}}
{{- $SecretName := include "deployment-bot.fullname" . -}}
{{- range $key, $val := .Values.deployment_bot.secrets }}
    - name: {{ $key }}
      valueFrom:
        secretKeyRef:
          name: {{ $SecretName }}-secrets
          key: {{ $key }}
{{- end}}
{{- range $key, $val := .Values.deployment_bot.plain }}
    - name: {{ $key }}
      value: {{ $val | quote }}
{{- end}}
{{- end }}
