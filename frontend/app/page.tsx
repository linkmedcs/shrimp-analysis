import { ReferenceSummary } from "@/components/reference-summary";
import { UploadPanel } from "@/components/upload-panel";

export default function Home() {
  return (
    <main>
      <section className="hero">
        <div className="hero__content">
          <span className="hero__kicker">MOLECULAR IDENTITY · PANEL V1</span>
          <h1>
            让每一份对虾种质
            <br />
            <em>都有清晰的分子身份</em>
          </h1>
          <p>
            上传 PLINK 基因型文件，通过冻结的 503 位点参考库、IBS 遗传距离和
            加权 K 近邻模型完成可追溯的种质鉴定。
          </p>
          <div className="hero__actions">
            <a className="primary-button" href="#identify">
              开始鉴定 <span aria-hidden="true">→</span>
            </a>
            <span>支持最多 100 个查询样本</span>
          </div>
        </div>
        <div className="hero__visual" aria-hidden="true">
          <div className="genome-orbit genome-orbit--outer" />
          <div className="genome-orbit genome-orbit--inner" />
          <div className="genome-core">
            <strong>503</strong>
            <span>SNP MARKERS</span>
          </div>
          <span className="genome-node genome-node--one">A/G</span>
          <span className="genome-node genome-node--two">C/T</span>
          <span className="genome-node genome-node--three">IBS</span>
        </div>
      </section>

      <div className="page-shell">
        <ReferenceSummary />
        <UploadPanel />

        <section className="workflow-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">TRACEABLE WORKFLOW</span>
              <h2>从样本到鉴定结果</h2>
            </div>
          </div>
          <div className="workflow-grid">
            <WorkflowStep index="01" title="输入校验" text="核对样本 ID、文件完整性和样本数量。" />
            <WorkflowStep index="02" title="位点对齐" text="比对染色体、位置、等位基因并处理互补链。" />
            <WorkflowStep index="03" title="质量控制" text="计算位点覆盖率和每个样本的缺失率。" />
            <WorkflowStep index="04" title="加权 KNN" text="基于 PLINK IBS 距离从已知参考样本中完成鉴定。" />
          </div>
        </section>
      </div>
    </main>
  );
}

function WorkflowStep({
  index,
  title,
  text,
}: {
  index: string;
  title: string;
  text: string;
}) {
  return (
    <article className="workflow-step">
      <span>{index}</span>
      <h3>{title}</h3>
      <p>{text}</p>
    </article>
  );
}
