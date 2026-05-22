---
title: 万卡 NVIDIA GPU 集群自动化装机实战:从 BMC 就绪到全集群上线
date: 2026-05-23
source: https://mp.weixin.qq.com/s/CBaU63mLVOgV3qGK5sWPPA
images: 3
---

# 万卡 NVIDIA GPU 集群自动化装机实战:从 BMC 就绪到全集群上线

> 假设你已经把所有服务器的 BMC IP、IPMI 账号密码配好了——本文从这里开始,一步步带你用 MAAS 把上千台 NVIDIA H100/H200 服务器干净利落地装上 Ubuntu,同时把 CUDA 驱动、Mellanox OFED、NCCL 调优全部固化进入镜像,真正做到**上电即可用** 。

## 一、整体架构:为万卡而设计的 MAAS 拓扑

直接给方案,不绕弯路。万卡规模建议这样部署:

![](images/55fc496a.jpg)

**资源预估**\(以 1300 台 8 卡节点 ≈ 10,400 GPU 为例\):

角色| 数量| 规格| 备注  
---|---|---|---  
Region Controller| 2| 32C / 128GB / 1TB NVMe| 主备 keepalived,数据库压力主要在这  
Rack Controller| 4| 16C / 64GB / 500GB NVMe| 每台覆盖 ~325 个节点  
管理网带宽| -| 每 Rack 至少 25 Gbps 上联| 镜像分发是主要瓶颈  
  
## 二、前置检查清单

开始之前,把这几件事确认一遍,可以省掉后面 80% 的坑:

项目| 要求  
---|---  
BMC 网络| 所有 BMC IP 已配好,**Region/Rack 能 ping 通且 IPMI/Redfish 可访问**  
管理网| 所有节点的管理网网卡已连到对应 ToR,VLAN 已打通  
BIOS 设置| 启用 **PXE Boot over IPv4 \(UEFI\)** ,启动顺序首位  
BIOS 设置| 关闭 Secure Boot\(MAAS 默认镜像未签名\),关闭 CSM  
网卡| 管理网网卡 PXE ROM 已启用,记录每台的**管理网 MAC**  
BMC 凭据| 准备好 CSV:hostname、BMC IP、IPMI/Redfish 账号密码、管理网 MAC  
内网镜像源| 提前同步好 Ubuntu 24.04 archive 到内网,加速 commissioning  
时间同步| Region/Rack 与 BMC 都接到同一个 NTP 源  
  
CSV 模板长这样,后面要用:
      
      1. hostname,bmc_ip,bmc_user,bmc_pass,mgmt_mac,rack
        2. gpu-r01-001,10.200.1.1,admin,Pwd@123,b8:ce:f6:01:00:01,rack-1
        3. gpu-r01-002,10.200.1.2,admin,Pwd@123,b8:ce:f6:01:00:02,rack-1
        4. ...
        5. gpu-r10-130,10.200.10.130,admin,Pwd@123,b8:ce:f6:0a:00:82,rack-4
    
    

## 三、整体流程一图速览

## ![](images/105e8989.jpg)

下面逐步展开。

## 四、第一步:安装 MAAS Region Controller

挑两台干净的 Ubuntu 24.04 LTS 服务器做 Region\(高可用一主一备\),先在主节点上:
      
      1. # 1. 安装 PostgreSQL(MAAS 元数据库)
        2. sudo apt update
        3. sudo apt install -y postgresql
        4.   
         
        5. # 2. 创建 MAAS 数据库和用户
        6. sudo -u postgres psql <<EOF
        7. CREATE USER maas WITH ENCRYPTED PASSWORD 'maas_db_pwd';
        8. CREATE DATABASE maasdb OWNER maas;
        9. EOF
        10.   
         
        11. # 3. 允许 Region/Rack 连接数据库
        12. echo "host maasdb maas 10.0.0.0/8 md5"| sudo tee -a /etc/postgresql/16/main/pg_hba.conf
        13. sudo sed -i "s/^#listen_addresses.*/listen_addresses = '*'/"/etc/postgresql/16/main/postgresql.conf
        14. sudo systemctl restart postgresql
        15.   
         
        16. # 4. 安装 MAAS Region(deb 包,生产推荐)
        17. sudo apt install -y maas-region-api
        18.   
         
        19. # 5. 初始化
        20. sudo maas init region \
        21. --database-uri "postgres://maas:maas_db_pwd@127.0.0.1/maasdb" \
        22. --maas-url "http://maas.example.com:5240/MAAS"
        23.   
         
        24. # 6. 创建管理员账户
        25. sudo maas createadmin \
        26. --username=admin \
        27. --password='Adm1n@MAAS' \
        28. --email=ops@example.com
        29.   
         
        30. # 7. 取出 API Key,保存好后面要用
        31. sudo maas apikey --username=admin >~/maas-apikey.txt
    
    

