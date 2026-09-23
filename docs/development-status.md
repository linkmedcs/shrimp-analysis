# Development Status

截至 2026-09-22，项目完成以下阶段：

## 阶段 1：算法标准化

- 加权 KNN Python 包。
- PLINK 1.9 IBS 距离。
- 未知样本预测和 LOO 分离。
- 核心算法版本 `weighted-knn-0.1.0`。

## 阶段 2：参考库和 Docker

- 冻结 `panel-v1`，使用全部 503 个位点。
- 标签规范化、原始文件保留、SHA-256 校验。
- ARM64 和 AMD64 Docker 镜像。
- 本机和容器历史回归结果一致。

## 阶段 3：新样本 Job Runner

- 阶段 3 交付版本 `0.2.0`；当前应用版本已升级为 `0.3.0`。
- 接受查询样本 PLINK `.bed/.bim/.fam`。
- 样本 ID、数量、位点、等位基因和缺失率质控。
- 自动 strand flip、参考样本提取、PLINK 合并、IBS 和 KNN。
- 标准任务目录、状态、日志、JSON 和 CSV。
- 预期拒绝与意外失败分离。
- 10 项单元/集成测试通过。
- GT、KONA、ZD 三个留出查询样本正确识别。
- 本机、Linux ARM64、Linux AMD64 任务输出一致。

最终验收结果保存在：

```text
test-output/stage3-final-host
test-output/stage3-final-arm64
test-output/stage3-final-amd64
```

## 阶段 4：异步任务后端

- FastAPI 上传、任务状态、结果、文件和参考库接口。
- PostgreSQL 持久化任务生命周期和结果元数据。
- Redis + RQ 异步队列。
- 独立 Python Worker 直接调用阶段 3 Job Runner。
- Alembic 数据库迁移。
- API、Worker、PostgreSQL、Redis 的 Docker Compose 编排。
- API 与 Worker 共享任务及上传卷，参考数据库只存在于 Worker 镜像。
- 应用版本 `0.3.0`，算法版本保持 `weighted-knn-0.1.0`。
- 12 项算法、API、Worker 和真实 PLINK 集成测试通过。
- 已通过 HTTP 上传 GT、KONA、ZD 三个留出样本，任务从 `queued` 转为
  `completed`，503 个位点全部匹配，结果及四类输出文件可通过 API 查询。

## 阶段 5：种质鉴定 Web MVP

- Next.js 16、React 19 和 TypeScript 前端。
- TanStack Query 管理参考库、任务状态、结果和文件请求。
- PLINK `.bed/.bim/.fam` 三文件上传界面。
- 任务状态轮询及 `queued/running/completed/rejected/failed` 展示。
- 样本鉴定结果、核心质控指标和审计文件下载。
- 响应式桌面与移动端布局。
- Next.js 同源 API 代理，无需开放浏览器跨域访问。
- 独立 `shrimp-web:0.1.0` 生产镜像并接入 Docker Compose。
- TypeScript 检查和 Next.js 生产构建通过。
- 浏览器验证首页、参考库数据、任务结果页和下载链接，控制台无错误。
- 支持 PLINK 三文件和 VCF/VCF.GZ 单文件上传；两者统一进入 PLINK + KNN 分析管线。
- 新增 `mock/` 输入数据和输入规范文档。

## 下一阶段

阶段 6 将实现分子指纹展示模块，包括样本查询、位点浏览、指纹图谱和种质间比较；
随后再加入用户、权限、对象存储和生产环境安全配置。
