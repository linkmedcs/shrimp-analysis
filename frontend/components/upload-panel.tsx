"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ChangeEvent, FormEvent, useState } from "react";

import { createIdentificationJob } from "@/lib/api";
import { formatBytes } from "@/lib/format";

type FileKind = "bed" | "bim" | "fam" | "vcf";
type InputMode = "plink" | "vcf";

const fileDefinitions: Array<{
  kind: FileKind;
  suffix: string;
  title: string;
  description: string;
}> = [
  {
    kind: "bed",
    suffix: ".bed",
    title: "基因型二进制文件",
    description: "保存压缩后的基因型矩阵",
  },
  {
    kind: "bim",
    suffix: ".bim",
    title: "位点信息文件",
    description: "包含染色体、位置和等位基因",
  },
  {
    kind: "fam",
    suffix: ".fam",
    title: "样本信息文件",
    description: "包含待鉴定样本 ID",
  },
];

const vcfDefinition = {
  kind: "vcf" as const,
  suffix: ".vcf",
  title: "VCF 变异文件",
  description: "支持 .vcf 和 .vcf.gz，需包含样本基因型",
};

export function UploadPanel() {
  const router = useRouter();
  const [inputMode, setInputMode] = useState<InputMode>("vcf");
  const [files, setFiles] = useState<Partial<Record<FileKind, File>>>({});
  const [validationError, setValidationError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createIdentificationJob,
    onSuccess: (job) => router.push(`/jobs/${job.id}`),
  });

  const isComplete = inputMode === "plink"
    ? fileDefinitions.every(({ kind }) => files[kind])
    : Boolean(files.vcf);

  function selectFile(kind: FileKind, suffix: string) {
    return (event: ChangeEvent<HTMLInputElement>) => {
      const selected = event.target.files?.[0];
      if (!selected) return;
      const acceptsGzipVcf =
        kind === "vcf" && selected.name.toLowerCase().endsWith(".vcf.gz");
      if (!selected.name.toLowerCase().endsWith(suffix) && !acceptsGzipVcf) {
        setValidationError(`请选择 ${suffix}${kind === "vcf" ? " 或 .vcf.gz" : ""} 文件`);
        event.target.value = "";
        return;
      }
      setValidationError(null);
      setFiles((current) => ({ ...current, [kind]: selected }));
    };
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isComplete) {
      setValidationError(
        inputMode === "plink"
          ? "请同时选择 BED、BIM 和 FAM 三个文件"
          : "请选择一个 VCF 或 VCF.GZ 文件",
      );
      return;
    }
    const formData = new FormData();
    if (inputMode === "plink") {
      fileDefinitions.forEach(({ kind }) => formData.append(kind, files[kind]!));
    } else {
      formData.append("vcf", files.vcf!);
    }
    mutation.mutate(formData);
  }

  return (
    <section className="upload-card" id="identify">
      <div className="section-heading">
        <div>
          <span className="eyebrow">NEW IDENTIFICATION</span>
          <h2>提交待鉴定样本</h2>
        </div>
        <span className="secure-note">文件仅用于本次分析任务</span>
      </div>

      <div className="input-mode-toggle" role="tablist" aria-label="输入格式">
        <button
          className={inputMode === "plink" ? "input-mode-toggle--active" : ""}
          onClick={() => { setInputMode("plink"); setValidationError(null); }}
          role="tab"
          aria-selected={inputMode === "plink"}
          type="button"
        >
          PLINK 三文件
        </button>
        <button
          className={inputMode === "vcf" ? "input-mode-toggle--active" : ""}
          onClick={() => { setInputMode("vcf"); setValidationError(null); }}
          role="tab"
          aria-selected={inputMode === "vcf"}
          type="button"
        >
          VCF 单文件
        </button>
      </div>

      <form onSubmit={submit}>
        <div className={`file-grid ${inputMode === "vcf" ? "file-grid--single" : ""}`}>
          {(inputMode === "plink" ? fileDefinitions : [vcfDefinition]).map(
            ({ kind, suffix, title, description }, index) => {
              const file = files[kind];
              return (
                <label
                  className={`file-input ${file ? "file-input--ready" : ""}`}
                  key={kind}
                >
                  <input
                    aria-label={`选择 ${suffix} 文件`}
                    onChange={selectFile(kind, suffix)}
                    type="file"
                  />
                  <span className="file-input__index">0{index + 1}</span>
                  <span className="file-input__suffix">{suffix}</span>
                  <strong>{file?.name ?? title}</strong>
                  <small>
                    {file ? `${formatBytes(file.size)} · 已选择` : description}
                  </small>
                </label>
              );
            },
          )}
        </div>

        <div className="upload-actions">
          <div className="upload-guidance">
            <strong>提交前检查</strong>
            <span>
              {inputMode === "plink"
                ? "三个文件应来自同一 PLINK 数据集，且样本 ID 不得与参考库重复。"
                : "VCF 应包含样本列和 GT 字段，且样本 ID 不得与参考库重复。"}
            </span>
          </div>
          <button
            className="primary-button"
            disabled={!isComplete || mutation.isPending}
            type="submit"
          >
            {mutation.isPending ? "正在上传…" : "开始种质鉴定"}
            <span aria-hidden="true">→</span>
          </button>
        </div>

        {(validationError || mutation.error) && (
          <p className="form-error" role="alert">
            {validationError ?? mutation.error?.message}
          </p>
        )}
      </form>
    </section>
  );
}
