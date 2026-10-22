---
title: Workspace 与沙箱：给 Agent 一块可控的工作台
date: 2026-10-09
source: https://mp.weixin.qq.com/s/LCrqnu-k1awBkLCaUDNeVw
images: 0
---

> 系列：《AgentScope Java 2.0 组件深挖》第 8 篇  
> 上一篇：【连载 \#7】Middleware：把横切逻辑挂上循环  
> 下一篇预告：Memory

上一篇把横切挂在循环外层：洋葱四钩、`order()`、内置中间件，以及「别直接 `Files.write` 工作区」那条坑。本篇把镜头挪到 **Harness 的物理工作台** ——目录约定（`AGENTS.md` / `MEMORY.md` / `skills` / `plans` 等）、文件系统三模式（本机 + shell / 远程 KV / 沙箱）、沙箱扩展与安全边界、常见坑。

事实以官方 v2 Workspace / Filesystem / Sandbox / Harness Architecture 文档、仓库 `v2.0.1` 源码（`IsolationScope`、`LocalFilesystemSpec`、`RemoteFilesystemSpec`、`DockerFilesystemSpec`、`SandboxFilesystemSpec`）与 `agentscope-examples/documentation` 下 `Workspace*Example` 为准。坐标统一 `io.agentscope.*`。文档实用片段与示例在个别 Builder 方法名上不完全一致（例如文档常见 `.systemPrompt(...)`，`v2.0.1` 示例写 `.sysPrompt(...)`）——**可运行代码以` v2.0.1` 示例为准**，概念与目录布局以文档为准。

依赖取系列一致的 **2.0.1** （Harness 入口在 `agentscope-harness`）：
    
    
    <dependency>  
      <groupId>io.agentscope</groupId>  
      <artifactId>agentscope-harness</artifactId>  
      <version>2.0.1</version>  
    </dependency>  
    

多副本远程 KV / Redis 快照等按需再加扩展模块（如 `agentscope-extensions-redis`）；Docker 沙箱需本机 Docker 可用。

## 一、系列衔接：横切挂好了，文件落在哪？  

Middleware 回答「横切挂在哪」。长跑还差另一半：

  * 人格、知识、技能、子 Agent 声明写在哪儿，才能多租户又不改代码？
  * 长期记忆、会话日志、Plan 文件物理上落本机、Redis，还是容器里？
  * `execute` 是宿主 `sh -c`，还是沙箱内执行？不可信代码能不能碰生产机？
  * 跨 `call()`、跨副本，怎么把「装过的依赖」一起恢复？

官方把答案收进 **Workspace（逻辑目录）+ Filesystem（物理后端）** ：同一套相对路径，可换三种落地方式；沙箱是其中一种，并额外提供隔离执行与快照恢复。上一篇 Architecture 提示过：读写作 `harnessAgent.getWorkspaceManager()`，不要 `java.nio.Files`——本篇展开为什么。

## 二、Workspace：逻辑目录，不是死路径  

文档强调：画成 `.agentscope/workspace/...` 只是**默认本机落点** 。同一棵树可以落在：

  1. 本机磁盘（`LocalFilesystemSpec` / 省略 `filesystem(...)`） 
  2. 远程分布式存储（Redis / JDBC / OSS，经 `RemoteFilesystemSpec`） 
  3. 沙箱容器（`DockerFilesystemSpec` 等 `SandboxFilesystemSpec` 家族）

相对路径不变，变的是后端；agent 业务代码不用为换部署形态重写。

### 2.1 目录约定（文档布局）
    
    
    .agentscope/workspace/  
    ├── AGENTS.md                 ← 静态：人格 + 行为  
    ├── MEMORY.md                 ← 长期：整理后的事实（受 token 预算注入）  
    ├── tools.json                ← 静态：MCP + allow/deny（可选）  
    ├── memory/YYYY-MM-DD.md      ← 长期：按日追加的事实流水  
    ├── knowledge/  
    │   ├── KNOWLEDGE.md          ← 入口全文注入  
    │   └── ...                   ← 其余只列路径，按需 read_file  
    ├── skills/<name>/SKILL.md  
    ├── subagents/<agent-id>.md  
    ├── plans/PLAN.md             ← Plan Mode 产物  
    └── agents/<agentId>/  
        ├── sessions/             ← 永不压缩的会话日志  
        └── tasks/                ← 子 Agent 后台任务记录  
    