**Region HA\(可选但强推\)** :第二台 Region 节点装好 `maas-region-api` 后,用同一个数据库 URI 重新跑 `maas init region` 即可。前面挂个 keepalived 提供 VIP,数据库用 `repmgr` 做流复制。

打开浏览器访问 `http://<region_vip>:5240/MAAS`,首次登录会让你配置:

  * **DNS forwarder** :填内网 DNS,例如 `10.0.0.10`
  * **Ubuntu archive** :改成内网镜像 `http://mirrors.example.com/ubuntu`
  * **Default OS** :选 Ubuntu Noble 24.04
  * **SSH 公钥** :粘上你的运维公钥,所有部署后的机器自动带上

## 五、第二步:部署 Rack Controller

每个机房一台\(或两台 HA\)。在每台 Rack 节点上:
      
      1. # 1. 装 Rack 包
        2. sudo apt install -y maas-rack-controller
        3.   
         
        4. # 2. 在 Region 上拿 shared secret
        5. sudo cat /var/lib/maas/secret              # 在 Region 节点执行,记录输出
        6.   
         
        7. # 3. 在 Rack 节点上注册到 Region
        8. sudo maas init rack \
        9. --maas-url http://<region_vip>:5240/MAAS \
        10. --secret <shared_secret>
        11.   
         
        12. # 4. 确认 Rack 已上线
        13. sudo maas status
    
    

回到 Region Web UI → Controllers,应能看到所有 Rack 节点都是 Connected 状态。

## 六、第三步:配置网络与 DHCP

MAAS 必须托管 PXE 子网的 DHCP。注意**不要和现有 DHCP 服务冲突** ,要么完全交给 MAAS,要么用专属 VLAN 隔离。
      
      1. # 登录 CLI(把 Web UI 拿到到> \
        2.   secondary_rack=<rack2_system_id>
        3.   
         
        4. # 3. 划分 IP 段:动态池(装机临时用)+ 保留段(已部署节点静态)
        5. maas admin ipranges create \
        6.   type=dynamic \
        7.   start_ip=10.10.0.100 end_ip=10.10.0.250 \
        8.   subnet=$SUBNET_ID \
        9.   comment='PXE temporary pool'
        10.   
         
        11. maas admin ipranges create \
        12.   type=reserved \
        13.   start_ip=10.10.1.0 end_ip=10.10.1.255 \
        14.   subnet=$SUBNET_ID \
        15.   comment='Static range for deployed nodes'
        16.   
         
        17. # 4. 设置网关和 DNS
        18. maas admin subnet update $SUBNET_ID \
        19.   gateway_ip=10.10.0.1 \
        20.   dns_servers=10.0.0.10
    
    

如果集群有多个 VLAN\(管理网、存储网、参数面分别独立\),逐个配置 subnet,**只在管理网开 DHCP** ,其他网络后续通过 cloud-init 配置静态 IP。

## 七、第四步:打 NVIDIA 镜像

这一步是装机效率的关键。把 CUDA 驱动、Mellanox OFED、NCCL、内核参数、监控 agent 全部预装进镜像,部署阶段只剩 cloud-init 跑个性化配置,**单台装机时间能压到 5 分钟以内** 。

### 7.1 准备 Packer 构建环境

挑一台带 KVM 加速的构建机\(8 核以上\):
      
      1. sudo apt install -y qemu-system-x86 qemu-utils libvirt-daemon-system
        2. wget https://releases.hashicorp.com/packer/1.11.2/packer_1.11.2_linux_amd64.zip
        3. unzip packer_1.11.2_linux_amd64.zip && sudo mv packer /usr/local/bin/
    
    

