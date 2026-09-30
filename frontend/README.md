# EC2 Capacity Block Search - 前端

异步版本的前端应用，支持任务提交和历史查看。

## 功能特性

- ✅ 多实例类型选择
- ✅ 多区域选择（支持按地区分组）
- ✅ 日期范围预测（0-6天）
- ✅ 任务提交和追踪
- ✅ 任务历史查看
- ✅ 结果 CSV 下载
- ✅ 自动刷新任务状态

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
VITE_API_ENDPOINT=https://xxxxx.execute-api.us-west-2.amazonaws.com/prod
VITE_API_KEY=your-api-key-here
```

### 3. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

### 4. 构建生产版本

```bash
npm run build
```

构建产物在 `dist/` 目录。

## 部署到 AWS Amplify

1. 构建项目：`npm run build`
2. 进入 `dist` 目录，选择所有文件
3. 压缩为 zip 文件
4. 在 Amplify Console 上传 zip

> 🔒 **安全建议（重要）**：前端产物中内嵌了 API Key（公开可见，非身份认证）。通过 Amplify 部署对外访问时，强烈建议：
> - 开启 Amplify **访问控制（Access control）→ 用户名 / 密码登录（Basic Auth）**，防止页面被任何人公开访问；
> - 为 Amplify 应用 / API Gateway 接入 **AWS WAF**，限制来源与速率、拦截恶意流量。
>
> 详见根目录 [README](../README.md) 的「安全建议」与「免责声明」。

## 使用说明

### 提交任务

1. 选择实例类型（可多选）
2. 选择持续时间（1-182天）
3. 选择开始日期
4. 选择预测天数（0-6天）
5. 选择查询区域
6. 点击"提交任务"

### 查看任务历史

1. 切换到"任务历史"标签
2. 查看所有已提交的任务
3. 任务完成后点击"下载"获取 CSV 结果
4. 页面每 10 秒自动刷新状态

## 项目结构

```
frontend/
├── src/
│   ├── components/
│   │   ├── SearchForm.jsx      # 搜索表单
│   │   └── TaskHistory.jsx     # 任务历史
│   ├── data/
│   │   └── instanceTypes.json  # 实例类型配置
│   ├── App.jsx                 # 主应用
│   └── main.jsx                # 入口文件
├── index.html
├── vite.config.js
└── package.json
```

## 技术栈

- React 18
- Material-UI 5
- Vite 5
- Axios
- Day.js

## 故障排查

### API 调用失败

检查：
- `.env` 文件中的 API_ENDPOINT 和 API_KEY 是否正确
- 浏览器控制台的网络请求
- API Gateway 是否正常运行

### 任务状态不更新

- 页面每 10 秒自动刷新
- 手动点击刷新按钮
- 检查后端 Step Functions 执行状态

### 下载失败

- 确认任务状态为 COMPLETED
- 检查 S3 bucket 权限
- 预签名 URL 有效期为 6 小时