三类生命周期别混：

类型| 谁写| 例子  
---|---|---  
静态资产| 你 / 团队| `AGENTS.md`、`knowledge/`、`skills/`、`subagents/`、`tools.json`  
运行时文件| 框架 / agent| `agents/.../sessions/`、`tasks/`、`plans/`  
长期记忆| agent + 后台任务| `MEMORY.md`、`memory/`  
  
**`AgentState` 不在这棵树里。** 对话缓冲、压缩摘要、权限 / Plan Mode 子上下文等易失快照，进独立的 `AgentStateStore`（默认 `~/.agentscope/state/...`），按 `(userId, sessionId)` 寻址。工作区存「持久文件产物」；`AgentState` 存「本轮可恢复的运行时上下文」——两套存储、两套生命周期。

### 2.2 每轮怎么进 system prompt

`WorkspaceContextMiddleware`（`io.agentscope.harness.agent.middleware`）在每次 reasoning 前拼装：Session Context、Memory / Knowledge 引导、按 filesystem 模式分支的 Workspace 说明，以及 `<loaded_context>` 里注入的 `AGENTS.md`（全文）、`MEMORY.md`（默认约 `maxContextTokens=8000` 预算内截断）、`knowledge/KNOWLEDGE.md` \+ 路径清单、`additionalContextFile` 指定文件。改 `AGENTS.md` / `MEMORY.md`，**下一次` call()` 即生效**，无需重建 agent。

关键文件走 **两层读** ：先问当前 `AbstractFilesystem`，没有再回退本地 `workspace.resolve(...)`。写入永远走 filesystem 后端。共享存储模式下，本机 git 同步的模板是下层，KV 覆盖是上层——首副本能立刻跑，管理台改完的人格下一轮全副本可见。

### 2.3 Builder 与解析顺序

不显式 `.workspace(...)` 时优先级：`workspace(Path|String)` → 系统属性 `agentscope.workspace` → 环境变量 `AGENTSCOPE_WORKSPACE` → 默认 `${user.dir}/.agentscope/workspace`。

`v2.0.1` 文档示例 `WorkspaceSetupExample` 会创建 `AGENTS.md`、`knowledge/`、`subagents/`，并用 `additionalContextFile("PREFERENCES.md")` 注入额外全文：
    
    
    import io.agentscope.core.agent.RuntimeContext;  
    import io.agentscope.harness.agent.HarnessAgent;  
    import java.nio.file.Files;  
    import java.nio.file.Path;  
      
    Path workspace = Files.createTempDirectory("agentscope-workspace-example");  
    // 写入 AGENTS.md / knowledge/KNOWLEDGE.md / subagents/researcher.md / PREFERENCES.md …  
      
    HarnessAgent agent =  
            HarnessAgent.builder()  
                    .name("phoenix-assistant")  
                    .sysPrompt("You are the Phoenix project assistant.")  
                    .model("dashscope:qwen-plus")  
                    .workspace(workspace)  
                    .additionalContextFile("PREFERENCES.md")  
                    .maxContextTokens(4000)  
                    .build();  
      
    RuntimeContext ctx = RuntimeContext.builder().sessionId("workspace-demo").build();  
    agent.call(/* UserMessage */, ctx).block();  
    

多租户：运行时数据按 `IsolationScope` / `userId` 进命名空间；静态资产默认共享，可用 `workspace/<userId>/skills/` 等目录覆盖同名共享技能 / 子 Agent（下层独有仍可见，重名上层优先）。

## 三、文件系统三模式：一行切换后端  

`HarnessAgent.builder().filesystem(...)` 三选一；**不写 = 模式 3（本机 + shell）** 。所有文件工具（文档：`read_file` / `write_file` / `edit_file` / `grep_files` / `glob_files` / `list_files`）与可选 `execute` 都走同一抽象。

模式| 配置| Shell？| 何时用  
---|---|---|---  
1 · 共享存储| `RemoteFilesystemSpec`| 无（故意）| 多副本共享 `MEMORY.md` / 会话日志 / 任务记录  
2 · 沙箱| `DockerFilesystemSpec` 等| 有（沙箱内）| 隔离执行、跨调用恢复、可选快照  
3 · 本机 + shell| `LocalFilesystemSpec` 或省略| 有（宿主 `sh -c`）| 单机 / 本地 / 信任环境 / 测试  
  
