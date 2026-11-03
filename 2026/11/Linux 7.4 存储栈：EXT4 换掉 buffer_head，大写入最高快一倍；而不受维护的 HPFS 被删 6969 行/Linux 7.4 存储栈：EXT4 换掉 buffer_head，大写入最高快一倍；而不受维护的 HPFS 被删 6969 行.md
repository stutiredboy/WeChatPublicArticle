---
title: Linux 7.4 存储栈：EXT4 换掉 buffer_head，大写入最高快一倍；而不受维护的 HPFS 被删 6969 行
date: 2026-11-03
source: https://mp.weixin.qq.com/s/vozH9gjxTfXGTWkFwVXIoA
images: 0
---

QUOTE

它不是「新换旧」，是「新路先修好，旧路再拆掉」。

本文对 Linux 7.4 存储栈两条相反方向变化的归纳

**同一个 Linux 7.4 合并窗口里，存储栈朝两个相反方向同时动了。****往前的那个：EXT4 把常规文件的缓冲 I/O 从 buffer\_head 换成 iomap，华为 Zhang Yi 给出的 FIO 数据里，大写入场景最高 +105%。****往后的那个：HPFS —— IBM 和微软为 OS/2 开发的文件系统 —— 被一个补丁整块删除，6969 行、23 个文件。****而这两件事其实是同一件事的两面：内核存储栈正在把 1990 年代的设计替换掉，方式是「让新的先可选、旧的先出局」。**

本文看点

01

iomap 是什么

02

性能全表

03

为何默认不开

04

HPFS 出局

05

其他三条线

06

怎么用

01

THE SWAP

### EXT4 到底换了什么：buffer\_head vs iomap

**先把两个概念说清楚，因为整篇文章的重量都压在这里。**

**「IOmap 是 Linux 中把文件偏移映射到设备块的现代框架，比旧的 buffer\_head 方式更高效，和 folio 集成得更好，同时也没有 buffer head 那部分高昂的内存开销。」**

·

**buffer\_head （旧）**：把「文件偏移 → 设备块」的映射结果包在一个 struct buffer\_head 里 —— 多一层结构，每个都有固定开销

·

**iomap （新）**：把映射直接表达成「一个设备范围 + 一个逻辑块偏移」的描述 —— 原生集成 folio，不需要中间结构

⭐ 而这里有一个关键的历史包袱

**「hpfs 使用 buffer\_heads，它们无法很好地处理块大小 > PAGE\_SIZE 的情况。没有这个修复，挂载时会命中 folio\_set\_bh 里第一次 \_\_bread\_gfp 调用上的 BUG\_ON\(offset >= folio\_size\(folio\)\);。」**

**——这正是 HPFS 那个 CVE-2026-97486 的成因。****也就是说： buffer\_head 这个抽象已经老到会在现代 folio 语义下直接踩 BUG\_ON 的程度。****一个为 OS/2 写的文件系统，在 2026 年会因为「块大小超过 PAGE\_SIZE」这种基础假设而在挂载时直接崩掉。****这就是「整块删除」这条新闻的真正技术底色：不是「有人不喜欢 HPFS」，是「HPFS 依赖的那个抽象本身已经站不住了」。**

  

02

THE NUMBERS

### 官方给出的性能数据：全表

**我回读了 v6 cover letter 里的完整 FIO 表（上游原文，非二手报道）。环境：4 核虚拟机，Xeon Platinum 8380，150GB RAM-backed virtual-io。**

⭐ 最刺眼的一组

·

**RWF\_DONTCACHE （绕过 page cache 直接写设备）**：1m 块 **1404 → 2883（+105%）** ；4k 块 **67.9 → 61.9（-9%）**

·

**只写 page cache 不回写** ：1m 块 **4295 → 5780（+35%）**

·

**触发回写** ：64k 块 **734 → 957（+30%）**

·

**唯一系统性退化的场景： fsync\(\) 密集的小写入** —— 1k **-15%** 、4k **-7%**

**作者自己的总结：「大 I/O 场景显示显著的写性能提升，而小 I/O 在同步和非缓存场景下有轻微回退。读性能没有显著差异。」**

⭐ 把表读透，我看到三件事

