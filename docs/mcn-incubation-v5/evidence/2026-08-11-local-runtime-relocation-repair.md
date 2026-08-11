# 第五版本地运行目录迁移修复

日期：2026-08-11

## 结论

第五版代码仓库从 `/Users/yangyucheng/Documents/第五版营销系统` 迁移到 `/Users/yangyucheng/Documents/ChatGPT/第五版营销系统` 后，源码与锁文件完整，但被复制的 Python 虚拟环境入口仍指向旧绝对路径，前端 Tailwind 解析又回落到没有 `node_modules` 的 Git 根。两项本地运行故障均已修复，统一入口 `http://127.0.0.1:2026/` 返回 `HTTP 200`。

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

Gateway 恢复后，Next 与 Nginx 虽已监听，首次页面请求仍超时。`logs/frontend.log` 显示 Tailwind 4 从 Git 根解析 `@import "tailwindcss"`，而本仓库的 pnpm workspace 和依赖位于 `frontend/`。

先写 `postcss-config.test.ts` 固定解析基准，再将 `@tailwindcss/postcss` 的 `base` 显式设为前端命令的 `process.cwd()`。本仓库所有 host-side pnpm 命令本来就按开发守则从 `frontend/` 执行，因此该值稳定指向依赖根，没有在仓库根制造第二份 `node_modules` 或本地软链接。

## 验证

- `make dev`：Gateway、Frontend 与 Nginx 均启动。
- `curl --max-time 30 http://127.0.0.1:2026/`：`HTTP 200`。
- `python3 ../scripts/pnpm.py check`：ESLint 与 TypeScript 通过。
- `python3 ../scripts/pnpm.py test`：`988 passed`。
- PostCSS 聚焦失败测试修复后：`1 passed`。
- Git 变更只包含 PostCSS 配置、测试和同步文档，不包含 `.venv`、`node_modules`、日志或凭证。

## 运行边界

本地服务当前保持运行，供右侧界面验收。页面可打开不等于 M01、宝妈孵化或主体问答业务质量通过；新的付费模型连续会话仍须用户明确确认，并按 `current/PREFLIGHT_PROTOCOL.md` 记录。