`filesystem(...)` 与 `abstractFilesystem(...)` 互斥；后者是自管逃生口，常规不必用。

### 3.1 模式 3：本机 + shell（默认）
    
    
    import io.agentscope.harness.agent.filesystem.spec.LocalFilesystemSpec;  
    import io.agentscope.harness.agent.workspace.LocalFsMode;  
      
    HarnessAgent agent =  
            HarnessAgent.builder()  
                    .name("local-shell-agent")  
                    .sysPrompt("You are a helpful assistant with shell access.")  
                    .model("dashscope:qwen-plus")  
                    .workspace(workspace)  
                    .filesystem(  
                            new LocalFilesystemSpec()  
                                    .executeTimeoutSeconds(30)  
                                    .env("EXAMPLE_VAR", "hello-from-agentscope")  
                                    .inheritEnv(true)  
                                    .mode(LocalFsMode.ROOTED)   // 默认；文档另有 SANDBOXED / UNRESTRICTED  
                                    .project(Paths.get("/path/to/project"))  
                                    .projectWritable(true))     // 非元数据写入落到 project  
                    .build();  
    

要点（文档 + `LocalFilesystemSpec` 源码）：

  * 实际是 **Overlay** ：上层 workspace（可写 + shell），下层 project（只读兜底）；shell 的 cwd 是 project。 
  * 路径策略默认 `ROOTED`：绝对路径只允许 workspace / project / `additionalRoots`；`..` 穿越拒绝。`UNRESTRICTED` 仅信任环境。 
  * `projectWritable(true)`：`MEMORY.md`、`agents/`、`skills/` 等元数据仍写 workspace；`src/...`、`pom.xml` 等落到项目目录——否则脚手架代码会全堆进 `.agentscope/workspace/`。 
  * **生产不要用本机模式跑不可信代码** ：`execute` 就是宿主 `sh -c`。

### 3.2 模式 1：远程 KV（无 shell）
    
    
    import io.agentscope.extensions.redis.RedisDistributedStore;  
    import io.agentscope.harness.agent.DistributedStore;  
    import io.agentscope.harness.agent.IsolationScope;  
    import io.agentscope.harness.agent.filesystem.spec.RemoteFilesystemSpec;  
    import redis.clients.jedis.JedisPooled;  
      
    DistributedStore store = RedisDistributedStore.fromJedis(jedis, "agentscope:example:");  
      
    HarnessAgent agent =  
            HarnessAgent.builder()  
                    .name("shared-agent")  
                    .sysPrompt("You are a helpful assistant.")  
                    .model("dashscope:qwen-plus")  
                    .workspace(workspace)  
                    .distributedStore(store) // 一并接线 stateStore 等  
                    .filesystem(new RemoteFilesystemSpec().isolationScope(IsolationScope.USER))  
                    .build();  
    

`AGENTS.md` / `MEMORY.md` / `tools.json` / `memory/` / `skills/` / `sessions/` 等按文档路由进 KV 命名空间；未列出的路径回落本地（仍无 shell）。本机磁盘放团队 git 同步的模板；运行时产物长在 Redis。要 shell → 换模式 2 或 3。

可用 `BaseStore`：`RedisStore`（`agentscope-extensions-redis`）、`JdbcStore`（`agentscope-extensions-mysql`）、`InMemoryStore`（测试，在 harness 内）。

### 3.3 模式 2：沙箱（下节展开）

文件与命令进容器；宿主不被碰。后端可选 Docker / Kubernetes（agent-sandbox）/ Daytona / E2B / AgentRun——同一套 `SandboxFilesystemSpec` 接口，agent 代码与 `AGENTS.md` 不变。

## 四、IsolationScope：谁和谁共享一桶  

共享存储与沙箱共用 `IsolationScope`（`io.agentscope.harness.agent.IsolationScope`）：

Scope| 谁共享| 典型场景  
---|---|---  
`USER`（多处默认）| 同一 `userId` 的多 session| SaaS：用户跨会话保留记忆 / 依赖  
`SESSION`| 每个 `sessionId`| 一次性对话沙箱  
`AGENT`| 该 agent 全部用户 / 会话| 公共知识库型  
`GLOBAL`| 整个 store 一个槽| 慎用  
  
