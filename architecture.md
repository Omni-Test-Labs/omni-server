# 架构设计：Pipeline 职责划分

## 概述

本文档 clarifies 为什么 `omni-runner` 包含 pipeline 引擎代码，以及它与 `"管生管死不管过程"` 设计原则的关系。

## 职责划分原则

### Server (omni-server) - Pipeline 的定义者和管理者

**职责范围：**
- 定义 Pipeline 数据模型（TaskManifest, PipelineStep）
- 创建和存储 Pipeline 配置
- 任务调度与分配（决定哪个 runner 执行哪个任务）
- 管理任务状态（pending → assigned → running → completed）
- 接收执行结果，记录最终状态
- 提供 API 接口供用户查看 pipeline 定义

**不涉及的实现细节：**
- Pipeline 步骤如何执行
- 依赖关系如何解析
- 重试如何处理
- must_pass 逻辑如何实现

### Runner (omni-runner) - Pipeline 的执行引擎和本地控制器

**职责范围：**
- 解析 Server 下发的 TaskManifest 配置
- **Pipeline Engine**: 负责本地执行的编排逻辑
  - 拓扑排序（确定步骤执行顺序）
  - 依赖管理（depends_on 检查）
  - 步骤调度（选择合适的 executor）
  - 流程控制（must_pass, always_run, failure_policy）
- 执行各个步骤（调用相应的 executor）
- 处理重试、超时等运行时行为
- 收集执行结果并上报

**核心职责：** "控制执行" - 按照配置控制本地如何执行任务

## 为什么 Runner 需要 Pipeline 代码？

### 设计依据

根据 `protocol.md` 和 `ROADMAP.md` 的明确定义：

1. **protocol.md (第 26 行)**：
   > "Runner 需将其解析为内存中的 Pipeline 执行序列"

2. **ROADMAP.md (第 36 行，Phase M3)**：
   > "**Omni-Runner:** 引入 `Pipeline Engine`，支持串行/并行执行，支持 `must_pass` 和 `failure_policy` 控制."

3. **pipeline_guide.md**：
   Pipeline 的核心价值在于 **跨技术栈编排**，需要在运行时动态调度不同类型的执行器。

### 实际例子

Server 发送配置：
```json
{
  "pipeline": [
    {
      "step_id": "setup",
      "order": 1,
      "type": "python",
      "cmd": "pip install -r requirements.txt",
      "must_pass": true
    },
    {
      "step_id": "test",
      "order": 2,
      "type": "binary",
      "cmd": "./bin/stress_test",
      "depends_on": ["setup"],
      "must_pass": true,
      "retry_policy": {"max_retries": 3}
    },
    {
      "step_id": "cleanup",
      "order": 3,
      "type": "shell",
      "cmd": "rm -rf /workspace",
      "always_run": true,
      "depends_on": ["test"]
    }
  ]
}
```

Runner 的 PipelineEngine 处理：
1. 解析 dependencies 建立 DAG：setup → test → cleanup
2. 执行 setup（Python executor）
3. 检查 setup 结果（必须成功）
4. 执行 test（Binary executor）
5. 如果失败，重试 3 次
6. 无论 test 成功与否，执行 cleanup（always_run: true）
7. 上报每个步骤的执行结果

## "管生管死不管过程" 的正确理解

| 原则 | Server 管 | Runner 管 | 不管 |
|------|----------|----------|------|
| **管生** | 创建任务、分配设备 | - | - |
| **管死** | 确定最终任务状态 | 实时执行、重试、超时控制 | - |
| **不管过程** | 不关心 Shell 如何执行、Python 如何运行 | 不关心业务逻辑、业务价值 | - |

**核心理解：**
- Server 定义 "做什么"（what to do）
- Runner决定 "怎么做"（how to do it）
- Pipeline Engine 是 Runner 实现 "怎么做" 的核心组件

## 代码分布

### Server (omni-server/src/omni_server/models.py)

```python
class PipelineStep(BaseModel):
    """数据模型：仅定义结构"""
    step_id: str
    order: int
    step_type: StepType
    cmd: str
    depends_on: list[str]
    must_pass: bool
    always_run: bool
    # ... 其他字段
```

### Runner (omni-runner/src/pipeline/engine.rs)

```rust
pub struct PipelineEngine;

impl PipelineEngine {
    pub async fn execute(&self, manifest: &TaskManifest) -> Result<Vec<StepResult>> {
        // 拓扑排序
        let ordered_steps = self.topological_sort(&manifest.pipeline)?;
        
        for step in ordered_steps {
            // 依赖检查
            if !self.can_execute_step(&step, &completed_steps, &dependency_map) {
                return Skip;
            }
            
            // 选择 executor
            let executor = self.get_executor(&step)?;
            let result = executor.execute(&step).await?;
            
            // must_pass 逻辑
            if !success && step.must_pass {
                break;
            }
        }
    }
}
```

## 对比：为什么不是 Server 编排？

考虑两种架构对比：

### 架构 A：Server 编排，Runner 只执行步骤

```
Server                    Runner
  |                        |
  | 1. 解析 pipeline         |
  | 2. 拓扑排序               |
  | 3. 决定执行顺序        <-- 网络往返 --> 4. 执行步骤 A
  | 5. 调度步骤 B         <-- 网络往返 --> 6. 执行步骤 B
  | 7. 决定重试           <-- 网络往返 --> 8. 执行
  | 9. 处理 always_run     <-- 网络往返 --> 10. 执行
```

**问题：**
- 需要大量网络往返
- 延迟高
- Server 需要了解 Runner 实时状态
- 网络故障时无法继续

### 架构 B：Runner 编排（当前架构）

```
Server                    Runner
  |                        |
  | 1. 发送 TaskManifest ---> |
  |                         | 2. 解析 pipeline
  |                         | 3. 本地编排（拓扑排序、依赖、重试）
  |                         | 4. 执行所有步骤
  | 5. 接收最终结果 <------ |
```

**优势：**
- 单次网络调用
- 本地执行，低延迟
- 网络故障不影响本地执行
- 边缘计算，响应快
- 符合 "边缘执行" 架构原则

## 总结

| 组件 | Pipeline 相关职责 | 原因 |
|------|----------------|------|
| **Server** | 定义 Pipeline 结构 | 控制配置、管理状态 |
| **Runner** | Pipeline 编排引擎 | 本地执行控制、低延迟 |

**Pipeline 在 Runner 中的定位：**

Pipeline Engine 是 Runner 实现智能本地执行的核心组件。它不是在 "定义 pipeline"，而是在 "控制如何按照定义执行pipeline"。这完全符合边缘计算架构和 "管生管死不管过程" 的设计原则。
