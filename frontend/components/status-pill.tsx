import type { JobStatus } from "@/lib/api";

const statusLabels: Record<JobStatus, string> = {
  queued: "等待处理",
  running: "正在鉴定",
  completed: "鉴定完成",
  rejected: "质控未通过",
  failed: "运行失败",
};

export function StatusPill({ status }: { status: JobStatus }) {
  return (
    <span className={`status-pill status-pill--${status}`}>
      <i aria-hidden="true" />
      {statusLabels[status]}
    </span>
  );
}
