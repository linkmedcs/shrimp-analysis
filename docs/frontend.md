# Web Frontend

阶段 5 使用 Next.js、React、TypeScript 和 TanStack Query 实现种质鉴定 Web MVP。

## 功能

```text
首页
├── 冻结参考库概览
├── BED/BIM/FAM 文件选择
├── 上传并创建异步任务
└── 鉴定流程说明

任务页
├── queued/running/final 状态轮询
├── 样本和位点汇总
├── 每个样本的种质鉴定结果
├── 拒绝及失败信息
└── 结果、质控、CSV 和日志下载
```

## 本地开发

先启动阶段 4 后端：

```bash
docker compose up -d postgres redis migrate api worker
```

然后启动前端开发服务器：

```bash
cd frontend
npm install
API_PROXY_URL=http://localhost:8000 npm run dev
```

访问 `http://localhost:3000`。

## Docker Compose

启动完整系统：

```bash
docker compose up --build -d
```

服务地址：

```text
Web      http://localhost:3000
API      http://localhost:8000
API Docs http://localhost:8000/docs
```

浏览器只访问 Next.js 的 `/api/*` 同源地址。Next.js 根据 `API_PROXY_URL` 将请求代理
到 Compose 网络中的 `http://api:8000`，因此不需要在 FastAPI 开放通配 CORS。

## 代码结构

```text
frontend/
├── app/
│   ├── jobs/[jobId]/page.tsx
│   ├── globals.css
│   ├── layout.tsx
│   ├── page.tsx
│   └── providers.tsx
├── components/
│   ├── reference-summary.tsx
│   ├── result-view.tsx
│   ├── site-header.tsx
│   ├── status-pill.tsx
│   └── upload-panel.tsx
├── lib/
│   ├── api.ts
│   └── format.ts
├── Dockerfile
├── next.config.ts
└── package.json
```

## 验证

```bash
cd frontend
npm run typecheck
npm run build
```

生产镜像使用 Next.js standalone 输出，以非 root `node` 用户运行。前端不包含 PLINK、
参考基因型或数据库凭据。
