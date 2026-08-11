# 第五版本地运行目录迁移修复

日期：2026-08-11

## 结论

第五版代码仓库从 `/Users/yangyucheng/Documents/第五版营销系统` 迁移到 `/Users/yangyucheng/Documents/ChatGPT/第五版营销系统` 后，源码与锁文件完整，但复制过来的 Python 虚拟环境和 Turbopack `.next` 缓存仍嵌有旧绝对路径；此外，`127.0.0.1:2026` 在 Next 开发模式下没有被允许加载跨源开发资源。三项本地运行故障均已修复。统一入口和实际工作区必须通过浏览器水合验收，不能再以首页一次 `HTTP 200` 代替工作区验收。

这不是模型、API Key、孵化内核或 A38 数据合同故障，也没有发起模型调用。

## Gateway 故障

首次 `make dev` 的 Gateway 启动失败：

```text
ModuleNotFoundError: No module named 'mcn_incubation'
```

仓库 `uv` workspace、`deerflow-harness` 对 `mcn-incubation-core` 的依赖和当前 editable `.pth` 均正确。真正异常是 `backend/.venv/bin/uvicorn` 的 shebang 仍为旧目录：

```text
#!/Users/yangyucheng/Documents/第五版营销系统/backend/.venv/bin/python
```

执行 `cd backend && uv sync --reinstall` 后，221 个当前锁定包与三个本地 workspace 包在现目录重装，`uvicorn` 入口改为当前绝对路径，Gateway 正常启动。`.venv` 是被 Git 忽略的本地生成物，没有提交环境文件。

## Frontend 故障

Gateway 恢复后，Next 与 Nginx 虽已监听，`/` 可以返回 200，但 `/workspace` 编译超时。`logs/frontend.log` 显示 Tailwind 4 从 Git 根解析 `@import "tailwindcss"`，而本仓库的 pnpm workspace 和依赖位于 `frontend/`。

第一次修复先写 `postcss-config.test.ts`，再将 `@tailwindcss/postcss` 的 `base` 设为 `process.cwd()`。该测试从 `frontend/` 运行且只访问首页，遗漏了真实工作区路由，因此产生假通过。复查中分别试验了 PostCSS 绝对基准和 `turbopack.root`；两者都未改变 `/workspace` 的真实故障，相关试验改动已撤销，没有把猜测留在代码里。

决定性证据来自 `.next` source map：其中仍引用迁移前的 `/Users/yangyucheng/Documents/第五版营销系统/frontend/package.json`。停止服务并删除可再生的 `frontend/.next` 后，保留原 PostCSS/Nextra 配置从零编译，`/workspace` 正常跳转到 `/workspace/chats/new` 并返回 200；新缓存不再包含旧路径。

页面随后暴露第二层问题：`localhost:2026` 能完整显示输入框，`127.0.0.1:2026` 只有服务端侧栏骨架，浏览器反复报告 `/_next/webpack-hmr` 握手失败。Next 日志明确要求允许 `127.0.0.1`。先修改 `dev-origins.test.ts` 得到失败测试，再把该回环地址加入默认 `allowedDevOrigins` 并对环境扩展项去重；局域网地址仍须显式配置。

## 验证

- `make dev`：Gateway、Frontend 与 Nginx 均启动并保持运行。
- `curl -L http://127.0.0.1:2026/workspace`：最终路由 `/workspace/chats/new` 返回 200。
- Playwright 分别访问 `localhost` 与 `127.0.0.1`：两者均为 200、输入框可见，控制台错误、失败请求和 4xx/5xx 响应均为 0。
- `dev-origins.test.ts`：新增断言先失败，修复后 10 项通过，覆盖默认回环地址、环境扩展和去重。
- `python3 ../scripts/pnpm.py check`：ESLint 与 TypeScript 通过。
- `python3 ../scripts/pnpm.py test`：126 个测试文件、989 项测试全部通过。
- `python3 ../scripts/pnpm.py format`：Prettier 通过。
- 纠正后的 Git 变更只包含开发来源配置、测试和同步文档；`.venv`、`.next`、`node_modules`、日志和凭证均未跟踪。

## 运行边界

本地服务当前保持运行，供右侧界面验收。页面可打开不等于 M01、宝妈孵化或主体问答业务质量通过；新的付费模型连续会话仍须用户明确确认，并按 `current/PREFLIGHT_PROTOCOL.md` 记录。
