---
title: OpenViking 上下文压缩机制详解：从会话到长期记忆的「蒸馏」之路
---

# OpenViking 上下文压缩机制详解：从会话到长期记忆的「蒸馏」之路

> 原文链接：[OpenViking 上下文压缩机制详解：从会话到长期记忆的「蒸馏」之路](https://mp.weixin.qq.com/s?__biz=MzAwMTYwNzE2Mg==&mid=2651037845&idx=1&sn=5c22805786635cd7a14067cd6258788e&chksm=804948438e2527c146075a67efe43234953d3dc295145c93ae4c50e6c844c80fb7ac271d56b8&mpshare=1&scene=1&srcid=0217nJObEZx3bV0iGKa6WG9G&sharer_shareinfo=d6b56749d4e4fbc44a6f7fa8287a39ef&sharer_shareinfo_first=d6b56749d4e4fbc44a6f7fa8287a39ef#rd)

# 片时欢笑且相亲，明日阴晴未定

本文基于 OpenViking 开源项目，详解其如何将会话中的「即时对话」压缩为可检索、可复用的「长期记忆」，并如何与 L0/L1/L2 层级、意图分析与检索形成闭环。适合对 AI 记忆系统、RAG 与上下文管理感兴趣的读者。## 一、为什么需要「上下文压缩」？



在长对话或多轮协作中，原始消息会不断堆积：每一条 user/assistant 消息、每一次工具调用与结果都会占用上下文窗口。若不做任何处理，会出现：

**上下文爆炸**：对话越长，送入模型的 token 越多，成本与延迟上升，且容易超出窗口限制。

**重点被稀释**：真正值得长期保留的信息（用户偏好、关键决策、问题解法）淹没在大量流水式对话里。

**检索难以复用**：未结构化的原始消息不利于按「记忆」「资源」「技能」等维度做检索与去重。

因此，我们需要一种机制：在合适的时机，把「当前这一段会话」做一次「压缩」——既保留可读的归档（便于回溯），又把其中值得长期保留的信息提炼成结构化记忆，写入统一存储并参与后续检索。这就是 OpenViking 的**上下文压缩机制**要解决的问题。## 二、整体架构：压缩在系统中的位置



OpenViking 的架构中，与「上下文」相关的三条主线是：

**上下文检索**（Context Retrieval）：意图分析、检索、Rerank，为当前 query 找到最相关的记忆/资源/技能。

**会话管理**（Session Management）：消息的增删、使用记录、以及**压缩（compress）与提交（commit）**。

**上下文提取**（Context Extraction）：从文档/会话中解析出 L0/L1/L2 层级，构建可检索的上下文树。

压缩机制处在「会话管理」与「上下文提取」的交汇处：

**输入**：当前会话中即将被归档的一批消息（`messages`）。

**输出**：

会话侧：归档目录（含 L0/L1 摘要）、当前会话的 L0/L1 更新；

记忆侧：经「提取 + 去重」后的长期记忆（Context），写入 AGFS 并进入向量化队列。

也就是说：**压缩 = 会话归档 + 长期记忆提取与落库**，并且全程复用 L0/L1/L2 与现有存储（AGFS、向量库）。## 三、触发时机：何时发生一次压缩？



压缩**不会**在每条消息后触发，而是与会话的**提交（commit）**绑定。典型用法如下：

`session = client.session(session_id="chat_001")
session.add_message("user", [TextPart("如何配置 embedding？")])
# ... 多轮对话 ...
session.commit() &nbsp;&nbsp;# 在这里触发一次「压缩」

`

在一次&nbsp;`commit()`&nbsp;调用中，会依次执行：

**归档当前消息**&nbsp; &nbsp;将当前&nbsp;`messages`&nbsp;视为「本段对话」的完整快照，写入会话目录下的&nbsp;`history/archive_{N}/`，并生成该段对话的 L0（`.abstract.md`）与 L1（`.overview.md`）。

**从归档消息中提取长期记忆**&nbsp; &nbsp;把同一批&nbsp;`messages`&nbsp;交给&nbsp;`SessionCompressor`，经「记忆提取 → 去重决策 → 落库 → 向量化」形成新的 Memory 型 Context。

**清空当前消息列表**&nbsp; &nbsp;当前会话的&nbsp;`messages`&nbsp;清空，后续新消息从「新的一段」开始；同时更新当前会话的 L0/L1（`.abstract.md`&nbsp;/&nbsp;`.overview.md`）。

因此，**一次 commit = 一次压缩周期**。业务层可通过「按轮数 / 按 token 数 / 按任务边界」等策略决定何时调用&nbsp;`commit()`，从而控制压缩的粒度与频率。## 四、压缩的两大产出：归档与长期记忆

### 4.1 会话归档（Archive）



每次压缩会生成一个归档目录，例如：

`viking://session/{session_id}/history/archive_001/
├── messages.jsonl &nbsp; &nbsp;# 原始消息（JSONL）
├── .abstract.md &nbsp; &nbsp; &nbsp;# L0：一句话摘要
└── .overview.md &nbsp; &nbsp; &nbsp;# L1：结构化会话摘要

`

**messages.jsonl**：原始对话的完整副本，便于回溯与审计。

**.abstract.md**：由 L0 摘要生成逻辑从「结构化摘要」中抽出一句话，用于快速识别本段对话主题。

**.overview.md**：由&nbsp;**结构化摘要模板**（

**一句话概述**：主题、意图、结果、状态（完成/进行中/待办）。

**Analysis**：按时间线的 2～4 个关键里程碑。

**Primary Request and Intent**：用户核心目标。

**Key Concepts**：关键技术/概念。

**Context References**：引用的 viking:// URI 或外链。

**Errors and Fixes**：问题与解决。

**User Messages**：关键用户原话。

**Pending Tasks / Current Work / Next Step**：未完成任务、当前工作、建议下一步。

也就是说：**每一段被压缩的对话，都拥有一份「L0 + L1」的层级表示**，与 OpenViking 对资源/记忆的 L0/L1/L2 模型一致，便于后续在检索或意图分析时按「摘要/概览」参与上下文选择（例如按 query 筛选最相关的若干 archive 的 overview）。### 4.2 长期记忆提取（Long-term Memory Extraction）



同一批&nbsp;`messages`&nbsp;在归档之外，还会进入&nbsp;**SessionCompressor**&nbsp;的「长期记忆」流水线，产出的是&nbsp;**Memory 类型的 Context**，写入 AGFS 并进入向量索引，供后续检索使用。

核心步骤可以概括为：

**记忆提取**（MemoryExtractor） &nbsp; 用 LLM 对&nbsp;`messages`&nbsp;做一次「哪些内容值得长期保留」的筛选与分类，输出多条**候选记忆**（CandidateMemory），每条都带有：

**类别**（category）：profile / preferences / entities / events / cases / patterns（见下）。

**L0/L1/L2**：abstract（一句话）、overview（结构化概览）、content（完整叙述，L2）。

**去重决策**（MemoryDeduplicator） &nbsp; 对每条候选记忆，先在向量库中按**同类别 + 相似度**做预筛，再通过 LLM 做 CREATE/UPDATE/MERGE/SKIP 决策，避免重复与冗余。

**落库与向量化**&nbsp; &nbsp;对最终要保留的记忆：写入 AGFS（路径按类别与归属 user/agent 划分），并送入向量化队列，生成 embedding 写入向量库；同时可建立与「本段对话中引用的资源/技能」的双向关系。

下面分别展开「六类记忆」与「L0/L1/L2 在记忆上的用法」以及「去重策略」。## 五、六类记忆与 L0/L1/L2



OpenViking 将长期记忆分为&nbsp;**6 类**，并明确其「归属」与「是否可合并」：类别归属含义可合并**profile**user用户身份、静态属性✅**preferences**user用户偏好、习惯✅**entities**user实体（人、项目、组织等）✅**events**user事件、决策、里程碑❌**cases**agent问题 + 解决方案❌**patterns**agent可复用流程、方法✅

**User 记忆**（profile / preferences / entities / events）存放在&nbsp;`viking://user/memories/`&nbsp;下对应子目录；**Agent 记忆**（cases / patterns）存放在&nbsp;`viking://agent/memories/`&nbsp;下。

**profile**&nbsp;特殊处理：内容**追加**到同一文件&nbsp;`viking://user/memories/profile.md`，而不是每条记忆一个文件，便于维护「用户画像」的单一入口。

每一类记忆在提取时都要求具备**三层结构**，与 OpenViking 的 L0/L1/L2 一致：

**abstract（L0）**：索引层，一句纯文本。

可合并类（preferences / entities / profile / patterns）：格式为&nbsp;`[合并键]: [描述]`，例如 &nbsp;&nbsp;`Python 代码风格：无类型注解、简洁直接`。

独立类（events / cases）：直接一句具体描述，例如 &nbsp;`乐队无法识别 → 请用户提供成员/专辑/风格信息`。

**overview（L1）**：结构化概览，带 Markdown 小标题，按类别使用不同模板（如 preferences 用「偏好域 / 具体偏好」，cases 用「问题 / 方案」等）。

**content（L2）**：完整叙述，自由 Markdown，可含背景、时间线、细节。

提取逻辑由&nbsp;**记忆提取模板**（`compression.memory_extraction`）驱动，其中规定了「什么值得记」「什么不值得记」以及每类的判定方式与 few-shot 示例，保证输出既符合六类定义，又符合 L0/L1/L2 的写法规范。## 六、去重机制：向量预筛 + LLM 决策



新抽出的候选记忆若直接全部写入，容易产生大量重复或高度相似的记忆（例如多轮对话中反复提到的同一偏好）。OpenViking 采用&nbsp;**Mem0 风格**&nbsp;的「向量预筛 + LLM 决策」两步去重。### 6.1 向量预筛（MemoryDeduplicator）



对每条候选记忆，用其&nbsp;**abstract + content**&nbsp;生成 embedding，在**同一类别**的已有记忆上做向量检索（例如 top-5）。

仅保留&nbsp;**相似度 ≥ 阈值**（默认 0.7）的已有记忆，作为「相似记忆」列表，供后续 LLM 决策使用。

若没有相似记忆，则直接走&nbsp;**CREATE**，无需调用 LLM。

这样既控制了送入 LLM 的规模，又保证去重只在「语义相近」的同一类别内进行。### 6.2 LLM 去重决策（CREATE / UPDATE / MERGE / SKIP）



在存在相似记忆时，由&nbsp;**去重决策模板**（`compression.dedup_decision`）调用 LLM，对「候选记忆 + 相似记忆列表」做出四类决策：决策含义后续动作**CREATE**与已有记忆均不同，视为全新按新记忆写入 AGFS 并向量化**UPDATE**是对某条已有记忆的补充/更新用 LLM 生成的 merged_content 覆盖/更新该条，再写入并向量化**MERGE**与多条已有记忆相关，需合并用 LLM 生成的 merged_content 作为合并后的 L2，写入新记忆并向量化**SKIP**与已有记忆重复，无新信息不写入，不向量化

LLM 输出的 JSON 中包含&nbsp;`decision`、`reason`&nbsp;以及（在 UPDATE/MERGE 时）`merged_content`。这样，**新记忆与旧记忆在语义上可以合并或更新**，而不是简单「只增不改」，有利于长期记忆的整洁与可复用性。## 七、压缩后的数据流：检索如何使用「压缩结果」



压缩产生的两类结果都会参与后续的检索与意图分析：

**归档的 L0/L1**&nbsp; &nbsp;会话对象提供&nbsp;`get_context_for_search(query)`，会根据当前 query 与各归档的&nbsp;`.overview.md`&nbsp;做相关性筛选（例如关键词匹配 + 时间顺序），选出最相关的若干归档的 overview，与「最近若干条消息」一起，作为**会话上下文的摘要**，传给&nbsp;**IntentAnalyzer**。

**长期记忆**&nbsp; &nbsp;记忆已写入 AGFS 并向量化，在 VikingFS 的&nbsp;`search`&nbsp;中会使用&nbsp;**IntentAnalyzer**&nbsp;基于「会话摘要 + 最近消息 + 当前 query」生成多路&nbsp;**TypedQuery**（memory / resource / skill），再对各路做检索与 Rerank，最终组成 FindResult。

因此，**压缩—归档与记忆—检索**&nbsp;形成闭环：

压缩产出「结构化会话摘要」和「长期记忆」；

检索时用「会话摘要 + 最近消息」做意图分析，再按类型查记忆/资源/技能；

记忆的 L0 参与向量检索，L1 可用于 Rerank 或二次筛选，L2 按需加载。## 八、关键代码与配置入口（便于扩展）



若你希望在自己的分支中调整压缩行为，可重点看以下模块与配置：

**会话层**

`Session.commit()`：触发归档 + 调用&nbsp;`SessionCompressor.extract_long_term_memories(...)`。

`Session.get_context_for_search(query)`：为检索准备「summaries + recent_messages」。

**压缩与记忆**

`SessionCompressor`：协调 MemoryExtractor 与 MemoryDeduplicator，并负责将最终记忆写入 AGFS、入队向量化、建立与资源/技能的关系。

`MemoryExtractor`：调用&nbsp;`compression.memory_extraction`&nbsp;模板，产出 CandidateMemory 列表。

`MemoryDeduplicator`：向量检索 +&nbsp;`compression.dedup_decision`&nbsp;模板，产出 CREATE/UPDATE/MERGE/SKIP 及可选的 merged_content。

**提示模板**（YAML）

`compression.structured_summary`：会话归档的 L1 结构化摘要格式。

`compression.memory_extraction`：六类记忆的判定、L0/L1/L2 写法与 few-shot。

`compression.dedup_decision`：四类去重决策的说明与输出格式。

**存储与向量**

记忆写入 AGFS 的路径由&nbsp;`MemoryExtractor.CATEGORY_DIRS`&nbsp;与 user/agent 归属决定。

向量化通过&nbsp;`VikingDBManager.enqueue_embedding_msg`&nbsp;将 Context 转为 EmbeddingMsg 入队，由异步 pipeline 生成 embedding 并写入向量库。

阈值方面，去重预筛的相似度阈值在&nbsp;`MemoryDeduplicator.SIMILARITY_THRESHOLD`（默认 0.7），可按需要调整。## 九、小结与设计要点



OpenViking 的上下文压缩机制可以概括为：

**时机**：在会话&nbsp;`commit()`&nbsp;时触发，对「当前这一段消息」做一次性的归档 + 长期记忆提取。

**归档**：为这段消息生成 L0/L1（.abstract.md / .overview.md）和原始 messages.jsonl，放入&nbsp;`history/archive_{N}/`，便于回溯和检索时选段。

**记忆**：用 LLM 从同一批消息中提炼「六类」候选记忆（L0/L1/L2），再经向量预筛 + LLM 去重（CREATE/UPDATE/MERGE/SKIP），只保留有价值、不重复的记忆写入 AGFS 并向量化。

**闭环**：压缩产出的「会话摘要」与「长期记忆」都会参与后续的意图分析与多路检索，使「说过的话」真正变成「可被检索、可被复用」的上下文。

若你正在做 AI 记忆、会话摘要或 RAG 系统，希望把「对话」和「知识库」打通，OpenViking 的这套「归档 + 六类记忆 + 去重 + L0/L1/L2」的设计，可以直接作为实现与二次开发的参考。更多实现细节可参阅项目中的&nbsp;`session`、`compressor`、`memory_extractor`、`memory_deduplicator`&nbsp;及&nbsp;`compression`&nbsp;下各 YAML 模板。

*本文基于 OpenViking 开源代码与文档整理，如有更新以仓库为准。*


