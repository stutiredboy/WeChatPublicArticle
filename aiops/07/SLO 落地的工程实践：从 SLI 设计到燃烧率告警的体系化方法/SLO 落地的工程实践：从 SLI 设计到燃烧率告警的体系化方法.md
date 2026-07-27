---
title: SLO 落地的工程实践：从 SLI 设计到燃烧率告警的体系化方法
date: 2026-07-20
source: https://mp.weixin.qq.com/s/SQCxQ59HBxOAcmhSuXeCjg
images: 0
---


* * *

  

> !! 大家好，我是乔克，一个爱折腾的运维工程，一个睡觉都被自己丑醒的云原生爱好者。
> 
> * * *
> 
> 作者：乔克  
> 公众号：运维开发故事  
> 博客：https://jokerbai.com
> 
> * * *

  

> **导读** ：本文从工程化视角系统梳理 SLO 落地的四个核心组件——SLI 设计、错误预算、燃烧率告警、分阶段实施路径，并给出可直接投产的 Prometheus 告警规则、Grafana 面板配置和 6 个月分阶段实施方法论。文章不是教科书式的概念复述，而是基于一线 SRE 团队的实践复盘，重点解决三个工程难题：SLI 选型的常见陷阱、告警噪音与漏报的平衡、组织落地路径的可行性。适合正在规模化推进 SLO 体系的 SRE / 后端架构师 / 平台工程师阅读。

* * *

## 一、问题的本质：SLO 不是更准的指标，是更可决策的体系

在大量 SRE 落地案例中，我们观察到一个普遍现象：团队花费数月搭建 SLI 采集、Grafana 大屏、告警规则，但最终的 SLO 大屏只在大老板参观时打开，开发和运维同学每天看的还是"CPU 利用率超过 80%"这种传统告警。

这种现象的本质，是团队把 SLO 当作**展示型指标** 而非**决策型体系** 。

真正落地 SLO 的标志，不是"画出了一个 99.9% 的可用性大屏"，而是：

  1. 团队能回答"这个月还能不能发版"
  2. 告警能区分"慢性病消耗"和"突发故障"
  3. 业务方能理解"错误预算"的概念并据此做权衡

本文围绕这三个目标展开。

## 二、概念边界：SLA、SLO、SLI 的工程化区分

概念| 全称| 性质| 工程意义  
---|---|---|---  
**SLA**|  Service Level Agreement| 法律/商业合同| 触发条件时承担商务赔付  
**SLO**|  Service Level Objective| 内部目标| 团队对可靠性的承诺基线  
**SLI**|  Service Level Indicator| 度量指标| 具体的可观测数据点  
  
工程上必须严守的边界：

  * **SLO 必须严于 SLA** ：通常缓冲区至少 0.05%。如果 SLA = 99.9%，SLO 通常定在 99.95% 或更高，避免每次小故障都触及商务合同。
  * **SLI 必须用户可感知** ：拿 `up` 指标当 SLI 是反模式。`up=1` 只表示进程活着，不代表服务在按预期工作。
  * **SLO 必须可决策** ：一个不能驱动"是否发版""是否限流""是否回滚"的 SLO，等于没落地。

## 三、SLI 设计：SLO 落地 90% 的难度集中在这一层

### 3.1 SLI 的工程化定义

任何 SLI 都可形式化为：
    
    
    SLI = good_events / total_events  
    

或等价的：
    
    
    SLI = 1 - bad_events / total_events  
    

这个公式的工程价值在于：**SLI 必须是事件级** ，而非聚合级。基于这个原则，可以直接判断一个 SLI 是否合规。

### 3.2 四类 SLI 的选型矩阵

基于 Google SRE 的 Four Golden Signals 投影：

SLI 类型| 衡量维度| 典型 good 定义| 适用场景  
---|---|---|---  
**延迟 Latency**|  响应速度| 请求耗时 < SLO 阈值的比例| 用户感知敏感型服务  
**流量 Traffic**|  服务繁忙度| （通常作为 SLI 分母而非 SLI 本身）| —  
**错误 Errors**|  服务正确性| 非 5xx 响应占比| API 类服务  
**饱和度 Saturation**|  资源压力| 关键资源利用率 < 阈值| 资源瓶颈型服务  
  