### 7.2 写 Packer 模板

`gpu-image.pkr.hcl`:
      
      1. packer {
        2.   required_plugins {
        3.     qemu ={ source ="github.com/hashicorp/qemu", version ="~> 1"}
        4. }
        5. }
        6.   
         
        7. variable "ubuntu_image"{
        8. default="https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"
        9. }
        10.   
         
        11. source "qemu""gpu"{
        12.   iso_url       =var.ubuntu_image
        13.   iso_checksum  ="file:https://cloud-images.ubuntu.com/noble/current/SHA256SUMS"
        14.   disk_image    =true
        15.   disk_size     ="30G"
        16.   format        ="raw"
        17.   accelerator   ="kvm"
        18.   cpus          =4
        19.   memory        =8192
        20.   ssh_username  ="ubuntu"
        21.   ssh_private_key_file ="./id_rsa"
        22.   ssh_timeout   ="20m"
        23.   shutdown_command ="sudo shutdown -P now"
        24.   output_directory ="output-gpu"
        25.   vm_name       ="gpu-noble.raw"
        26.   
         
        27. # 用 cloud-init seed ISO 注入初始 SSH key
        28.   cd_files      =["./cloud-init/user-data","./cloud-init/meta-data"]
        29.   cd_label      ="cidata"
        30. }
        31.   
         
        32. build {
        33.   name    ="gpu-golden"
        34.   sources =["source.qemu.gpu"]
        35.   
         
        36. # ① 基础系统配置
        37.   provisioner "shell"{
        38. inline=[
        39. "sudo apt-get update",
        40. "sudo apt-get install -y build-essential dkms linux-headers-$(uname -r) \
        41.          chrony net-tools ipmitool ethtool lldpd \
        42.          pciutils nvme-cli sysstat htop jq",
        43. # 容器运行时(K8s/Docker 集群预装)
        44. "sudo apt-get install -y containerd runc",
        45. # 监控 agent
        46. "curl -sSL http://mirrors.example.com/scripts/install-node-exporter.sh | sudo bash"
        47. ]
        48. }
        49.   
         
        50. # ② 屏蔽 nouveau,准备装 NVIDIA 驱动
        51.   provisioner "shell"{
        52. inline=[
        53. "echo 'blacklist nouveau' | sudo tee /etc/modprobe.d/blacklist-nouveau.conf",
        54. "echo 'options nouveau modeset=0' | sudo tee -a /etc/modprobe.d/blacklist-nouveau.conf",
        55. "sudo update-initramfs -u"
        56. ]
        57. }
        58.   
         
        59. # ③ 安装 NVIDIA 驱动 + CUDA Toolkit + Fabric Manager
        60.   provisioner "shell"{
        61. inline=[
        62. # 添加 NVIDIA 官方仓库(生产推荐内网镜像)
        63. "wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb",
        64. "sudo dpkg -i cuda-keyring_1.1-1_all.deb",
        65. "sudo apt-get update",
        66. # 装 Open GPU Kernel Module(H100/H200/B200 必须用 open driver)
        67. "sudo apt-get install -y nvidia-driver-570-open nvidia-utils-570",
        68. # 装 CUDA 工具链(可选,如果业务侧自己装 CUDA 可以跳过)
        69. "sudo apt-get install -y cuda-toolkit-12-6",
        70. # 装 Fabric Manager(NVLink/NVSwitch 拓扑必备,DGX/HGX 平台必装)
        71. "sudo apt-get install -y nvidia-fabricmanager-570",
        72. "sudo systemctl enable nvidia-fabricmanager",
        73. # 装 nvidia-persistenced(常驻进程,避免每次启动 CUDA 时长延迟)
        74. "sudo systemctl enable nvidia-persistenced"
        75. ]
        76. }
        77.   
         
        78. # ④ 安装 Mellanox OFED(ConnectX-7/BlueField-3 RDMA 驱动)
        79.   provisioner "shell"{
        80. inline=[
        81. "wget https://content.mellanox.com/ofed/MLNX_OFED-24.10-1.1.4.0/MLNX_OFED_LINUX-24.10-1.1.4.0-ubuntu24.04-x86_64.tgz",
        82. "tar xzf MLNX_OFED_LINUX-*.tgz",
        83. "cd MLNX_OFED_LINUX-* && sudo ./mlnxofedinstall --without-fw-update --force --upstream-libs --dpdk",
        84. "cd .. && sudo rm -rf MLNX_OFED_LINUX-*",
        85. # RDMA 工具链
        86. "sudo apt-get install -y rdma-core ibverbs-utils perftest libibverbs-dev"
        87. ]
        88. }
        89.   
         
        90. # ⑤ 内核 / sysctl 优化(NCCL / 大模型训练通用)
        91.   provisioner "file"{
        92.     destination ="/tmp/99-cluster.conf"
        93.     content =<<-EOT
        94. # TCP buffer for high BDP
        95.       net.ipv4.tcp_rmem =409687380268435456
        96.       net.ipv4.tcp_wmem =409665536268435456
        97.       net.core.rmem_max =268435456
        98.       net.core.wmem_max =268435456
        99.       net.core.netdev_max_backlog =250000
        100. # huge pages 给训练用
        101.       vm.nr_hugepages =2048
        102.       vm.swappiness =1
        103. # 文件描述符
        104.       fs.file-max =2097152
        105.       fs.nr_open =1048576
        106.     EOT
        107. }
        108.   provisioner "shell"{
        109. inline=["sudo mv /tmp/99-cluster.conf /etc/sysctl.d/"]
        110. }
        111.   
         
        112. # ⑥ GRUB 内核参数(IOMMU passthrough、关闭 mitigations、PCIe 优化)
        113.   provisioner "shell"{
        114. inline=[
        115. "sudo sed -i 's|GRUB_CMDLINE_LINUX_DEFAULT=.*|GRUB_CMDLINE_LINUX_DEFAULT=\"intel_iommu=on iommu=pt mitigations=off transparent_hugepage=madvise pcie_aspm=off\"|' /etc/default/grub",
        116. "sudo update-grub"
        117. ]
        118. }
        119.   
         
        120. # ⑦ NCCL 默认配置(后续业务可覆盖)
        121.   provisioner "file"{
        122.     destination ="/tmp/nccl.conf"
        123.     content =<<-EOT
        124. # 多机多卡训练默认走 RDMA
        125.       NCCL_IB_HCA=mlx5
        126.       NCCL_IB_GID_INDEX=3
        127.       NCCL_IB_TC=160
        128.       NCCL_IB_SL=5
        129.       NCCL_NET_GDR_LEVEL=2
        130.       NCCL_DEBUG=INFO
        131.       NCCL_TOPO_FILE=/etc/nccl-topo.xml
        132.     EOT
        133. }
        134.   provisioner "shell"{
        135. inline=["sudo mkdir -p /etc/nccl && sudo mv /tmp/nccl.conf /etc/nccl/nccl.conf"]
        136. }
        137.   
         
        138. # ⑧ 关键!清理状态,避免镜像复用时机器身份冲突
        139.   provisioner "shell"{
        140. inline=[
        141. "sudo cloud-init clean --logs --seed",
        142. "sudo apt-get clean",
        143. "sudo rm -rf /var/lib/apt/lists/*",
        144. "sudo truncate -s 0 /etc/machine-id",
        145. "sudo rm -f /var/lib/dbus/machine-id",
        146. "sudo ln -sf /etc/machine-id /var/lib/dbus/machine-id",
        147. "sudo rm -rf /tmp/* /var/tmp/* /root/.bash_history /home/ubuntu/.bash_history",
        148. "sudo rm -f /etc/ssh/ssh_host_*",# 让首次启动重生成 host key
        149. "sudo find / -name '*.dpkg-old' -delete 2>/dev/null || true"
        150. ]
        151. }
        152. }
    
    

