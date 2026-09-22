"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchReferencePanels } from "@/lib/api";

export function ReferenceSummary() {
  const query = useQuery({
    queryKey: ["reference-panels"],
    queryFn: fetchReferencePanels,
  });
  const panel = query.data?.[0];

  return (
    <section className="reference-strip" aria-label="参考数据库概览">
      <div>
        <span>冻结参考库</span>
        <strong>{panel?.reference_version ?? "加载中"}</strong>
      </div>
      <div>
        <span>分子标记</span>
        <strong>{panel ? panel.panel.marker_count.toLocaleString() : "—"}</strong>
      </div>
      <div>
        <span>有标签样本</span>
        <strong>
          {panel ? panel.samples.labelled_reference_count.toLocaleString() : "—"}
        </strong>
      </div>
      <div>
        <span>种质类别</span>
        <strong>{panel?.samples.label_class_count ?? "—"}</strong>
      </div>
      <div>
        <span>鉴定算法</span>
        <strong>
          {panel
            ? `${panel.algorithm_defaults.name} · K=${panel.algorithm_defaults.k}`
            : "—"}
        </strong>
      </div>
    </section>
  );
}