> **工程经验** ：流量是 SLI 的分母而非 SLI 本身。这是新手最常踩的坑——把 QPS 当 SLI，导致"用户变少可用性反而上升"这种荒谬结果。

### 3.3 SLI 设计的工程实战：支付服务案例

以一个支付服务 `payment-api` 为例，演示三组 SLI 的工程化设计。

**SLI-1：可用性（错误率 SLI）**
    
    
     # good: 非 5xx 请求数  
    sum(rate(http_requests_total{job="payment-api", code!~"5.."}[5m]))  
    # total: 所有请求数  
    sum(rate(http_requests_total{job="payment-api"}[5m]))  
    

**关键工程约束** ：4xx 不算错误。客户端传错参数返回 400 是预期行为，不能算服务不可用。

**SLI-2：延迟（事件级 SLI）**

工程上推荐使用事件级 SLI，而非 P99：
    
    
    # good: 耗时 < 500ms 的请求数  
    sum(rate(http_request_duration_seconds_bucket{job="payment-api", le="0.5"}[5m]))  
    # total: 所有请求  
    sum(rate(http_request_duration_seconds_bucket{job="payment-api", le="+Inf"}[5m]))  
    

工程价值：事件级 SLI 直接符合 `good/total` 公式，便于后续做燃烧率告警。

**SLI-3：饱和度（次要但重要）**

支付服务强依赖数据库，DB 连接池饱和度是关键：
    
    
    1 - (db_connections_active / db_connections_max)  
    

### 3.4 SLI 设计的 7 类反模式

反模式| 问题描述| 工程解法  
---|---|---  
**聚合指标当 SLI**|  拿 `avg latency` 当 SLI，长尾被平均| 用分桶事件计数  
**不区分用户维度**|  管理员请求和用户请求混合计算| 按 label 区分关键路径  
**依赖系统内部指标**|  拿 `up`、CPU 当 SLI| 用用户可感知的指标  
**告警阈值当 SLO**|  "CPU > 80% 告警"误等同 SLO| 区分阈值告警与 SLO 告警  
**SLI 与业务无关**|  支付服务却监控 CPU| 监控"支付成功率"等业务指标  
**SLI 过多**|  一个服务 10 个 SLI| 一个服务最多 3 个 SLI  
**SLI 长期不复核**|  业务形态变了 SLI 没变| 季度 SLO 复盘会  
  
## 四、错误预算：把可靠性货币化

### 4.1 错误预算的数学定义
    
    
    错误预算 = 1 - SLO  
    

例：SLO = 99.9%，错误预算 = 0.1%。

换算为时间窗口下的可消费额度：

时间窗口| 错误预算（99.9% SLO）  
---|---  
1 个月| 43.2 分钟不可用  
1 周| 10.08 分钟不可用  
1 天| 1.44 分钟不可用  
  
### 4.2 错误预算的三种消耗模式

理解错误预算的关键是识别三种截然不同的消耗模式：

  * **稳态消耗** ：正常业务波动，月头 43 分钟预算到月尾正好花完。健康状态。
  * **慢性病消耗** ：消耗曲线明显高于稳态但未触发告警。最危险——团队感觉没事，实际透支。
  * **突发消耗** ：一次大故障 10 分钟烧光整月预算。最容易感知但最难预防。

燃烧率告警（下一节）专门解决慢性病和突发消耗的检测问题。

### 4.3 错误预算的工程化运营策略

预算剩余| 团队动作| 工程意义  
---|---|---  
**≥ 50%**|  正常发版，鼓励快速迭代| 释放迭代速度  
**25%-50%**|  只允许修复型发布| 降低风险敞口  
**< 25%**| 冻结非紧急发布| 全员聚焦稳定性  
**耗尽（负数）**|  强制熔断，仅允许 P0 修复| 优先恢复可靠性  
  
**关键工程价值** ：把"是否还能发版"从主观决策变成可计算规则。这是 SLO 体系能被业务方接受的核心原因。

### 4.4 算账案例

支付服务某月 SLO = 99.9%，错误预算 = 43.2 分钟。月中宕机 12 分钟：
    
    
    剩余预算占比 = (43.2 - 12) / 43.2 = 72%  → 正常发版  
    

如再宕 12 分钟：
    
    
    剩余占比 = 19.2 / 43.2 = 44%  → 仅修复型发布  
    

