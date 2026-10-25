{{- define "workload.name" -}}
{{- required "metadata.name is required: pass the workload's score.yaml as values" (.Values.metadata | default dict).name -}}
{{- end -}}

{{- define "workload.selector" -}}
app.kubernetes.io/name: {{ include "workload.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "workload.labels" -}}
{{ include "workload.selector" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