构建:
      
      1. mkdir -p cloud-init && cd cloud-init
        2. ssh-keygen -f id_rsa -N ''
        3. cat > user-data <<EOF
        4. #cloud-config
        5. ssh_authorized_keys:
        6. - $(cat id_rsa.pub)
        7. ssh_pwauth: true
        8. chpasswd:
        9.   expire: false
        10.   users:
        11. -{ name: ubuntu, password: ubuntu, type: text }
        12. EOF
        13. echo "instance-id: gpu-build"> meta-data
        14. cd ..
        15.   
         
        16. packer build gpu-image.pkr.hcl
        17. # 产物:output-gpu/gpu-noble.raw
    
    

整个构建过程通常 30~50 分钟,主要时间花在 OFED 编译上。**这是一次性投入,后续每次 deploy 都直接用这个镜像。**

##  八、第五步:上传镜像到 MAAS

MAAS 接收的自定义镜像必须是 `tar.gz` 包裹的 raw 文件:
      
      1. # 1. 转格式 + 打包
        2. qemu-img convert -O raw output-gpu/gpu-noble.raw gpu-noble.img
        3. tar czf gpu-noble.tar.gz gpu-noble.img
        4.   
         
        5. # 2. 上传到 MAAS
        6. maas admin boot-resources create \
        7.   name='custom/gpu-noble' \
        8.   title='Ubuntu 24.04 NVIDIA Golden' \
        9.   architecture='amd64/generic' \
        10.   filetype='tgz' \
        11.   base_image='ubuntu/noble' \
        12.   content@=gpu-noble.tar.gz
        13.   
         
        14. # 3. 确认上传成功
        15. maas admin boot-resources read | jq '.[] | select(.name=="custom/gpu-noble")'
    
    

