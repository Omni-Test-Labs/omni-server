# Omni-Server

测试任务的调度中心，维护 Task Queue、Device Registry (设备注册表) 和 Results Data (报告存储)。

## Pipeline 职责说明

本仓库**不包含** Pipeline 执行引擎代码。Pipeline 的职责划分如下：

### Server (本仓库)
- 定义 Pipeline 数据模型（TaskManifest, PipelineStep）
- 创建和存储 Pipeline 配置
- 任务调度与分配
- 管理任务状态（pending → assigned → running → completed）
- 接收执行结果，记录最终状态

### Runner (omni-runner 仓库)
- **Pipeline Engine**: 本地执行编排引擎
  - 拓扑排序、依赖管理
  - 流程控制（must_pass, always_run）
  - 步骤调度

详细说明请参见 [architecture.md](./architecture.md)。

## 技术栈

- FastAPI
- PostgreSQL
- Redis

## 测试覆盖率

- 测试数量: 73 个
- 通过率: 100% ✅
- 覆盖率: 96.20% ✅ (达到 95% 要求)

## 运行测试

```bash
source .venv/bin/activate
pytest --cov=src tests/
```

## 依赖关系

- 与 `omni-runner` 通过 HTTP (protocol.md) 通信
- 与 `omni-sdk-py` 共享模型定义
