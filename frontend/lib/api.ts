export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "rejected"
  | "failed";

export interface JobSummary {
  submitted_samples?: number;
  accepted_samples?: number;
  rejected_samples?: number;
  assigned_samples?: number;
  final_marker_count?: number;
  final_marker_overlap_ratio?: number;
}

export interface JobRecord {
  id: string;
  status: JobStatus;
  message: string;
  reason_code: string | null;
  reference_version: string;
  application_version: string | null;
  algorithm_version: string | null;
  summary: JobSummary | null;
  input_files: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Assignment {
  ID: string;
  predicted_label: string | null;
  predicted_name?: string | null;
  status: string;
  known_neighbor_count: number;
  score_ratio: number | null;
  nearest_distance: number | null;
  assigned_mean_distance: number | null;
  matched_marker_count: number;
  marker_overlap_ratio: number;
  sample_missing_rate: number;
}

export interface RejectedSample {
  sample_id: string;
  reason: string;
  missing_rate: number;
  maximum_missing_rate: number;
}

export interface JobResult {
  job_id: string;
  status: JobStatus;
  reference_version: string;
  application_version: string;
  algorithm_version: string;
  reason_code?: string;
  message?: string;
  summary?: JobSummary;
  assignments?: Assignment[];
  rejected_samples?: RejectedSample[];
}

export interface OutputFile {
  key: string;
  name: string;
  size_bytes: number;
  download_url: string;
}

export interface ReferencePanel {
  reference_version: string;
  lifecycle_status: string;
  species: {
    common_name: string;
    scientific_name: string;
  };
  panel: {
    declared_name: string;
    marker_count: number;
    marker_policy: string;
  };
  samples: {
    genotype_sample_count: number;
    labelled_reference_count: number;
    label_class_count: number;
  };
  algorithm_defaults: {
    name: string;
    version: string;
    k: number;
  };
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message ?? `请求失败（HTTP ${response.status}）`;
    throw new Error(message);
  }
  return payload as T;
}

export function createIdentificationJob(formData: FormData) {
  return requestJson<JobRecord>("/api/jobs", {
    method: "POST",
    body: formData,
  });
}

export function fetchJob(jobId: string) {
  return requestJson<JobRecord>(`/api/jobs/${jobId}`);
}

export function fetchJobResult(jobId: string) {
  return requestJson<JobResult>(`/api/jobs/${jobId}/result`);
}

export function fetchJobFiles(jobId: string) {
  return requestJson<OutputFile[]>(`/api/jobs/${jobId}/files`);
}

export function fetchReferencePanels() {
  return requestJson<ReferencePanel[]>("/api/reference-panels");
}

export function isTerminalStatus(status: JobStatus) {
  return ["completed", "rejected", "failed"].includes(status);
}