降级：`USER` 且无 `userId` → 按 `SESSION`；`SESSION` 且无 `sessionId` → 跳过状态查找、新环境。`AGENT` 用 build 时固定的 agent 名，不因缺字段降级。

**沙箱并发语义是「顺序复用」不是「同实例热共享」** ：同 scope key 的并发调用各自起容器，结束时**最后写入的快照胜出** 。`AGENT` / `GLOBAL` 多用户争用时，用 `executionGuard(...)`（或 `distributedStore(...)` 自动注入）串行化。

`AgentState` 寻址与 scope **正交** ：始终 `(userId, sessionId)`，不跟 IsolationScope 混为一谈。

## 五、沙箱：隔离、快照、镜像契约  

### 5.1 最小 Docker 示例（`v2.0.1` WorkspaceSandboxExample）
    
    
    import io.agentscope.core.agent.RuntimeContext;  
    import io.agentscope.harness.agent.HarnessAgent;  
    import io.agentscope.harness.agent.IsolationScope;  
    import io.agentscope.harness.agent.sandbox.impl.docker.DockerFilesystemSpec;  
      
    HarnessAgent agent =  
            HarnessAgent.builder()  
                    .name("sandbox-agent")  
                    .sysPrompt("You are a coding assistant in a Docker sandbox.")  
                    .model("dashscope:qwen-plus")  
                    .workspace(workspace)  
                    .filesystem(  
                            new DockerFilesystemSpec()  
                                    .image("ubuntu:24.04")  
                                    .isolationScope(IsolationScope.USER)) // 示例显式指定  
                    .build();  
      
    RuntimeContext alice =  
            RuntimeContext.builder().userId("alice").sessionId("alice-s1").build();  
    agent.call(/* 在沙箱内写文件、跑命令 */, alice).block();  
    // 同 userId 再次 call：可复用 / 从快照恢复；另一 userId 看不到 alice 的文件  
    

`IsolationScope` 默认值：Sandbox 文档表写 `USER` 为默认；Filesystem 页 `DockerFilesystemSpec` 选项表写默认 `SESSION`；`LocalFilesystemSpec` 源码注释称与 Remote/Sandbox 一致默认 `USER`。**不要依赖隐式默认** ，像示例一样显式 `.isolationScope(...)`。

文档补充可选：内存 / CPU 限制、网络、端口、环境变量、`snapshotSpec`（`NoopSnapshotSpec` 默认 / `LocalSnapshotSpec` / `OssSnapshotSpec` / `RedisSnapshotSpec` / `JdbcSnapshotSpec` 等）。

### 5.2 启动时投影什么？

沙箱启动时，框架把宿主静态资产 tar 进容器内 `/workspace`（可配）。`SandboxFilesystemSpec` 默认投影根（源码）：`AGENTS.md`、`skills`、`subagents`、`knowledge`、`.skills-cache`。按内容 SHA-256 增量；可用 `workspaceProjectionRoots` / `workspaceProjectionEnabled(false)` 调整。

运行时产物（`MEMORY.md`、`memory/`、`agents/...`）落在沙箱内，随快照跨 `call()` 保留——`npm install` / `pip install` 不必每轮重来。**沙箱内修改默认不回写宿主** ；取产物让 agent `read_file`，或配置 `artifactDeliveryTarget(...)` 注册 `deliver_artifact`（未配置时提示语会说明文件出不了容器）。

### 5.3 多副本三件套

  1. 分布式 `AgentStateStore`（`.stateStore(...)` 或经 `.distributedStore(...)`） 
  2. 非 Noop 的 `snapshotSpec`（OSS / Redis 等） 
  3. 合适的 `IsolationScope`（常见 `USER`）

`distributedStore(RedisDistributedStore.fromJedis(...))` 可一键注入 stateStore + 快照 + executionGuard。仅本地 `JsonFileAgentStateStore` 开沙箱时，文档写明 build 会 **warn** ：状态难跨 JVM / 跨实例。配了 `RemoteFilesystemSpec` / 沙箱却仍用本地 state store 时，文档称 `build()` 会直接 `IllegalStateException` 强制提醒——以你所用小版本行为为准，生产务必显式分布式状态。

### 5.4 安全边界与镜像契约

沙箱解决三件事：执行边界（不可信输入 / 危险命令关进容器）、跨调用恢复可执行环境、多副本共享同一逻辑用户的 workspace slot。