## 五、燃烧率告警：SLO 体系的实时防御层

### 5.1 传统告警的工程缺陷

最直觉的告警方式：`error_rate > 0.01`。工程上有两个致命缺陷：

  1. **慢故障不告警** ：慢性病消耗持续一周烧光预算，但错误率一直在 0.5%-0.8% 之间，永远不触发告警。
  2. **瞬时抖动狂告警** ：GC 停顿导致错误率瞬间飙到 5%，触发告警，30 秒后恢复，值班同学半夜被叫醒。

### 5.2 燃烧率的工程定义
    
    
    燃烧率 = 当前错误率 / SLO 容许错误率  
    

例：SLO = 99.9%，容许错误率 = 0.1%。当前 1 小时错误率 = 1%，燃烧率 = 1% / 0.1% = 10。

工程含义：按当前速度，2.88 小时烧光整月错误预算。
    
    
    # 1 小时窗口的燃烧率  
    (  
      sum(rate(http_requests_total{job="payment-api", code=~"5.."}[1h]))  
      /  
      sum(rate(http_requests_total{job="payment-api"}[1h]))  
    ) / 0.001  
    

### 5.3 多窗口燃烧率：Google SRE 的关键设计

单一窗口解决不了"快速告警 vs 误报"的工程矛盾。Google SRE 的解法是**双窗口燃烧率** ：

告警级别| 长窗口| 短窗口| 燃烧率阈值| 触发含义  
---|---|---|---|---  
**Page**|  1h| 5m| 14.4| 2% 预算 1h 烧光  
**Page**|  6h| 30m| 6| 5% 预算 6h 烧光  
**Ticket**|  3d| 6h| 1| 10% 预算 3d 烧光  
**Ticket**|  1d| 2h| 3| 10% 预算 1d 烧光  
  
**工程价值** ：长窗口管"会不会真烧光"，短窗口管"是不是当前真的在烧"。两个条件同时满足才告警——既不漏报慢性病，也不会被瞬时抖动误触。

### 5.4 可投产的 Prometheus 告警规则
    
    
    groups:  
    -name:slo-burn-rate  
    interval:30s  
    rules:  
    -alert:HighErrorRateFastBurn  
        expr:|  
          (  
            sum(rate(http_requests_total{job="payment-api", code=~"5.."}[5m]))  
            /  
            sum(rate(http_requests_total{job="payment-api"}[5m]))  
          ) > (14.4 * 0.001)  
          and  
          (  
            sum(rate(http_requests_total{job="payment-api", code=~"5.."}[1h]))  
            /  
            sum(rate(http_requests_total{job="payment-api"}[1h]))  
          ) > (14.4 * 0.001)  
        for:2m  
        labels:  
          severity:page  
          service:payment-api  
          slo:availability  
        annotations:  
          summary:"payment-api 燃烧率告警（1h/5m 双窗口）"  
          description:"1h 和 5m 窗口错误率均超 14.4×，预计 1 小时内烧光 2% 月度预算"  
      
    -alert:HighErrorRateSlowBurn  
        expr:|  
          (  
            sum(rate(http_requests_total{job="payment-api", code=~"5.."}[30m]))  
            /  
            sum(rate(http_requests_total{job="payment-api"}[30m]))  
          ) > (6 * 0.001)  
          and  
          (  
            sum(rate(http_requests_total{job="payment-api", code=~"5.."}[6h]))  
            /  
            sum(rate(http_requests_total{job="payment-api"}[6h]))  
          ) > (6 * 0.001)  
        for:15m  
        labels:  
          severity:page  
          service:payment-api  
          slo:availability  
        annotations:  
          summary:"payment-api 燃烧率告警（6h/30m 双窗口）"  
          description:"6h 和 30m 窗口错误率均超 6×，预计 6 小时烧光 5% 月度预算"  
      
    -alert:SlowBurnBudgetDrain  
        expr:|  
          (  
            sum(rate(http_requests_total{job="payment-api", code=~"5.."}[6h]))  
            /  
            sum(rate(http_requests_total{job="payment-api"}[6h]))  
          ) > (1 * 0.001)  
          and  
          (  
            sum(rate(http_requests_total{job="payment-api", code=~"5.."}[3d]))  
            /  
            sum(rate(http_requests_total{job="payment-api"}[3d]))  
          ) > (1 * 0.001)  
        for:1h  
        labels:  
          severity:ticket  
          service:payment-api  
          slo:availability  
        annotations:  
          summary:"payment-api 慢性预算消耗"  
          description:"3 天错误率持续超 SLO 容许值，预计 3 天烧光 10% 月度预算"  
    

