# 测试分层（V2 Phase 1 骨架）

当前仓库不是 pytest 项目，使用标准库 unittest；`tests/acceptance` 没有 `__init__.py`，不会被 `discover -s tests` 自动收集，浏览器验收按独立命令执行。不把 47 用例/82% 覆盖率作为全局门槛。

## Layer 1：代码级

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

覆盖单元、契约、治理、可靠性、worktree、model、workbench store/service/API。全量结果必须记录环境与失败原因；未运行项标 `not_run`。

## Layer 2：接口与集成

```bash
PYTHONPATH=src python -m unittest \
  tests.test_workbench_api tests.test_workbench_store tests.test_workbench_service \
  tests.test_workflow tests.test_managed_runs tests.test_execution_preparation -v
```

这些用例使用真实 FastAPI/TestClient、SQLite、LangGraph checkpoint 和临时 Git 仓库，不代表真实业务验收。

## Layer 3：UI / E2E

```bash
PYTHONPATH=src DOCLOOP_BROWSER_CHANNEL=chrome \
  python -m unittest tests.acceptance.test_workbench_browser -v
```

需要本机浏览器；Windows 建议使用 `msedge`（默认），macOS 可用 `chrome`。模型配置/DPAPI/Codex 依赖环境，失败不得包装为通过。

## 证据字段（Phase 1 起）

每条测试/检查记录：`test_case_id`、`task_id`、`test_layer`、`command`、`exit_code`、`executed_at`、`log_path`、`screenshot_path`、`result`。`not_run` 可表达但不得计为通过。完整 REQ→AC→TASK→TC→RUN→evidence→Commit 在 Phase 4 接入。
