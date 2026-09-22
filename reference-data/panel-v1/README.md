# panel-v1

该目录保存已经冻结的凡纳滨对虾种质鉴定参考数据库。

- 冻结日期：2026-09-22。
- 位点策略：使用当前 BIM 文件中的全部 503 个位点。
- 基因型样本数：673。
- 已标注参考样本数：650。
- `genotype/reference.bed/.bim/.fam` 为冻结的 PLINK 参考文件。
- `metadata/labels.raw.tsv` 为只读的原始标签文件，保留原格式问题用于追溯。
- `metadata/labels.tsv` 为运行时使用的规范化标签文件，每行严格为 `ID`、`POP` 两列。
- 空 `POP` 不会被猜测或补写，算法仍将这些记录视为未知样本。
- 规范化由 `scripts/normalize_reference_metadata.py` 完成。
- `manifest.json` 记录版本、统计信息、参数和 SHA-256。
- 冻结文件为只读；任何数据或标签调整都应创建新版本，不应覆盖 `panel-v1`。

使用冻结参考库运行 CLI：

```bash
weighted-knn-genotype \
  --plink-prefix reference-data/panel-v1/genotype/reference \
  --metadata reference-data/panel-v1/metadata/labels.tsv \
  --reference-manifest reference-data/panel-v1/manifest.json \
  --autosome-count 45 \
  --loo
```