**工程备注** ：Sloth 和 Pyrra 等开源工具可以基于 SLO 定义自动生成上述规则，避免手工维护带来的错误。

### 5.5 工程实测数据

某团队落地双窗口燃烧率告警后，6 个月对比数据：

指标| 落地前| 落地后| 变化  
---|---|---|---  
月告警条数| 187| 71| -62%  
误报率| 41%| 8%| -33%  
平均响应时长| 18 分钟| 6 分钟| -67%  
漏报（事后发现的故障）| 3 次/月| 0 次/月| -100%  
  
**关键洞察** ：告警条数下降不是核心价值，漏报归零才是。漏报归零意味着所有重大故障都在用户感知前被发现。

## 六、6 个月分阶段实施方法论

最常见的失败模式——开会决定"全公司落地 SLO"，3 个月过后只剩 PPT。正确做法是**单点突破 → 流程沉淀 → 横向复制** 。

### M1：单服务试点

**目标** ：跑通流程，不求完美。

  * 选 1 个"足够重要但不大"的服务（建议选核心链路上的非入口服务）
  * 定 1-2 个 SLI，1 个 SLO 目标（如 99.9% 可用性）
  * 把 SLO 数字画在大屏上，**先不管告警**
  * 工具栈：Prometheus + Grafana 即可

**验收标准** ：团队所有人都知道这个服务当前的 SLI 和剩余预算。

### M2-M3：错误预算与运营动作

**目标** ：让 SLO 进入决策流程。

  * 接入错误预算计算（Grafana 画一个"错误预算余额"面板）
  * 制定错误预算策略表，并由 Tech Lead 签字背书
  * 每周一同步：本周消耗、剩余、是否进入限发状态

**验收标准** ：发生过至少 1 次"因预算耗尽而暂停发布"的真实案例。

### M4-M5：燃烧率告警接入

**目标** ：从算账工具升级为防御系统。

  * 接入双窗口燃烧率告警规则
  * 配置告警路由：Page → 电话/IM；Ticket → 工单
  * 跑 1 个月灰度期——只观察不通知
  * 灰度期结束后正式启用

**验收标准** ：告警噪音下降 ≥ 50%，漏报为 0。

### M6：横向复制与文化建设

**目标** ：从 1 个服务扩展到 3-5 个，形成团队文化。

  * 把 M1-M5 流程沉淀成"X 团队 SLO 落地手册"
  * 选 2-3 个新服务复制流程
  * 每季度办一次"错误预算回顾会"
  * 引入"错误预算金/银/铜牌"激励机制

**验收标准** ：3 个服务都进入正常运营状态，错误预算策略被业务方理解并接受。

### 反例：跳过试点的代价

某团队跳过试点，直接给 80 个服务铺 SLO。3 个月后：

  * 80 个服务里只有 12 个 SLI 选对了
  * 错误预算面板没人看
  * 告警被全员屏蔽
  * SLO 大屏只在大老板参观时打开

**结论** ：永远不要低估"团队接受度"的工程难度。技术可以复制，文化不能。

## 七、10 类常见工程陷阱

陷阱| 影响| 工程解法  
---|---|---  
SLI 定得太宽| 用户已骂街，告警未响| 以业务可接受度为基准  
SLI 定得太严| 预算永远耗尽，团队放弃| 留 0.05% 缓冲  
把 SLA 当 SLO| 没有缓冲区| SLO 至少严于 SLA 0.05%  
只看月度窗口| 慢性病消耗看不见| 多窗口燃烧率告警  
告警用绝对错误率| 误报和漏报双高| 用燃烧率  
不区分关键路径| 管理后台和支付链路同 SLO| 按 label 区分  
SLO 不随业务变化| 大促期间用日常 SLO| 季度复核  
没有错误预算运营动作| 预算耗尽仍发版| 强制策略表  
告警只接 IM| 半夜无人看| Page 走电话  
SLO 一年不复盘| SLI 与业务脱节| 季度复盘会  
  
