# 鉴定输入文件规范

当前种质鉴定支持两种互斥输入方式：

1. PLINK binary dataset：`.bed + .bim + .fam` 三个文件。
2. VCF：一个 `.vcf` 或 `.vcf.gz` 文件。

两种输入最终都会在 Worker 内转换或整理为 PLINK binary dataset，再执行同一套位点
对齐、缺失率质控、IBS 距离和加权 KNN 流程。输入格式不会改变算法版本。

## 方式一：PLINK 三文件

### `.bed`

- PLINK 1 binary genotype file。
- 必须与同一数据集的 `.bim` 和 `.fam` 配套。
- 文件内容必须是合法 PLINK binary 编码，不能只改扩展名。

### `.bim`

每行至少 6 列，空白字符分隔：

```text
CHR  SNP_ID  CM  BP  A1  A2
```

要求：

- `SNP_ID` 唯一，并且应与 `panel-v1` 的 marker ID 对应。
- `CHR` 和 `BP` 必须与参考位点一致。
- `A1/A2` 应为实际等位基因；当前流程支持 A/C/G/T 及其互补链识别。
- 不在参考库中的额外位点会被忽略。
- 默认至少 90% 的参考位点能够按 ID、染色体、位置和等位基因对齐。

### `.fam`

每行至少 6 列，空白字符分隔：

```text
FID  IID  PAT  MAT  SEX  PHENO
```

要求：

- `IID` 必须存在且在本次输入内唯一。
- `IID` 不得与冻结参考库的 673 个基因型样本重复。
- 默认最多提交 100 个查询样本。
- `FID` 和 `IID` 应与 `.bed` 的样本顺序一致。
- `SEX`、`PHENO` 当前不用于种质预测，可使用 `0` 和 `-9`。

## 方式二：VCF/VCF.GZ

支持标准 VCF 4.x 文本文件和 BGZF 压缩的 `.vcf.gz` 文件。VCF 必须包含：

- `##fileformat=VCFv4.x` 元信息行。
- `#CHROM POS ID REF ALT QUAL FILTER INFO FORMAT sample...` 表头。
- 至少一个样本列。
- 每个样本的 `GT` 基因型字段。
- `ID` 位点名应与参考 BIM 中的 `SNP_ID` 一致。
- `CHROM` 和 `POS` 应与参考位点一致。
- `REF/ALT` 应真实描述等位基因，当前推荐使用 SNP 的 A/C/G/T 碱基。

VCF 输入会先由 PLINK 1.9 转换。转换时：

- 没有单独的 FID 时，PLINK 会使用样本名生成 FID/IID。
- 多等位位点、复杂 Indel 或无法转换的等位基因可能被 PLINK 拒绝或无法与
  `panel-v1` 对齐。
- 只包含少量位点的 VCF 会在位点覆盖率质控阶段被拒绝。
- `.vcf.gz` 必须是 gzip/BGZF 压缩，不能是 ZIP 文件。

VCF 示例：

```text
##fileformat=VCFv4.2
#CHROM POS ID REF ALT QUAL FILTER INFO FORMAT Q_SAMPLE
1 11687793 1:11687793 A G . PASS . GT 0/1
```

实际文件应使用制表符，不应使用上面示例中的空格替代格式化分隔。

## 样本和质量要求

| 检查项 | 默认要求 | 失败结果 |
| --- | ---: | --- |
| 查询样本数 | 1–100 | `too_many_query_samples` 或输入错误 |
| 参考位点覆盖率 | ≥ 90% | `insufficient_marker_overlap` |
| 单样本基因型缺失率 | ≤ 20% | 样本被拒绝；全部失败则 Job `rejected` |
| 有标签参考样本 | 650 | 参考库异常时 Job `failed` |
| 参考数据库 | `panel-v1`，503 位点 | 参考清单校验失败 |
| 样本 ID | 不得与参考基因型 IID 重复 | `sample_id_conflict` |

位点覆盖率是相对于冻结 `panel-v1` 的 503 个 marker 计算，不是相对于输入文件中
额外位点的比例。

## 不支持的输入

- 只提交 `.bed` 或只提交 `.bim/.fam`。
- 将 VCF 改名为 `.bed`，或将 PLINK 文件改名为 `.vcf`。
- BGEN、GDS、HapMap、Excel、CSV 等格式未在当前 API 中直接支持。
- 没有 `GT` 字段的 VCF。
- 样本列为空、IID 重复或位点 ID 重复的输入。

## API 上传字段

`POST /api/jobs` 只接受以下两种 multipart 形式之一：

```text
PLINK: bed + bim + fam
VCF:    vcf
```

不能同时提交 VCF 和 PLINK 字段，也不能只提交 PLINK 三文件中的一部分。

## 可复现示例

仓库中的 [mock](/Users/ghx/biology/shrimp-analysis/mock) 目录包含完整 PLINK、
等价 VCF 和低覆盖拒绝用例。使用方式见 [mock/README.md](/Users/ghx/biology/shrimp-analysis/mock/README.md)。
