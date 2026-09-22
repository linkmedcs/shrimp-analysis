# Identification Job Runner

阶段 3 Job Runner 将新的 PLINK 查询样本与冻结的 `panel-v1` 对齐、质控、
合并，并输出网站后端可以直接读取的 JSON 和 CSV。

## 输入约定

第一版只接受一个 PLINK binary dataset：

```text
query.bed
query.bim
query.fam
```

要求：

- IID 在查询文件中唯一。
- IID 不得与 `panel-v1` 的任何基因型样本重复。
- 默认最多 100 个查询样本。
- 默认至少 90% 的参考位点必须能够按 ID、染色体、位置和等位基因对齐。
- 默认单样本基因型缺失率不得超过 20%。

查询中与参考库互补链一致的非回文 SNP 会自动通过 PLINK `--flip` 调整。
位置不一致或等位基因无法对齐的位点不会进入合并数据集。

## 本地运行

```bash
weighted-knn-genotype run-job \
  --query-prefix path/to/query \
  --job-dir jobs/JOB-EXAMPLE \
  --reference-manifest reference-data/panel-v1/manifest.json
```

如果输入目录中的文件固定命名为 `query.bed/.bim/.fam`：

```bash
weighted-knn-genotype run-job \
  --input-dir path/to/input \
  --jobs-root jobs
```

## Docker 运行

```bash
mkdir -p docker-input docker-output
cp path/to/query.{bed,bim,fam} docker-input/

docker run --rm \
  -v "$PWD/docker-input:/work/input:ro" \
  -v "$PWD/docker-output:/work/output" \
  shrimp-genotype:0.3.0 \
  run-job \
  --input-dir /work/input \
  --job-dir /work/output \
  --reference-manifest /app/reference-data/panel-v1/manifest.json
```

`docker-output` 必须为空，防止覆盖之前的任务证据和结果。

## 任务目录

```text
JOB-ID/
├── status.json
├── input/
│   ├── query.bed
│   ├── query.bim
│   └── query.fam
├── work/
├── output/
│   ├── result.json
│   ├── quality_control.json
│   └── knn_assignments.csv
└── logs/
    └── analysis.log
```

`input/` 保存输入副本和 SHA-256，`work/` 保存 PLINK 中间文件，`logs/`
保存完整命令与输出。Worker 可以在任务归档前删除 `work/`，但不应删除输入、日志和结果。

## 状态

```text
validating  输入及参考库校验中
running     PLINK 或 KNN 运行中
completed   至少一个样本完成鉴定
rejected    输入或质控未通过
failed      环境或程序异常
```

## 输出

`result.json` 分别记录 Job Runner 的 `application_version` 和 KNN 的
`algorithm_version`，同时包含任务状态、参数、文件哈希、样本汇总、拒绝原因和鉴定结果。
非有限浮点值会转换成 JSON `null`，保证结果是严格 JSON。

`quality_control.json` 包含：

- 位点交集和匹配比例。
- strand flip 数量。
- 位置及等位基因不匹配数量。
- 每个查询样本的缺失率。
- 合并阶段额外排除的位点。

`knn_assignments.csv` 保留完整 KNN 分数、距离、版本和质控字段。

比较本机和容器任务结果：

```bash
python scripts/compare_job_outputs.py jobs/HOST jobs/DOCKER
```

## 退出码

```text
0  completed
2  文件、参数、PLINK 或程序错误
3  rejected
```
