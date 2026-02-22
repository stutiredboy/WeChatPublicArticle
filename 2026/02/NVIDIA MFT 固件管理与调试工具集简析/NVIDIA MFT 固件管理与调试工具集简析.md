---
title: NVIDIA MFT 固件管理与调试工具集简析
---

# NVIDIA MFT 固件管理与调试工具集简析

> 原文链接：[NVIDIA MFT 固件管理与调试工具集简析](https://mp.weixin.qq.com/s?__biz=Mzk2NDEyMTM1Mg==&mid=2247488771&idx=1&sn=dea960c453f895759fc681e5386eae53&chksm=c548bc294694050d32ca6832fdf46fd849bcd61d231db6069ff10560144d9667a196da9071df&mpshare=1&scene=1&srcid=0217zyHmThsXGQx0SkMaWrfb&sharer_shareinfo=da60085b857edb6db91ab10b3bcd13b4&sharer_shareinfo_first=da60085b857edb6db91ab10b3bcd13b4#rd)

![Pasted image 20260215221355.png](images/1771725111905.png)
NVIDIA MFT（NVIDIA Firmware Tools，原 Mellanox Firmware Tools）是 NVIDIA 面向**InfiniBand、Ethernet 网卡、交换机、网关**等网络设备的**固件管理与调试工具集**，核心用于固件查询、定制、烧录与设备调试，是高性能计算（HPC）、AI 集群网络运维的必备工具。

主要内容：1. 核心定位与适用场景2. 核心工具简析（按使用频率）2.1. mst（Mellanox Service Tool）——设备管理入口2.2. flint—— 固件烧录与查询（最常用）2.3. mlxburn—— 固件定制与批量烧录2.4. mstflint——flint 的增强版（部分场景替代 flint）2.5. 调试工具集（故障排查专用）2.6. mftshell—— 交互式前端（入门友好）3. 典型工作流（固件升级）4. 安装与版本5. 关键注意事项6. NVIDIA MFT命令速查表6.1. 前置必用（mst）6.2. 查询信息6.3. 烧录固件（最常用）6.4. 恢复/清空6.5. 网卡状态&amp;配置（mlxconfig）6.6. 链路 / 端口状态（mlxlink）6.7. 一键升级流程（学废系列）6.8. 常见设备名简写（方便脚本）## 1. 核心定位与适用场景



1）**核心定位**：NVIDIA 网络设备（ConnectX 网卡、Switch-IB 交换机等）的**固件全生命周期管理工具**，替代传统厂商专用烧录工具。

2）**适用场景**网卡 / 交换机固件版本查询、升级 / 降级定制固件（如开启 SR-IOV、RoCE、DPU 功能）批量设备固件烧录与配置硬件寄存器访问、故障诊断与日志抓取

3）**支持系统**：Linux（主流发行版）、Windows、FreeBSD；适配 x86_64、ARM64 架构。## 2. 核心工具简析（按使用频率）

### 2.1. mst（Mellanox Service Tool）——设备管理入口



1）**核心作用**：启动 / 停止寄存器访问驱动、枚举本地 NVIDIA 网络设备，是所有 MFT 操作的**前置依赖**。

2）常用命令：


  
   
   
   
  `# 启动mst驱动（必须先执行）
mst start

# 列出所有可管理的NVIDIA设备（输出形如mt4123_pciconf0）
mst status

# 停止mst驱动
mst stop
`### 2.2. flint—— 固件烧录与查询（最常用）



1）**核心作用**：固件镜像烧录、版本查询、VPD（关键产品数据）读取、Flash 分区管理，支持.bin/.mlx 格式固件。

2）常用命令：


  
   
   
   
  `# 查询设备固件版本（替换为目标设备名）
flint -d mt4123_pciconf0 q

# 烧录固件（-y自动确认，-i指定镜像）
flint -d mt4123_pciconf0 -i fw-ConnectX5.bin burn

# 读取VPD信息（含PN、SN、MAC）
flint -d mt4123_pciconf0 vpd

# 擦除固件（谨慎使用）
flint -d mt4123_pciconf0 erase
`### 2.3. mlxburn—— 固件定制与批量烧录



1）**核心作用**：生成**标准 / 定制化固件镜像**、批量烧录、固件版本校验，适合大规模集群部署。

2）常用命令：


  
   
   
   
  `# 生成适配当前设备的标准固件
mlxburn -d mt4123_pciconf0 -gen

# 定制固件（开启RoCE v2、SR-IOV 8VF）

mlxburn -d mt4123_pciconf0 -gen-roce_v2_en-sriov_en-num_vfs8

# 批量烧录（从文件读取设备列表）
mlxburn -i fw.bin -devs_list devices.txt burn
`### 2.4. mstflint——flint 的增强版（部分场景替代 flint）



1）**核心作用**：与 flint 功能高度兼容，新增 DPU/BlueField 设备支持、更灵活的固件分区操作，推荐新设备使用。

2）常用命令：


  
   
   
   
  `# 查询DPU固件
mstflint -d mt4168_pciconf0 q

# 烧录DPU固件
mstflint -d mt4168_pciconf0 -i fw-BlueField3.bin burn
`### 2.5. 调试工具集（故障排查专用）



1）**mlxdump/mstdump**：抓取设备固件 / 硬件状态 Dump，用于故障分析。

2）**mlxtrace/fwtrace**：固件执行轨迹追踪，定位固件崩溃 / 异常。

3）**itrace**：InfiniBand 事务级追踪，排查网络链路问题。

4）**wqd**：Work Queue 深度监控，分析网卡队列性能瓶颈。### 2.6. mftshell—— 交互式前端（入门友好）



1）**核心作用**：MFT 工具的**命令行封装**，支持自动补全、命令历史，降低入门门槛。

2）使用方式


  
   
   
   
  `mftshell

# 进入后执行命令（无需加mst/flint前缀）
mst start
flint -d mt4123_pciconf0 q
`## 3. 典型工作流（固件升级）



1）**准备**：下载对应设备的固件镜像（NVIDIA 官网）、安装 MFT 工具包。

2）**启动驱动**：`mst start`&nbsp;→&nbsp;`mst status`&nbsp;确认设备枚举成功。

3）**查询当前版本**：`flint -d &lt;设备名&gt; q`&nbsp;记录旧版本。

4）**烧录固件**：`flint -d &lt;设备名&gt; -i &lt;固件文件&gt; burn`（等待完成，勿断电）。

5）**验证与重启**：烧录成功后，`flint q`&nbsp;确认新版本；**重启服务器 / 交换机**使固件生效。## 4. 安装与版本



1）**安装**：从 NVIDIA Networking 官网下载对应系统的 MFT 包（.rpm/.deb/.exe），按指引安装。

2）**版本匹配**：MFT 版本需与**固件版本、设备型号**兼容，建议使用最新 LTS 版（如 v4.26.x）。## 5. 关键注意事项



1）**风险提示**：固件烧录失败可能导致设备变砖，**操作前备份固件、确保供电稳定、严格匹配设备型号**。

2）**权限要求**：Linux 需 root 权限，Windows 需管理员权限。

3）**设备兼容性**：仅支持 NVIDIA（原 Mellanox）网络设备，不支持 GPU 固件管理。## 6. NVIDIA MFT命令速查表

### 6.1. 前置必用（mst）




  
   
   
   
  `# 启动驱动（所有操作前必须）
mst start

# 查看网卡设备名（如 mt4123_pciconf0）
mst status

# 停止驱动
mst stop
`### 6.2. 查询信息




  
   
   
   
  `# 查看固件版本
flint -d 设备名 q

# 查看完整信息（PN、SN、PSID、MAC）
flint -d 设备名 si

# 查看 VPD
flint -d 设备名 vpd
`### 6.3. 烧录固件（最常用）




  
   
   
   
  `# 直接烧录（-y 自动确认）
flint -d 设备名 -i fw.bin -y burn

# 不校验直接烧（风险高，仅应急）
flint -d 设备名 -i fw.bin -y-nofs burn
`### 6.4. 恢复/清空




  
   
   
   
  `# 清空固件（慎用！）
flint -d 设备名 erase

# 恢复出厂默认配置
flint -d 设备名 reset
`### 6.5. 网卡状态&amp;配置（mlxconfig）




  
   
   
   
  `# 查看当前配置
mlxconfig -d 设备名 query

# 查看所有可配项
mlxconfig -d 设备名 show_all

# 开启 SR-IOV
mlxconfig -d 设备名 setSRIOV_EN=1NUM_OF_VFS=8

# 开启 RoCE v2
mlxconfig -d 设备名 setROCE_CC_LEGACY=1

# 配置完必须重启生效
`### 6.6. 链路 / 端口状态（mlxlink）




  
   
   
   
  `# 查看端口状态、速率、光模块信息
mlxlink -d 设备名

# 强制 100G / 25G 速率
mlxlink -d 设备名 -s 100G
mlxlink -d 设备名 -s 25G

# 查看错误计数
mlxlink -d 设备名 -c
`### 6.7. 一键升级流程（学废系列）




  
   
   
   
  `# 1. 启动 mst
mst start

# 2. 找到设备
mst status

# 3. 查看当前版本
flint -d mt4123_pciconf0 q

# 4. 烧录
flint -d mt4123_pciconf0 -i fw-ConnectX5.bin -y burn

# 5. 重启服务器
reboot
`### 6.8. 常见设备名简写（方便脚本）




  
   
   
   
  `# 列出所有网卡设备
mst status |grep mt |awk'{print $1}'

# 批量查询所有网卡固件版本
fordevin`mst status |grep mt |awk'{print $1}'`;do
echo"=== $dev ==="
&nbsp; flint -d$dev q
done`