后续每次驱动 / 内核升级,重跑 Packer + 上传一次新版本即可。MAAS 支持镜像版本管理,可以指定老版本回滚。

## 九、第六步:批量录入服务器

BMC 已经配好,直接走 API 批量导入。把前面的 CSV 喂给下面这个脚本:
      
      1. #!/bin/bash
        2. # bulk-enroll.sh
        3.   
         
        4. while IFS=, read -r hostname bmc_ip bmc_user bmc_pass mgmt_mac rack;do
        5. ["$hostname"="hostname"]&&continue# 跳过表头
        6.   
         
        7.   echo "Enrolling $hostname ($bmc_ip)..."
        8.   maas admin machines create \
        9.     hostname="$hostname" \
        10.     architecture=amd64/generic \
        11.     mac_addresses="$mgmt_mac" \
        12.     power_type=redfish \
        13.     power_parameters_power_address="https://$bmc_ip" \
        14.     power_parameters_power_user="$bmc_user" \
        15.     power_parameters_power_pass="$bmc_pass" \
        16.     power_parameters_power_verify_ssl=n \
        17. >/dev/null 2>&1&& echo "  ✓ OK"|| echo "  ✗ FAIL"
        18. done< gpu-nodes.csv
    
    

执行:
      
      1. chmod +x bulk-enroll.sh
        2. ./bulk-enroll.sh 2>&1| tee enroll.log
    
    

**故障排查** :如果 `power_type=redfish` 失败\(部分老 BMC 不支持\),改用 `power_type=ipmi`:
      
      1. power_type=ipmi
        2. power_parameters_power_address="$bmc_ip"
        3. power_parameters_power_driver=LAN_2_0
        4. power_parameters_power_boot_type=efi
    
    

录入完成后:
      
      1. maas admin machines read | jq '[.[] | {hostname, status_name, power_state}]'| head -50
    
    

应该看到所有机器都是 `New` 状态,`power_state` 大部分是 `off`\(MAAS 已经能通过 BMC 看到电源状态\)。

## 十、第七步:Commissioning\(自检 + 硬件清点\)

这一步会让所有机器**自动开机 → PXE → 跑硬件检测 → 自动关机** ,把 CPU/内存/磁盘/网卡/PCIe 拓扑全部录入数据库。

理解每台机器在 MAAS 里的状态流转,对排错非常关键:

![](images/3ce86d70.jpg)