但边界有硬前提——**镜像必须满足运行时契约** ，否则文件工具会「难排查地失败」：

  * POSIX `sh`、核心 utils、`sed` / `grep -rHnF --include` / `find`
  * **GNU**` stat -c`（BSD `stat -f` 不行） 
  * `tar`、`base64`、`python3`（`edit_file` 精确替换依赖） 
  * 可写 workspace 根（默认 `/workspace`）

`ubuntu:24.04` / debian 系通常可用（可能需装 `python3`）；**alpine（BusyBox）与 distroless 不满足** 。换镜像前在容器内跑文档给出的自检命令。

K8s（agent-sandbox）另需运行时 HTTP API（`/execute`、`/upload`、`/download` 等），且 PVC 应挂在 `workspaceRoot`（默认 `/workspace`）；PVC 是工作区持久化第一层，Harness 快照是冷恢复保险。`SandboxState` 身份指针（claimName 等）多副本时仍依赖分布式 `AgentStateStore`。

Docker 可用 `BindMountEntry` 挂宿主目录；托管沙箱（Daytona / E2B）在云上，**不能挂你的本机路径** 。

## 六、和 Middleware / 权限的接缝  

  * Harness 的 workspace 注入本身就是 Middleware（`v2.0.1` 源码类名 `WorkspaceContextMiddleware`）；你用 `.middleware(...)` 加的自定义件 **整体先于** Harness 内置。 
  * 沙箱 / 远程模式下，业务代码写文件应走 `getWorkspaceManager()`；Builder 阶段播种本地模板（尚无 RuntimeContext）才适合直接 `Files.write` 本机 `AGENTS.md`。 
  * 权限系统仍在 Acting 前闸门；沙箱缩小的是「即便放行，破坏半径」——两者互补，不是互相替代。

## 七、常见坑  

  1. **生产用默认本机 + shell 跑不可信任务**  
` execute` = 宿主 `sh -c`。要隔离请换沙箱。

  2. **用` java.nio.Files` 当「工作区 API」**  
沙箱 / 远程 KV 下会写到宿主错位置。运行时 I/O → `getWorkspaceManager()`。

  3. **混用` AgentState` 与 workspace 文件**  
易失运行时进 `AgentStateStore`；`MEMORY.md` / 会话 JSONL / `plans/` 在工作区。恢复链路两边都要配齐。

  4. **远程 KV 模式指望 shell**  
文档明确：模式 1 **不提供** shell。要命令执行用沙箱或本机。

  5. **多副本只换了 filesystem，忘了分布式 state / 快照**  
沙箱元数据与 AgentState 同店；本地 Json store + 沙箱 = 难跨实例 resume。优先 `.distributedStore(...)`。

  6. **`IsolationScope.USER` 却不传 `userId`**  
会降级到 `SESSION`；多会话共享记忆的预期会落空。

  7. **`AGENT` / `GLOBAL` 并发不配 guard**  
同 slot 并发 = 最后快照覆盖。需要串行就配 `executionGuard` / distributedStore。

  8. **沙箱镜像选 alpine / distroless**  
不满足 GNU `stat` / 工具链契约，`grep_files` / `edit_file` / 快照易怪失败。

  9. **以为沙箱内写入会同步回宿主**  
默认不会。产物用 `read_file` 或 `deliver_artifact`。

  10. **`tools.json` 的 `allow` 漏列内置工具**  
allow/deny 在全部注册之后过滤，也会砍掉 `read_file` / `memory_search` / `agent_spawn` 等；白名单务必显式保留需要的内置项。且 MCP 注册在 **build 时一次** ；共享存储改远端 `tools.json` 后要重建 agent。

  11. **脚手架代码写进`.agentscope/workspace/`**  
本地开发助手打开 `projectWritable(true)`，让非元数据写入进 project。

  12. **文档`.systemPrompt` vs 示例 `.sysPrompt`**  
以你依赖的 `v2.0.1` 源码 / 示例编译为准，不要混抄两套片段。

## 八、下一篇预告：Memory  

Workspace 解决「定义与进化文件落在哪、命令在哪跑」。下一篇【连载 \#9】Memory 会专讲 `MEMORY.md` \+ `memory/` 两层长期记忆、`MemoryFlushMiddleware`（`v2.0.1` 源码已有此类）、压缩与大工具结果落盘——接上本篇「记忆通道开了数据才会长进工作区」那条线。

