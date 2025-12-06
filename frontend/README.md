# 前端项目 - x402 代付助手

基于 React + TypeScript + Vite + Tailwind CSS 构建的 Web3 代付转账前端应用。

## 前置要求

- **Node.js** >= 18.0.0
- **npm** >= 9.0.0 或 **yarn** >= 1.22.0 或 **pnpm** >= 8.0.0
- **MetaMask** 浏览器扩展（用于钱包连接）

## 快速开始

```bash
# 1. 检查 Node.js 版本（需要 >= 18.0.0）
node --version

# 2. 进入前端目录
cd frontend

# 3. 安装依赖
npm install

# 4. 启动开发服务器
npm run dev
```

**注意**：确保后端服务 `main.py` 已启动在 `http://localhost:9000`，前端才能正常工作。

### 验证安装

安装完成后，你可以运行以下命令验证：

```bash
# 检查依赖是否安装成功
npm list --depth=0

# 运行代码检查
npm run lint

# 构建项目（验证配置是否正确）
npm run build
```

## 详细安装步骤

### 1. 安装依赖

```bash
cd frontend
npm install
```

或使用其他包管理器：

```bash
# 使用 yarn
yarn install

# 使用 pnpm
pnpm install
```

### 2. 配置文件说明

项目使用以下配置文件，通常不需要修改：

- `vite.config.ts` - Vite 构建配置
- `tailwind.config.js` - Tailwind CSS 配置
- `postcss.config.js` - PostCSS 配置（用于 Tailwind）
- `tsconfig.app.json` - TypeScript 应用配置
- `tsconfig.node.json` - TypeScript Node 配置
- `eslint.config.js` - ESLint 代码检查配置

### 3. 后端服务配置

确保后端服务已启动并运行在 `http://localhost:9000`。

如果需要修改后端地址，请编辑 `src/App.tsx` 中的第 150 行：

```typescript
const response = await fetch('http://localhost:9000/chat', { 
  // ... 其他配置
});
```

## 运行项目

### 开发模式

```bash
npm run dev
```

项目将在 `http://localhost:5173` 启动（Vite 默认端口）。

### 构建生产版本

```bash
npm run build
```

构建产物将输出到 `dist/` 目录。

### 预览生产构建

```bash
npm run preview
```

### 代码检查

```bash
npm run lint
```

## 项目结构

```
frontend/
├── src/
│   ├── App.tsx          # 主应用组件
│   ├── main.tsx         # 应用入口
│   └── index.css        # 全局样式（包含 Tailwind）
├── public/              # 静态资源目录
├── index.html           # HTML 模板
├── package.json         # 依赖配置
├── vite.config.ts       # Vite 配置
├── tailwind.config.js   # Tailwind 配置
├── postcss.config.js    # PostCSS 配置
└── tsconfig.*.json      # TypeScript 配置
```

### 所有依赖安装

运行 `npm install` 会自动安装 `package.json` 中列出的所有依赖（包括生产和开发依赖）。

## 环境要求

- 现代浏览器（支持 ES2022+）
- MetaMask 扩展已安装并配置了 Sepolia 测试网

## 常见问题

### 端口冲突

如果 5173 端口被占用，Vite 会自动选择下一个可用端口。你可以在终端输出中查看实际使用的端口。

### 后端连接失败

确保：
1. 后端服务 `main.py` 已启动在 `localhost:9000`
2. 后端 CORS 配置允许前端域名
3. 检查浏览器控制台是否有错误信息

### MetaMask 未检测到

确保：
1. MetaMask 扩展已安装并启用
2. 已切换到 Sepolia 测试网络
3. 浏览器允许扩展访问网站

## 开发注意事项

1. 代码使用 TypeScript 严格模式，注意类型检查
2. 样式使用 Tailwind CSS 工具类，无需额外 CSS 文件
3. 所有以太坊交互都通过 Ethers.js 6.x API
4. 签名使用 EIP-712 标准，确保钱包支持

## 完整依赖清单

### 一键安装

所有依赖已配置在 `package.json` 中，运行以下命令即可安装：

```bash
npm install
```

### 生产依赖（5个）

```
react ^19.2.0
react-dom ^19.2.0
ethers ^6.15.0
lucide-react ^0.555.0
react-markdown ^10.1.0
uuid ^13.0.0
```

### 开发依赖（15个）

```
vite ^7.2.4
@vitejs/plugin-react ^5.1.1
typescript ~5.9.3
tailwindcss ^3.4.17
autoprefixer ^10.4.22
postcss ^8.5.6
eslint ^9.39.1
@eslint/js ^9.39.1
eslint-plugin-react-hooks ^7.0.1
eslint-plugin-react-refresh ^0.4.24
globals ^16.5.0
typescript-eslint ^8.46.4
@types/node ^24.10.1
@types/react ^19.2.5
@types/react-dom ^19.2.3
```

**总计**：6 个生产依赖 + 15 个开发依赖 = 21 个包