执行批量 commission:
      
      1. # 拉取所有 New 状态的机器
        2. NEW_MACHINES=$(maas admin machines read | \
        3.   jq -r '.[] | select(.status_name=="New") | .system_id')
        4.   
         
        5. # 分批,每批 200 台,避免 boot storm
        6. BATCH_SIZE=200
        7. echo "$NEW_MACHINES"| split -l $BATCH_SIZE - batch_
        8.   
         
        9. for batch in batch_*;do
        10.   echo "=== 提交批次 $batch ==="
        11. while read sid;do
        12.     maas admin machine commission "$sid" \
        13.       enable_ssh=1 \
        14.       skip_bmc_config=1&
        15. done<"$batch"
        16.   wait
        17.   echo "等待 30 秒再提交下一批..."
        18.   sleep 30
        19. done
        20. rm -f batch_*
    
    

监控进度\(开个窗口跑\):
      
      1. watch -n 5'maas admin machines read | \
        2.   jq -r "[.[].status_name] | group_by(.) | map({status: .[0], count: length})"'
    
    

正常情况下,几分钟后机器状态会按 `New → Commissioning → Testing → Ready` 流转。如果有节点卡在 `Commissioning` 超过 30 分钟,大概率是这四种原因之一:

  1. **BIOS PXE 启动顺序错了** → 进 BMC 改启动顺序
  2. **管理网网卡 MAC 录错了** → CSV 核对一遍
  3. **Secure Boot 没关** → BMC 里关掉
  4. **HTTP/TFTP 在 Rack 上被防火墙拦** → `sudo ufw status` 检查

进入 Ready 状态后,所有机器的硬件清单都能在 Web UI 的 Hardware 标签下看到——这一步顺便就给你交付了一份**全集群硬件资产表** 。

## 十一、第八步:批量部署上线

终于到了最爽的一步。给机器打 tag、绑定 cloud-init、批量部署:
      
      1. # 1. 给所有 GPU 节点打 tag
        2. for sid in $(maas admin machines read | \
        3.   jq -r '.[] | select(.hostname|startswith("gpu-")) | .system_id');do
        4.   maas admin tag update-nodes gpu add="$sid"2>/dev/null
        5. done
        6.   
         
        7. # 2. 准备 cloud-init(部署后立即跑的个性化配置)
        8. cat > deploy-cloud-init.yaml <<'EOF'
        9. #cloud-config
        10.   
         
        11. # 时区 / 主机名(MAAS 会自动注入 hostname)
        12. timezone:Asia/Shanghai
        13.   
         
        14. # 写入 RDMA 网卡静态配置(用 MAC 匹配,避免接口名漂移)
        15. write_files:
        16. - path:/etc/netplan/60-rdma.yaml
        17.     permissions:'0600'
        18.     content:|
        19.       network:
        20.         version:2
        21.         ethernets:
        22.           rdma0:
        23.             match:{ macaddress:"auto"}
        24. set-name: rdma0
        25.             mtu:4200
        26.             dhcp4: false
        27.           rdma1:
        28.             match:{ macaddress:"auto"}
        29. set-name: rdma1
        30.             mtu:4200
        31.             dhcp4: false
        32.   
         
        33. - path:/etc/security/limits.d/99-hpc.conf
        34.     content:|
        35. * soft nofile 1048576
        36. * hard nofile 1048576
        37. * soft memlock unlimited
        38. * hard memlock unlimited
        39. * soft stack unlimited
        40.   
         
        41. - path:/etc/modules-load.d/rdma.conf
        42.     content:|
        43.       ib_uverbs
        44.       mlx5_core
        45.       mlx5_ib
        46.   
         
        47. runcmd:
        48. # 应用网卡配置
        49. - netplan apply
        50. # GPU 持久模式(避免每次启动 CUDA 时延迟)
        51. - nvidia-smi -pm 1
        52. # 启用 ECC(默认就开,显式确认一遍)
        53. - nvidia-smi -e 1
        54. # 启动监控
        55. - systemctl enable --now node_exporter
        56. - systemctl enable --now nvidia-fabricmanager
        57. - systemctl enable --now nvidia-persistenced
        58. # 自检并打日志
        59. - nvidia-smi --query-gpu=index,name,driver_version,memory.total,pstate --format=csv >/var/log/gpu-inventory.log
        60. - ibv_devinfo >/var/log/rdma-devinfo.log
        61. - nvidia-smi nvlink --status >/var/log/nvlink-status.log
        62. # 注册到调度器(SLURM / K8s)
        63. -/opt/cluster/register.sh
        64.   
         
        65. # 训练用户(SSH 公钥从 MAAS 全局配置继承)
        66. users:
        67. - name: trainer
        68.     sudo:'ALL=(ALL) NOPASSWD:ALL'
        69.     groups:[adm, sudo, docker]
        70.     shell:/bin/bash
        71. EOF
        72.   
         
        73. # 3. 批量部署:用前面打的金镜像
        74. USER_DATA=$(base64 -w0 deploy-cloud-init.yaml)
        75.   
         
        76. for sid in $(maas admin machines read | \
        77.   jq -r '.[] | select(.tag_names != null and (.tag_names|index("gpu")) and .status_name=="Ready") | .system_id');do
        78.   
         
        79.   maas admin machine deploy "$sid" \
        80.     distro_series=gpu-noble \
        81.     user_data="$USER_DATA"&
        82.   
         
        83. # 控制并发,避免镜像分发把 Rack 网卡打爆
        84. [ $(jobs -r | wc -l)-ge 100]&& wait -n
        85. done
        86. wait
        87.   
         
        88. echo "全部部署任务已提交,在 Web UI 监控状态。"
    
    