* * *

既然看到这里了，就点个关注吧。

## 参考  

  * https://java.agentscope.io/v2/zh/docs/harness/workspace.html\[1\]
  * https://java.agentscope.io/v2/en/docs/harness/workspace.html\[2\]
  * https://java.agentscope.io/v2/zh/docs/harness/filesystem.html\[3\]
  * https://java.agentscope.io/v2/en/docs/harness/filesystem.html\[4\]
  * https://java.agentscope.io/v2/zh/docs/harness/sandbox.html\[5\]
  * https://java.agentscope.io/v2/en/docs/harness/sandbox.html\[6\]
  * https://java.agentscope.io/v2/en/docs/harness/architecture.html\[7\]
  * https://java.agentscope.io/v2/zh/docs/harness/memory.html（下篇预告）\[8\]
  * https://github.com/agentscope-ai/agentscope-java\[9\]
  * https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-examples/documentation/src/main/java/io/agentscope/examples/documentation2/harness/workspace/WorkspaceSetupExample.java\[10\]
  * https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-examples/documentation/src/main/java/io/agentscope/examples/documentation2/harness/workspace/WorkspaceLocalShellExample.java\[11\]
  * https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-examples/documentation/src/main/java/io/agentscope/examples/documentation2/harness/workspace/WorkspaceSharedStoreExample.java\[12\]
  * https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-examples/documentation/src/main/java/io/agentscope/examples/documentation2/harness/workspace/WorkspaceSandboxExample.java\[13\]
  * https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-harness/src/main/java/io/agentscope/harness/agent/IsolationScope.java\[14\]
  * https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-harness/src/main/java/io/agentscope/harness/agent/filesystem/spec/LocalFilesystemSpec.java\[15\]
  * https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-harness/src/main/java/io/agentscope/harness/agent/filesystem/spec/SandboxFilesystemSpec.java\[16\]
  * https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-harness/src/main/java/io/agentscope/harness/agent/sandbox/impl/docker/DockerFilesystemSpec.java\[17\]

### 引用链接

\[1\]*https://java.agentscope.io/v2/zh/docs/harness/workspace.html*

\[2\]*https://java.agentscope.io/v2/en/docs/harness/workspace.html*

\[3\]*https://java.agentscope.io/v2/zh/docs/harness/filesystem.html*

\[4\]*https://java.agentscope.io/v2/en/docs/harness/filesystem.html*

\[5\]*https://java.agentscope.io/v2/zh/docs/harness/sandbox.html*

\[6\]*https://java.agentscope.io/v2/en/docs/harness/sandbox.html*

\[7\]*https://java.agentscope.io/v2/en/docs/harness/architecture.html*

\[8\]https://java.agentscope.io/v2/zh/docs/harness/memory.html（下篇预告）:  *https://java.agentscope.io/v2/zh/docs/harness/memory.html%EF%BC%88%E4%B8%8B%E7%AF%87%E9%A2%84%E5%91%8A%EF%BC%89*

\[9\]*https://github.com/agentscope-ai/agentscope-java*

\[10\]*https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-examples/documentation/src/main/java/io/agentscope/examples/documentation2/harness/workspace/WorkspaceSetupExample.java*

\[11\]*https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-examples/documentation/src/main/java/io/agentscope/examples/documentation2/harness/workspace/WorkspaceLocalShellExample.java*

\[12\]*https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-examples/documentation/src/main/java/io/agentscope/examples/documentation2/harness/workspace/WorkspaceSharedStoreExample.java*

\[13\]*https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-examples/documentation/src/main/java/io/agentscope/examples/documentation2/harness/workspace/WorkspaceSandboxExample.java*

\[14\]*https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-harness/src/main/java/io/agentscope/harness/agent/IsolationScope.java*

\[15\]*https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-harness/src/main/java/io/agentscope/harness/agent/filesystem/spec/LocalFilesystemSpec.java*

\[16\]*https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-harness/src/main/java/io/agentscope/harness/agent/filesystem/spec/SandboxFilesystemSpec.java*

\[17\]*https://github.com/agentscope-ai/agentscope-java/blob/v2.0.1/agentscope-harness/src/main/java/io/agentscope/harness/agent/sandbox/impl/docker/DockerFilesystemSpec.java*