# Mock 输入数据

这些文件用于本地测试 API、Docker Worker 和命令行 Job Runner，不代表新的参考
数据库或新的实验数据。

## 目录

```text
mock/
├── plink/valid/              # 3 个完整查询样本，预期鉴定为 GT/KONA/ZD
├── plink/low-marker-overlap/ # 仅保留 10 个位点，预期被拒绝
├── vcf/valid/                # 503 位点；同时提供 query.vcf/query.vcf.gz
├── vcf/partial-marker-overlap/ # 477/503 位点；同时提供两种 VCF 格式
└── vcf/low-marker-overlap/   # 10 位点；同时提供两种 VCF 格式，预期被拒绝
```

每个 VCF 案例同时提供未压缩的 `query.vcf` 和 BGZF 压缩的 `query.vcf.gz`，两者内容一致，
用于分别测试两种上传格式。VCF 是由同一组 PLINK mock 通过 PLINK 1.9 导出，样本 ID 和位点 ID 保持一致。
`partial-marker-overlap` 在有效数据基础上固定移除了 26 个 marker，覆盖率为
`477 / 503 = 94.83%`，高于默认的 90% 阈值；它用于验证“不是 100% 覆盖但仍可鉴定”的情况。

## 命令行测试

PLINK：

```bash
weighted-knn-genotype run-job \
  --query-prefix mock/plink/valid/query \
  --job-dir jobs/mock-plink \
  --reference-manifest reference-data/panel-v1/manifest.json
```

VCF：

```bash
weighted-knn-genotype run-job \
  --query-vcf mock/vcf/valid/query.vcf.gz \
  --job-dir jobs/mock-vcf \
  --reference-manifest reference-data/panel-v1/manifest.json
```

未压缩 VCF 也可以直接运行：

```bash
weighted-knn-genotype run-job \
  --query-vcf mock/vcf/valid/query.vcf \
  --job-dir jobs/mock-vcf-plain \
  --reference-manifest reference-data/panel-v1/manifest.json
```

部分位点覆盖但应通过质控：

```bash
weighted-knn-genotype run-job \
  --query-vcf mock/vcf/partial-marker-overlap/query.vcf.gz \
  --job-dir jobs/mock-vcf-partial-overlap \
  --reference-manifest reference-data/panel-v1/manifest.json
```

低覆盖输入应返回 `insufficient_marker_overlap`：

```bash
weighted-knn-genotype run-job \
  --query-vcf mock/vcf/low-marker-overlap/query.vcf.gz \
  --job-dir jobs/mock-vcf-low-overlap \
  --reference-manifest reference-data/panel-v1/manifest.json
```

## API 测试

PLINK：

```bash
curl -X POST http://localhost:3000/api/jobs \
  -F "bed=@mock/plink/valid/query.bed" \
  -F "bim=@mock/plink/valid/query.bim" \
  -F "fam=@mock/plink/valid/query.fam"
```

VCF：

```bash
curl -X POST http://localhost:3000/api/jobs \
  -F "vcf=@mock/vcf/valid/query.vcf.gz"
```