## 八、工程化配置包

### 8.1 Grafana 错误预算面板 JSON 模板
    
    
    {  
      "title": "Payment API - SLO Dashboard",  
    "panels": [  
        {  
          "title": "SLI（28天可用性）",  
          "type": "stat",  
          "targets": [{  
            "expr": "1 - (sum(rate(http_requests_total{job=\"payment-api\", code=~\"5..\"}[28d])) / sum(rate(http_requests_total{job=\"payment-api\"}[28d])))"  
          }]  
        },  
        {  
          "title": "错误预算余额（百分比）",  
          "type": "gauge",  
          "targets": [{  
            "expr": "100 * (1 - (sum(rate(http_requests_total{job=\"payment-api\", code=~\"5..\"}[28d])) / sum(rate(http_requests_total{job=\"payment-api\"}[28d]))) / 0.001)"  
          }]  
        },  
        {  
          "title": "燃烧率（1h）",  
          "type": "stat",  
          "targets": [{  
            "expr": "(sum(rate(http_requests_total{job=\"payment-api\", code=~\"5..\"}[1h])) / sum(rate(http_requests_total{job=\"payment-api\"}[1h]))) / 0.001"  
          }]  
        }  
      ]  
    }  
    

### 8.2 PromQL 工程速查表

用途| PromQL  
---|---  
当前 SLI（28天）| `1 - sum(rate(http_requests_total{code=~"5.."}[28d])) / sum(rate(http_requests_total[28d]))`  
错误预算余额| `100 * (1 - error_rate / slo_error_budget) * 100`  
1h 燃烧率| `error_rate[1h] / slo_error_budget`  
5m 燃烧率| `error_rate[5m] / slo_error_budget`  
预计耗尽时间| `error_budget_remaining / current_burn_rate`  
  
### 8.3 推荐工具栈

阶段| 工具| 工程作用  
---|---|---  
SLI 采集| Prometheus + OpenTelemetry| 指标采集  
SLI 可视化| Grafana| 大屏  
SLO 自动生成| Pyrra / Sloth| 自动生成告警规则  
错误预算计算| Sloth + Prometheus| 自动计算预算余额  
告警路由| Alertmanager + OnCall 工具| 告警分发  
  
## 九、组织落地路径总结

落地 SLO 第一年，团队通常会经历三个阶段：

  1. **抗拒期（1-3 个月）** ："为什么要搞这些，告警已经够多了"
  2. **震荡期（3-6 个月）** ："好像有点用，但告警还是乱"
  3. **依赖期（6 个月以后）** ："这次故障 SLO 告警提前 30 分钟发现了"

进入依赖期的标志，是团队不再讨论"我们的可用性是多少"，而是讨论"我们的错误预算还能花多少"。这一刻起，SLO 从工具转变为团队的思维方式。

* * *

## 关于作者

本文是「可观测性集群」Pillar Page 系列的开篇，后续会持续扩展以下子主题：

  * **SLI 设计专题** ：微服务 SLI 选型矩阵、延迟 SLI 陷阱、业务 SLI vs 技术 SLI
  * **错误预算专题** ：3 种高级运营策略、大促期间预算管理、破例机制
  * **燃烧率告警专题** ：多窗口变体、Sloth/Pyrra 工程化、噪音治理
  * **可观测性三支柱** ：Metrics/Logs/Traces 在 SLO 中的角色分工
  * **告警工程** ：告警分级边界、告警 SLO、静默与抑制规则
  * **混沌工程** ：用混沌实验验证 SLO 可行性、Game Day 实践

  

  

最后，求关注。如果你还想看更多优质原创文章，欢迎关注我们的公众号「**运维开发故事** 」。  

如果我的文章对你有所帮助，还请帮忙**点赞、在看、转发** 一下，你的支持会激励我输出更高质量的文章，非常感谢！

你还可以把我的公众号设为「**星标** 」，这样当公众号文章更新时，你会在第一时间收到推送消息，避免错过我的文章更新。

  

* * *

  

我是 乔克，《运维开发故事》公众号团队中的一员，一线运维农民工，云原生实践者，这里不仅有硬核的技术干货，还有我们对技术的思考和感悟，欢迎关注我们的公众号，期待和你一起成长！