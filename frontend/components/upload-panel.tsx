"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ChangeEvent, FormEvent, useMemo, useState } from "react";

import { createIdentificationJob } from "@/lib/api";
import { formatBytes } from "@/lib/format";

type FileKind = "bed" | "bim" | "fam";

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

export function UploadPanel() {
  const router = useRouter();
  const [files, setFiles] = useState<Partial<Record<FileKind, File>>>({});
  const [validationError, setValidationError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createIdentificationJob,
    onSuccess: (job) => router.push(`/jobs/${job.id}`),
  });

  const isComplete = useMemo(
    () => fileDefinitions.every(({ kind }) => files[kind]),
    [files],
  );

  function selectFile(kind: FileKind, suffix: string) {
    return (event: ChangeEvent<HTMLInputElement>) => {
      const selected = event.target.files?.[0];
      if (!selected) return;
      if (!selected.name.toLowerCase().endsWith(suffix)) {
        setValidationError(`请选择 ${suffix} 文件`);
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
      setValidationError("请同时选择 BED、BIM 和 FAM 三个文件");
      return;
    }
    const formData = new FormData();
    fileDefinitions.forEach(({ kind }) => formData.append(kind, files[kind]!));
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

      <form onSubmit={submit}>
        <div className="file-grid">
          {fileDefinitions.map(({ kind, suffix, title, description }, index) => {
            const file = files[kind];
            return (
              <label className={`file-input ${file ? "file-input--ready" : ""}`} key={kind}>
                <input
                  accept={suffix}
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
          })}
        </div>

        <div className="upload-actions">
          <div className="upload-guidance">
            <strong>提交前检查</strong>
            <span>三个文件应来自同一 PLINK 数据集，且样本 ID 不得与参考库重复。</span>
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