**部署进度监控** :
      
      1. watch -n 10'maas admin machines read | \
        2.   jq -r "[.[] | select(.tag_names!=null and (.tag_names|index(\"gpu\"))) | .status_name] | \
        3.    group_by(.) | map({s: .[0], n: length})"'
    
    

## 十二、第九步:部署后验证

机器进入 `Deployed` 状态不代表它真的能跑训练。建议跑一遍**上线巡检脚本** ,问题节点立刻挑出来:
      
      1. # verify.sh,在 Region/跳板机上执行
        2. cat > verify.sh <<'EOF'
        3. #!/bin/bash
        4. HOSTS=$(maas admin machines read | \
        5.   jq -r '.[] | select(.status_name=="Deployed") | .hostname')
        6.   
         
        7. PASS=0; FAIL=0; FAIL_HOSTS=""
        8.   
         
        9. for h in $HOSTS;do
        10.   result=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
        11.     ubuntu@$h "
        12.       gpu_count=\$(nvidia-smi --query-gpu=count --format=csv,noheader 2>/dev/null | head -1)
        13.       ecc_errors=\$(nvidia-smi --query-gpu=ecc.errors.uncorrected.volatile.total --format=csv,noheader 2>/dev/null | awk 'BEGIN{s=0}{s+=\$1}END{print s}')
        14.       nvlink_ok=\$(nvidia-smi nvlink --status 2>/dev/null | grep -c 'Active')
        15.       rdma_count=\$(ibv_devices 2>/dev/null | grep -cE '^\s+(mlx|rocep)')
        16.       mem_gb=\$(free -g | awk '/^Mem/{print \$2}')
        17.       echo \"\$gpu_count \$ecc_errors \$nvlink_ok \$rdma_count \$mem_gb\"
        18.     "2>/dev/null)
        19.   
         
        20.   read gpu ecc nvlink rdma mem <<<"$result"
        21.   
         
        22. # H100 8 卡 + 18 NVLink active + 8 RDMA NIC 是健康标志
        23. if["$gpu"="8"]&&["$nvlink"-ge "16"]&&["$ecc"="0"] \
        24. &&["$rdma"-ge "8"]&&["$mem"-ge "1000"];then
        25.     PASS=$((PASS+1))
        26. else
        27.     FAIL=$((FAIL+1))
        28.     FAIL_HOSTS="$FAIL_HOSTS\n  $h (gpu=$gpu, nvlink=$nvlink, ecc=$ecc, rdma=$rdma, mem=$mem)"
        29. fi
        30. done
        31.   
         
        32. echo "PASS: $PASS"
        33. echo "FAIL: $FAIL"
        34. echo -e "Problem hosts:$FAIL_HOSTS"
        35. EOF
        36.   
         
        37. chmod +x verify.sh &&./verify.sh
    
    

期望输出:
      
      1. PASS:1300
        2. FAIL:0
    
    