**① 「显著提升」的真正条件是「块尺寸够大」。****所有正收益几乎都在 64k 和 1m 上 —— 而 64 KiB 是 max\_sectors\_kb 常见上限附近，1 MiB 是现代 NVMe 单次 I/O 的典型规模。****这正是大文件顺序写（复制大视频、tar 解包、容器镜像导入）的形态。****所以结论是：写大文件会变快，变小文件批量写不会。**

**② 同一个配置项，仅块尺寸从 4k 变成 1m，收益就从「倒退 9%」翻到「翻倍」。****而 RWF\_DONTCACHE 正是现代 LSM 树数据库和 NVMe 直写场景的常用标志 —— 这类工作负载上 iomap 的价值比普通大文件顺序写要大得多。**

**⚠️ 4k 退化 -9% 的原因，cover letter 没有解释。****我的推测（未经验证）：小尺寸下 iomap 地址空间操作的建立/销毁开销占比更高，而每次 I/O 实际数据量太小，摊不薄。****这是一个诚实的空白，值得上游继续查。**

  

03

WHY OPT-IN

### 为什么默认不开：不只是「还没写完」

**「这不默认启用，需要 buffered\_iomap 挂载选项，因为这个模式不支持在线碎片整理、内联数据、fsverify、fscrypt、非 extent inode 和 data=journal 模式。如果启用了 buffered\_iomap，ext4 会在必要时自动回落到原来的 I/O 代码路径。启用 buffered iomap 后，大写入显示显著的性能提升。」**

·

**online defragmentation** （在线碎片整理）：中等 —— 可靠 fstrim / 定期重建代替

·

**inline data** （内联数据）：低 —— 属于优化特性

·

**fsverify** ：中等偏高 —— 调试/取证场景受限

·

**fscrypt** ：**高** —— 大量企业部署依赖它

·

**non-extent inodes** ：低 —— 现代 ext4 很少产生

·

**data=journal 模式**：**高** —— 极端安全场景会依赖

**而「会自动回落」这句是关键的可用性保证：你可以在不逐个检查特性的情况下直接加这个 mount option，遇到不支持的场景会自动退回老路径。这大幅降低了「开错」的代价。**

⭐ 但有一个更隐蔽的代价：data=ordered 也不能用了

**「1. 锁顺序差异 —— folio 锁和事务开始的锁顺序在 iomap 路径中与 buffer\_head 路径相反。****2\. 不使用 data=ordered 模式 —— 两个主要原因：a\) data=ordered 模式下 folio 锁和事务开始的锁顺序与 iomap 路径相反，会导致死锁；b\) iomap 回写路径不支持部分 folio 提交。」**

**data=ordered 是 ext4 的默认模式，它保证：写按序到达设备，但数据块先于元数据块落盘。****这个保证的用途是：即使掉电，也不会出现「元数据说这个块有效，但数据是旧的」这种不一致。**

**⚠️ 技术细节要讲清楚，避免过度解读：这个降级是按 inode 生效的（有专门的状态位和 tracepoint），不是整个文件系统一刀切。而且这是「用持久性换吞吐」的显式选择，不是 bug。**

  

04

HPFS

### HPFS 被删：6969 行、23 个文件

**这条比 EXT4 短，但信息量在「理由」而不是「动作」里。**

**作者是 Breno Rodrigues Alves，收件人抄送了 linux-fsdevel、linux-kernel，以及 Mikulas Patocka（红帽）和 Alexander Viro —— 这不是无名小卒的随手提交。**

**「HPFS 文件系统驱动早已被孤立、长期无人维护。linux-fsdevel 上的一封 RFC 指出 HPFS 即将被移除，因为它没有剩余用户，且在 SMP 或 PREEMPT 内核上已不再被支持。近期的漏洞（例如 CVE-2026-97486）进一步凸显了缺乏维护的问题。」**

·

**「在 SMP 或 PREEMPT 内核上已不再被支持」—— 这才是致命的** ：现代 Linux 早没有单处理器配置了，所以它实际上已经不能工作

·

**CVE-2026-97486 加持** ：那个 BUG\_ON\(offset >= folio\_size\(folio\)\) 的崩溃

·

**HPFS\_SUPER\_MAGIC 保留**：**userspace ABI 兼容性 —— 老工具里硬编码的 magic number 不变**

·

**defconfig 清理另行发送** ：所以你可能某个版本突然发现 HPFS 不在 Kconfig 里了

