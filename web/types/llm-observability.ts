export interface LLMPromptProvenance {
  prompt_name?: string | null
  prompt_source?: string | null
  prompt_label?: string | null
  prompt_version?: number | null
}

export interface LLMWorkflowCardCounts {
  raw?: number | null
  repaired?: number | null
  committed?: number | null
  already_covered?: number | null
  alumni_built?: number | null
}

export interface LLMWorkflowScore {
  key: string
  value: string | number | boolean | null
  label: string
  rationale?: string | null
}

export interface LLMWorkflowStep {
  step_id: string
  label: string
  status: string
  started_at?: string | null
  ended_at?: string | null
  duration_ms?: number | null
  detail?: string | null
  metadata?: Record<string, unknown>
}

export interface LLMWorkflowSummary {
  workflow_id: string
  workflow_name: string
  status: string
  started_at?: string | null
  ended_at?: string | null
  duration_ms?: number | null
  session_id?: string | null
  model?: string | null
  prompt: LLMPromptProvenance
  drop_point?: string | null
  failure_summary?: string | null
  repair_applied: boolean
  card_counts: LLMWorkflowCardCounts
  alumni_path?: string | null
  is_partial: boolean
}

export interface LLMWorkflowDetail {
  workflow_id: string
  workflow_name: string
  status: string
  session_id?: string | null
  trace_ids: string[]
  started_at?: string | null
  ended_at?: string | null
  duration_ms?: number | null
  prompt: LLMPromptProvenance
  model?: string | null
  summary?: string | null
  likely_cause?: string | null
  recommended_action?: string | null
  drop_point?: string | null
  alumni_path?: string | null
  prompt_provenance_unavailable: boolean
  context_pack_summary: Record<string, unknown>
  raw_output_summary: Record<string, unknown>
  repair_summary: Record<string, unknown>
  parsed_payload_summary: Record<string, unknown>
  validation_summary: Record<string, unknown>
  append_summary: Record<string, unknown>
  card_counts: LLMWorkflowCardCounts
  scores: LLMWorkflowScore[]
  steps: LLMWorkflowStep[]
  limitations: string[]
}
