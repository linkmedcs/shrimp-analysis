# Backend API

阶段 4 将阶段 3 Job Runner 包装为异步 HTTP 服务。API、数据库、队列和分析进程
保持独立，Web 请求不会直接运行 PLINK。

## 服务组成

```text
FastAPI API
    ├── PostgreSQL：任务状态与结果元数据
    ├── Redis：RQ 任务队列
    └── 共享卷：上传文件与任务输出

RQ Worker
    └── run_identification_job()
            ├── PLINK 1.9
            ├── panel-v1
            └── weighted KNN
```

`compose.yaml` 包含：

- `postgres`：任务持久化。
- `redis`：队列和 RQ 状态。
- `migrate`：启动时运行 Alembic migration。
- `api`：FastAPI，不包含 PLINK 和完整参考基因型。
- `worker`：包含 PLINK、冻结参考库和 Job Runner。

## 启动

```bash
./scripts/start-local.sh
docker compose ps
curl http://localhost:8000/api/health
```

服务器使用 `./scripts/start-server.sh`；两个脚本共用同一个 Compose 配置和构建流程。

正常健康检查：

```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok"
}
```

停止服务但保留 PostgreSQL、Redis 和任务卷：

```bash
./scripts/stop-stack.sh
```

只有明确需要删除全部本地数据时才运行 `docker compose down -v`。

## 创建任务

```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "bed=@tests/fixtures/holdout_query.bed" \
  -F "bim=@tests/fixtures/holdout_query.bim" \
  -F "fam=@tests/fixtures/holdout_query.fam"
```

也可以直接上传一个 VCF 或 VCF.GZ 文件：

```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "vcf=@mock/vcf/valid/query.vcf.gz"
```

两种方式必须二选一；完整的字段、格式和质量要求见
[docs/input-requirements.md](input-requirements.md)。

成功时返回 HTTP `202`，初始状态为 `queued`。Worker 开始处理后状态变为
`running`，最终进入 `completed`、`rejected` 或 `failed`。

## 接口

```text
POST /api/jobs
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/result
GET  /api/jobs/{job_id}/files
GET  /api/jobs/{job_id}/files/{file_key}
GET  /api/reference-panels
GET  /api/health
```

`GET /api/jobs/{job_id}/result` 在任务尚未产生结果时返回 HTTP `409`。

可下载文件键：

```text
result
quality_control
assignments
analysis_log
```

## 状态与失败语义

- `queued`：数据库记录已创建，等待 Worker。
- `running`：Worker 已开始执行 Job Runner。
- `completed`：至少一个查询样本完成鉴定。
- `rejected`：输入或质量控制未通过，不应自动重试。
- `failed`：队列、环境或程序异常，需要检查日志后决定是否重新提交。

PostgreSQL 是任务状态的最终依据；Redis 仅负责任务排队。Worker 不重新实现任何
PLINK 或 KNN 逻辑。

## 数据卷

```text
uploads-data  API 保存原始上传文件，Worker 从此处读取
jobs-data     Job Runner 的 input/work/output/logs 目录
postgres-data
redis-data
```

任务结果生成后，`jobs-data` 中仍保存 Job Runner 的完整审计目录。当前版本不自动
删除上传和中间文件；后续应增加明确的归档及保留策略。