**⭐ 一个有意思的注脚：删的是 HPFS，留的是 magic number。****这是典型的、只有内核开发者才会关心的细节 —— 删代码和不断 ABI 之间的分寸。**

⭐ 而同时被删的另一个：BFS

**「这移除了 bfs，UnixWare 用于其引导分区的文件系统。它只支持连续文件且没有子目录。这种分区上唯一的数据是内核和引导程序设置，所以没有理由再从 Linux 访问它。uapi 头保留。」** —— Christian Brauner

**把两个删除放在一起，是 Linux 内核 2026 年的一段缩影：**

·

**HPFS** ：IBM + 微软，为 OS/2，约 1989 年起，6969 行

·

**BFS** ：SCO，为 UnixWare，1990 年代末，1.2k 行

·

**两个 uapi 头都保留了**

**而关于 SCO 那一段历史，本号此前写过《Unix 为什么会分裂成两个阵营》和《商业 Unix 只剩一个还在开发》—— BFS 的删除，其实是那段诉讼史在代码里的最后一块残片被清掉。**

  

05

OTHER LINES

### 同窗口里其他三条存储线

⭐ XFS 校验和：从「每次都拷贝」改成「出错才拷贝」

**「主体是对带校验和的读做惰性 bounce 缓冲。XFS 会为每次 direct read 做 bounce 缓冲，因为设备需要 stable pages 来做校验和，这样用户空间在读飞行期间修改缓冲区就无法破坏数据并让校验和失败。这烧掉了 DRAM 带宽和 CPU，而绝大多数时候根本不需要这些拷贝；而且因为 bounce buffer 是 bio\_vec，用 4k 页产生的 I/O 更小且不对齐，也就是 1 MB 减去 4k。现在读先直接进用户缓冲区，只有校验和失败才分配 bounce buffer 并重读。完整性验证从 iomap 移到文件系统里，这样它可以按自己的方式处理错误。」**

**这修掉了一个隐藏缺陷：因为 bounce buffer 是 bio\_vec，用 4k 页拼出的 1MB 其实是「1MB 减去 4k」，既小一点又不对齐 —— 所以每次带校验和的 direct read，I/O 都是碎的。****这是典型的「为了一个几乎不发生的场景，付出每次都付的代价」的设计，被改成了「先乐观，出事再悲观」。**

XFS 本身：这一轮基本是修 bug

**「主体是 bug 修复、清理和代码重构，很多很多。大部分 bug 修复针对 scrub 和在线修复代码。这里没有真正的新特性，只有大量为未来工作准备的代码。也有一些小的性能优化，但都不大。」** —— Carlos Maiolino

Btrfs：三个具体的小改进

·

**Zstd 解压快约 8 MB/s**

·

**降低 inode extent map 锁争用** —— shrinker 处理无 extent map 的 inode 时**耗时减少 10–20%**

·

**reflink 速度提升** （重排锁和 flush）

Block 层：从软驱到 Apple M4

**旧的一侧** ：软盘驱动修了 KASan 报的栈越界，以及一个**可以追溯到 2017 年代码重构的回归** ；**还有若干数据竞争，被「我们自己的工具」找出** （Phoronix 委婉地写：presumably are around AI tooling）。

**新的一侧** ：**Apple M4 T8132 ANS2 NVMe 支持** 被合入。

**⭐ 而中间还有一个动人的细节：SWIM（Sander Woz Integrated Machine）驱动 —— 老 Apple Macintosh 的软盘控制器 —— 的修复来自 Linux m68k 社区的 Finn Thain，缘于他最近需要用到这个驱动，却发现它「bug 多到没用」。共处理 33 个修复，在 Mac Quadra 650、Mac LC III、Mac Quadra 700 和 Mac IIvx 上成功测试。****一个 1990 年代 Macintosh 的软驱驱动，在 2026 年被一个 m68k 社区的人救活了，而且是在真实硬件上测的。****这和 HPFS 被删放在一起，是同一条曲线的两端：一个太偏门所以出局，一个够偏门但还有人真在用所以留下。**

  

06

HOW TO USE

### 怎么用，以及值不值得开

EXT4：三个使用前提

·

**文件系统没有用 data=journal**（data=ordered 是默认，会被自动降级）

·

**没有依赖 fscrypt** （加密文件系统直接不支持）

·

**能接受「小 I/O 密集 + fsync 密集」场景可能变慢 7–15%**

