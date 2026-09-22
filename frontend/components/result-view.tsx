import type { JobResult, OutputFile } from "@/lib/api";
import { formatBytes, formatNumber, formatPercent } from "@/lib/format";

export function ResultView({
  result,
  files,
}: {
  result: JobResult;
  files: OutputFile[];
}) {
  if (result.status === "rejected" || result.status === "failed") {
    return (
      <>
        <section className="result-alert result-alert--error">
          <span>{result.status === "rejected" ? "QC" : "ERR"}</span>
          <div>
            <h2>{result.status === "rejected" ? "样本未通过质控" : "任务运行失败"}</h2>
            <p>{result.message ?? "请下载分析日志并检查任务输入。"}</p>
            {result.reason_code && <code>{result.reason_code}</code>}
          </div>
        </section>
        <Downloads files={files} />
      </>
    );
  }

  const assignments = result.assignments ?? [];
  const summary = result.summary;

  return (
    <>
      <section className="metrics-grid">
        <Metric label="提交样本" value={summary?.submitted_samples ?? "—"} />
        <Metric label="完成鉴定" value={summary?.assigned_samples ?? "—"} accent />
        <Metric label="匹配位点" value={summary?.final_marker_count ?? "—"} />
        <Metric
          label="位点覆盖率"
          value={formatPercent(summary?.final_marker_overlap_ratio)}
        />
      </section>

      <section className="data-card">
        <div className="section-heading section-heading--compact">
          <div>
            <span className="eyebrow">ASSIGNMENTS</span>
            <h2>鉴定结果</h2>
          </div>
          <span className="result-count">{assignments.length} 个样本</span>
        </div>
        <div className="table-scroll">
          <table className="result-table">
            <thead>
              <tr>
                <th>样本 ID</th>
                <th>预测种质</th>
                <th>已知邻居</th>
                <th>最近距离</th>
                <th>得分比</th>
                <th>缺失率</th>
                <th>位点覆盖率</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((assignment) => (
                <tr key={assignment.ID}>
                  <td className="sample-id">{assignment.ID}</td>
                  <td>
                    <strong className="prediction-chip">
                      {assignment.predicted_label ?? "未分配"}
                    </strong>
                  </td>
                  <td>{assignment.known_neighbor_count}</td>
                  <td>{formatNumber(assignment.nearest_distance, 5)}</td>
                  <td>{formatNumber(assignment.score_ratio, 2)}</td>
                  <td>{formatPercent(assignment.sample_missing_rate, 2)}</td>
                  <td>{formatPercent(assignment.marker_overlap_ratio)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {(result.rejected_samples?.length ?? 0) > 0 && (
        <section className="rejected-card">
          <div>
            <span className="eyebrow">SAMPLE QC</span>
            <h2>未通过质控的样本</h2>
          </div>
          <div>
            {result.rejected_samples!.map((sample) => (
              <p key={sample.sample_id}>
                <strong>{sample.sample_id}</strong>
                <span>{formatPercent(sample.missing_rate, 2)} 缺失率</span>
              </p>
            ))}
          </div>
        </section>
      )}

      <Downloads files={files} />
    </>
  );
}

function Downloads({ files }: { files: OutputFile[] }) {
  if (files.length === 0) return null;
  return (
    <section className="downloads-card">
      <div>
        <span className="eyebrow">AUDIT FILES</span>
        <h2>结果与审计文件</h2>
        <p>保留结构化结果、质控明细、完整 CSV 和 PLINK 运行日志。</p>
      </div>
      <div className="download-list">
        {files.map((file) => (
          <a download key={file.key} href={file.download_url}>
            <span>
              <strong>{file.name}</strong>
              <small>{formatBytes(file.size_bytes)}</small>
            </span>
            <b aria-hidden="true">↓</b>
          </a>
        ))}
      </div>
    </section>
  );
}

function Metric({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <div className={`metric ${accent ? "metric--accent" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