任何 `FAIL` 节点直接在 MAAS Web UI 选中 → Release → 重新 Deploy 一次,自动化流程会自愈。

进阶巡检还可以加上:

  * `nccl-tests` 跑 all-reduce,验证机内 NVLink 和机间 RDMA 带宽
  * `dcgmi diag -r 3` 跑 NVIDIA 官方 GPU 健康诊断
  * `ibstat` 检查每个 RDMA port 的 LinkUp 状态和速率

## 十三、运维侧常用操作速查

整套体系跑起来后,日常会反复用到这几条命令:
      
      1. # 重装一台节点(故障替换、内核升级)
        2. maas admin machine release <system_id> erase=true secure_erase=true
        3. maas admin machine deploy <system_id> distro_series=gpu-noble user_data="$USER_DATA"
        4.   
         
        5. # 一键关机 / 开机(IPMI 直控)
        6. maas admin machine power-off <system_id>
        7. maas admin machine power-on <system_id>
        8.   
         
        9. # 查看某台机器的事件日志(排查装机失败)
        10. maas admin events query hostname=gpu-r01-001 limit=50
        11.   
         
        12. # 镜像版本切换(测试环境先验证)
        13. maas admin boot-resource update <resource_id>...
        14.   
         
        15. # 导出全集群资产清单(给客户验收用)
        16. maas admin machines read | \
        17.   jq -r '.[] | [.hostname, .cpu_count, .memory, .architecture,
        18.                 (.power_parameters.power_address // "")] | @csv' \
        19. > assets.csv
    
    

## 十四、最后几条踩坑提醒

  1. **镜像分发瓶颈** :超过 500 并发部署时,在每个 Rack 上额外起一个 nginx 缓存代理,把 boot resource 二级缓存住,带宽降一半。
  2. **BMC 限流** :有些品牌的 BMC\(尤其是 Supermicro 老型号\)同一时刻接受的 IPMI 会话数有限,`bulk-enroll` 时如果失败率高,把脚本里的并发降到 50 以下。
  3. **大磁盘扫描慢** :NVMe 多盘的机器 commissioning 阶段 SMART 扫描可能耗时 10+ 分钟,这是正常的,别提前 abort。
  4. **网卡命名漂移** :不同批次的服务器即使型号一样,网卡命名也可能不同。在 cloud-init 里用 `match: macaddress` 而不是写死接口名,会更鲁棒。
  5. **Fabric Manager 必启** :H100/H200/B200 这类有 NVSwitch 的平台,`nvidia-fabricmanager` 服务没起 GPU 之间的 NVLink 跑不通,nvidia-smi 看着正常但跑 NCCL 会卡死。
  6. **驱动与 CUDA 版本对齐** :Open Kernel Module 从 R515 开始才支持 H100,选驱动版本时务必和 CUDA Toolkit 对齐\(参见 NVIDIA 官方兼容性表\)。生产环境强烈建议锁版本,统一升级。
  7. **金镜像版本管理** :每次更新镜像时,在 `name` 里带上版本号\(`custom/gpu-noble-v20260426`\),旧版本保留至少两个,出问题能快速回滚。
  8. **释放节点必须擦盘** :`release` 时一定加 `erase=true`,否则下任租户能恢复出上家的数据。涉密集群上 `secure_erase=true` 走硬件层 ATA Secure Erase。

* * *

走完这一整套流程,1300 台节点从”BMC 配好 + 上电”到”全部 Deployed + 验证通过”,熟练后**端到端 90 分钟以内** 完全可以做到。后续无论是季度大重装、客户验收前清场、还是临时切换驱动版本,都是同一套 API 重跑一遍而已——这就是 MAAS 给万卡 GPU 集群带来的真正价值。

> **配套资源**
> 
>   * MAAS 官方文档:`https://maas.io/docs`
>   * NVIDIA Open GPU Kernel Modules:`https://github.com/NVIDIA/open-gpu-kernel-modules`
>   * Mellanox OFED 下载:`https://network.nvidia.com/products/infiniband-drivers/linux/mlnx_ofed/`
>   * NCCL 官方调优指南:`https://docs.nvidia.com/deeplearning/nccl/`
>