**开启方式** ：sudo mount -o remount,buffered\_iomap /mnt **关闭** ：sudo mount -o remount,nobuffered\_iomap /mnt

⭐ 我的实际建议

·

**开发机 / 大文件下载解压 / 容器镜像导入** → **值得开** —— 这正是收益最大的场景

·

**CI 跑构建、跑测试** → **值得试** —— 收益大且数据可重生成

·

**数据库服务器（WAL / LSM 树）** → **谨慎** —— DONTCACHE + 大 I/O 收益最大，但持久性语义有变化

·

**备份盘 / 归档存储** → **别开** —— 收益小、风险不对称

·

**fscrypt 加密卷** → **不能开**

·

**data=journal 卷** → **不能开**

**⭐ 而最重要的一句是：因为默认不开、且不支持时会自动回落，所以「先在非关键卷上试一个下午」几乎没有风险。****这才是这个特性值得关注的真正原因 —— 它不是「你必须升级」，而是「你可以试」。**

HPFS / BFS：不需要做任何事

**除非你真的在挂载 OS/2 或 UnixWare 分区 —— 而那种场景在 2026 年基本只存在于博物馆和怀旧用途。**

  

14

KEY FACTS

### 关键事实速查

KEY FACTS

项目| 内容  
---|---  
EXT4 新路径| **buffered I/O 从 buffer\_head 换成 iomap，31 个补丁，⭐ 默认关闭（opt-in）**  
性能（DONTCACHE 1m）| **⭐ 1404 → 2883 MiB/s，+105%**  
性能（DONTCACHE 4k）| **⚠️ 67.9 → 61.9，-9%（原因上游未解释）**  
性能（fsync 密集小写）| **⚠️ 1k -15%、4k -7% —— 唯一系统性退化的场景**  
读性能| **无显著差异（热读 ±3% 以内）**  
不支持的特性| **在线碎片整理、内联数据、fsverify、fscrypt、非 extent inode、 data=journal**  
⭐ 隐蔽代价| **data=ordered 不可用（按 inode 降级）—— 掉电持久性保证弱于默认 ext4**  
回落机制| **✅ 不支持时自动回落到老路径，所以「试一下」几乎无风险**  
HPFS| **⭐ IBM + 微软为 OS/2 开发，6969 行 / 23 文件被整块删除**  
HPFS 致命理由| **在 SMP / PREEMPT 内核上早已不可用；CVE-2026-97486**  
同窗口另一个| **BFS（UnixWare 引导分区）1.2k 行被删；⭐ 两个 uapi 头都保留**  
XFS 校验和| **⭐ 从「每次 direct read 都拷贝」改成「校验失败才拷贝重读」**  
Btrfs| **Zstd 解压 +8MB/s；shrinker 耗时 -10~20%；reflink 提速**  
Block 层| **软驱修复（含 2017 年回归）、SWIM 老 Mac 软驱 33 个修复、Apple M4 NVMe**  
  

同一个 7.4 窗口里，EXT4 把二十年的 buffer\_head 换成 iomap，HPFS 被整块删掉。这两件事放在一起看，是同一条曲线的两端：内核存储栈正在把上世纪的设计替换掉，而替换的方式是「让新的先可选、旧的先出局」——iomap 因为还有特性没做完，所以做成挂载选项，遇到不支持的场景自动回落；HPFS 因为在现代内核上根本不能工作，所以连选项都不值得留。值得注意的是 EXT4 那个 opt-in 的设计：因为默认关闭且会回落，所以它不是「你必须升级」，而是「你可以试」——这才是这类内核特性最值得被采用的姿态。至于那些被删掉的老文件系统，HPFS 是 OS/2 的，BFS 是 UnixWare 的，它们对应的都是商业 Unix 史上已经落幕的那一段。代码被清掉，uapi 头留着 —— 这是内核开发者在「删掉」和「不破坏兼容」之间拿捏的分寸。

  
END  

您或许也对以下文章感兴趣：

· Linux 内核编译时间砍掉 36%  
· ext4 弃用 data=journal  
· Linux 7.3 是一个「全方位纪录」

本文同步发布于 freelamp.com 与 B站「LeisureLinux」

我是 FreeLAMP.com，专注开源安全工具与工程实践，持续分享安全入门与前沿技术的观察。

如果今天这篇有收获，欢迎**点赞、在看、转发** 三连，我们下篇见。