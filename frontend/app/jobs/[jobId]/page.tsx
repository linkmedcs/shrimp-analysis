"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ResultView } from "@/components/result-view";
import { StatusPill } from "@/components/status-pill";
import {
  fetchJob,
  fetchJobFiles,
  fetchJobResult,
  isTerminalStatus,
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";

const lifecycle = [
  { key: "queued", label: "任务入队" },
  { key: "running", label: "质控与计算" },
  { key: "completed", label: "生成结果" },
];

export default function JobPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;
  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && isTerminalStatus(status) ? false : 1_500;
    },
  });
  const terminal = jobQuery.data
    ? isTerminalStatus(jobQuery.data.status)
    : false;
  const resultQuery = useQuery({
    queryKey: ["job-result", jobId],
    queryFn: () => fetchJobResult(jobId),
    enabled: terminal,
  });
  const filesQuery = useQuery({
    queryKey: ["job-files", jobId],
    queryFn: () => fetchJobFiles(jobId),
    enabled: terminal,
  });

  if (jobQuery.isLoading) {
    return <LoadingState />;
  }

  if (jobQuery.error || !jobQuery.data) {
    return (
      <main className="job-page page-shell">
        <section className="result-alert result-alert--error">
          <span>404</span>
          <div>
            <h1>无法读取任务</h1>
            <p>{jobQuery.error?.message ?? "任务不存在或服务暂时不可用。"}</p>
            <Link href="/">返回首页</Link>
          </div>
        </section>
      </main>
    );
  }

  const job = jobQuery.data;
  const currentIndex = job.status === "queued" ? 0 : job.status === "running" ? 1 : 2;
  const unsuccessful = job.status === "rejected" || job.status === "failed";
  const finalStepLabel =
    job.status === "rejected"
      ? "质控未通过"
      : job.status === "failed"
        ? "任务失败"
        : "生成结果";
  const statusMessage =
    job.status === "queued"
      ? "等待分析 Worker"
      : job.status === "running"
        ? "正在执行位点质控和加权 KNN"
        : job.status === "completed"
          ? "鉴定结果已生成"
          : job.message;

  return (
    <main className="job-page">
      <div className="page-shell">
        <div className="job-heading">
          <div>
            <Link className="back-link" href="/">
              ← 返回新建任务
            </Link>
            <span className="eyebrow">IDENTIFICATION JOB</span>
            <h1>种质鉴定任务</h1>
            <code>{job.id}</code>
          </div>
          <StatusPill status={job.status} />
        </div>

        <section className="progress-card">
          <div className="progress-steps">
            {lifecycle.map((step, index) => (
              <div
                className={`progress-step ${index <= currentIndex ? "progress-step--active" : ""} ${unsuccessful && index === 2 ? "progress-step--error" : ""}`}
                key={step.key}
              >
                <span>
                  {unsuccessful && index === 2
                    ? "!"
                    : index < currentIndex || job.status === "completed"
                      ? "✓"
                      : index + 1}
                </span>
                <strong>{index === 2 ? finalStepLabel : step.label}</strong>
              </div>
            ))}
          </div>
          <div className="job-meta">
            <span>
              参考库 <strong>{job.reference_version}</strong>
            </span>
            <span>
              创建时间 <strong>{formatDateTime(job.created_at)}</strong>
            </span>
            <span>
              当前说明 <strong>{statusMessage}</strong>
            </span>
          </div>
        </section>

        {!terminal && (
          <section className="running-card">
            <div className="running-indicator">
              <i />
              <i />
              <i />
            </div>
            <div>
              <h2>{job.status === "queued" ? "等待可用 Worker" : "正在执行种质鉴定"}</h2>
              <p>
                {job.status === "queued"
                  ? "任务已经安全保存，系统将按队列顺序开始处理。"
                  : "正在进行位点对齐、样本质控、IBS 距离计算和加权 KNN。"}
              </p>
            </div>
          </section>
        )}

        {terminal && resultQuery.isLoading && <LoadingState compact />}
        {resultQuery.data && (
          <ResultView result={resultQuery.data} files={filesQuery.data ?? []} />
        )}
      </div>
    </main>
  );
}

function LoadingState({ compact = false }: { compact?: boolean }) {
  return (
    <main className={compact ? "loading-state loading-state--compact" : "loading-state"}>
      <span />
      <p>正在读取任务数据…</p>
    </main>
  );
}
