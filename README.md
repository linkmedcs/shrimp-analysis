# Shrimp Analysis

凡纳滨对虾分子指纹与种质鉴定算法原型。

当前开发进度见 [docs/development-status.md](docs/development-status.md)。

当前冻结参考数据库为 `reference-data/panel-v1`，使用全部 503 个现有位点。
运行时标签使用严格两列的 `metadata/labels.tsv`；原始标签保存在
`metadata/labels.raw.tsv` 供追溯。

## 阶段一结构

```text
weighted_knn_genotype/
  config.py          KNN参数
  ibs.py             IBS矩阵、元数据与PLINK 1.9接口
  weighted_knn.py    单样本加权KNN核心算法
  evaluation.py      未知样本预测与LOO评估
  reference.py       参考数据库版本与SHA-256校验
  cli.py             命令行入口
  __main__.py        Python模块入口
```

安装为本地命令：

```bash
python -m pip install -e .
weighted-knn-genotype --help
```

未安装命令行入口时，也可以直接运行：

```bash
python -m weighted_knn_genotype --help
```

使用现有 IBS 矩阵：

```bash
weighted-knn-genotype \
  --ibs-matrix path/to/input.mibs \
  --ids path/to/input.mibs.id \
  --metadata reference-data/panel-v1/metadata/labels.tsv \
  --reference-manifest reference-data/panel-v1/manifest.json \
  --id-column ID \
  --label-column POP \
  --k 5 \
  --min-known-neighbors 3 \
  --loo \
  --output-dir test-output/knn-results-package
```

直接从 PLINK 文件生成 IBS：

```bash
weighted-knn-genotype \
  --plink-prefix reference-data/panel-v1/genotype/reference \
  --metadata reference-data/panel-v1/metadata/labels.tsv \
  --autosome-count 45 \
  --reference-manifest reference-data/panel-v1/manifest.json \
  --loo
```

运行测试：

```bash
python -m unittest discover -s tests -v
```

## Docker 运行

构建固定的 PLINK 1.9 与 Python 运行环境：

```bash
docker build -t shrimp-genotype:0.3.0 .
```

镜像固定使用 Debian 13.5、Python 3.13.5、NumPy 2.2.4、Pandas 2.2.3 和
PLINK 1.9.0-b.7.7，并以非 root 用户运行。参考数据库被写入镜像并设为只读。

使用镜像内置的只读 `panel-v1` 完整运行鉴定和 LOO：

```bash
mkdir -p docker-output
docker run --rm \
  -v "$PWD/docker-output:/work/output" \
  shrimp-genotype:0.3.0 \
  --plink-prefix /app/reference-data/panel-v1/genotype/reference \
  --metadata /app/reference-data/panel-v1/metadata/labels.tsv \
  --reference-manifest /app/reference-data/panel-v1/manifest.json \
  --autosome-count 45 \
  --loo \
  --output-dir /work/output
```

比较 Docker 与本机结果：

```bash
python scripts/compare_result_csv.py \
  test-output/panel-v1-freeze-validation \
  docker-output
```

Dockerfile 的默认目标仍是可独立运行的分析镜像。`api` 和 `worker` 构建目标由
阶段 4 的 `compose.yaml` 使用。

构建可发布到常见 Linux 服务器的多架构镜像：

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t your-registry/shrimp-genotype:0.3.0 \
  --push .
```

当前版本已分别在 `linux/arm64` 和 `linux/amd64` 下完成完整 PLINK + KNN
回归，两种容器结果均与本机结果逐行一致。

## 新样本 Job Runner

阶段 3 提供完整的新样本鉴定命令：

```bash
weighted-knn-genotype run-job \
  --query-prefix path/to/query \
  --job-dir jobs/JOB-EXAMPLE \
  --reference-manifest reference-data/panel-v1/manifest.json
```

Job Runner 会自动完成输入复制和哈希、503 位点对齐、strand flip、样本缺失率
质控、650 个有标签参考样本提取、PLINK 合并、IBS 距离和加权 KNN，并输出
`result.json`、`quality_control.json`、`knn_assignments.csv` 和完整日志。

详细输入、目录和输出契约见 [docs/job-runner.md](docs/job-runner.md)。
支持的 PLINK/VCF 输入字段和质量要求见
[docs/input-requirements.md](docs/input-requirements.md)；可复现测试数据见
[mock/README.md](mock/README.md)。

## 异步鉴定 API

阶段 4 使用 FastAPI、PostgreSQL、Redis 和 RQ Worker，把 Job Runner 包装为
可以由网站调用的异步任务服务。API 不执行 PLINK；Worker 从队列取任务后直接调用
`run_identification_job()`。

启动完整开发环境：

```bash
./scripts/start-local.sh
curl http://localhost:8000/api/health
```

服务器首次构建或重新启动完整服务：

```bash
./scripts/start-server.sh
```

两个入口共用 `scripts/start-stack.sh` 和同一个 `compose.yaml`。本地默认将 Web
映射到 3000 端口，服务器默认映射到 80 端口；可通过 `SHRIMP_WEB_PORT` 覆盖。

本地和服务器使用同一个脚本停止完整服务，并保留数据库与任务数据卷：

```bash
./scripts/stop-stack.sh
```

上传一个 PLINK binary dataset：

```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "bed=@path/to/query.bed" \
  -F "bim=@path/to/query.bim" \
  -F "fam=@path/to/query.fam"
```

使用返回的 `job_id` 查询状态和结果：

```bash
curl http://localhost:8000/api/jobs/JOB-ID
curl http://localhost:8000/api/jobs/JOB-ID/result
curl http://localhost:8000/api/jobs/JOB-ID/files
```

交互式 API 文档位于 `http://localhost:8000/docs`。详细说明见
[docs/backend-api.md](docs/backend-api.md)。

## Web 前端

阶段 5 提供 Next.js 种质鉴定界面。启动完整服务后访问：

```text
http://localhost:3000
```

前端支持：

- 展示冻结参考库、标记数、参考样本数和种质类别。
- 选择并上传 `.bed/.bim/.fam` 文件。
- 自动跳转到任务页并轮询 `queued/running/completed` 状态。
- 展示每个样本的预测种质、邻居数、距离、得分比、缺失率和位点覆盖率。
- 展示质控拒绝或运行失败信息。
- 下载结果 JSON、质控 JSON、预测 CSV 和分析日志。

前端通过 Next.js 同源代理访问 FastAPI，因此浏览器不需要额外配置 CORS。详细说明见
[docs/frontend.md](docs/frontend.md)。
