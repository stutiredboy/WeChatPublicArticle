---
title: k8s mellanox网卡使用dpdk驱动问题总结
---

# k8s mellanox网卡使用dpdk驱动问题总结

> 原文链接：[k8s mellanox网卡使用dpdk驱动问题总结](https://mp.weixin.qq.com/s?__biz=MzIwMzU1Njg1Nw==&mid=2247483860&idx=1&sn=6d6c124166d20803b0cbc1fc51924980&chksm=97bad49b155ac906cb78f6a4168ca675490df844467bb46d598fd2945c3a07f1d8ea72bca332&mpshare=1&scene=1&srcid=0201qJQWSWc3qOxpMO1nsX34&sharer_shareinfo=35c57ed1cdb1c60fec763e84c523dc83&sharer_shareinfo_first=35c57ed1cdb1c60fec763e84c523dc83#rd)

本文主要总结一下在k8s环境中，mellanox网卡使用dpdk driver可能会遇到的问题及解决办法。




**不能挂载 /sys 目录到pod中**



其他厂家的网卡，比如intel的x710等，如果想在k8s中，使用dpdk driver，/sys目录是必须挂载的，因为dpdk启动过程会读取这个目录下的文件。但是对于mellanox网卡来说，它是比较特殊的，在使用dpdk driver时，也必须绑定在kernel driver mlx5_core上面。




如果挂载了 /sys 目录到pod中，就会报如下的错误

```
net_mlx5: port&nbsp;0&nbsp;cannot get MAC address, is mlx5_en loaded? (errno: No such file or directory)
```

原因是 host上的 /sys/ 会覆盖 pod 里的 /sys/ 内容，而 mlx 网卡会读取这些目录，比如 /sys/devices/pci0000:00/0000:00:09.0/net/，如果覆盖了，就会报错。




下面分析下代码

```
mlx5_pci_probe
```


**dpdk启动过程中找不到mellanox网卡**
有时候会出现下面的错误，找不到mellanox网卡，并且提示了是不是没有加载kernel driver，如果没有在k8s环境中，这个提示是有用的，可能网卡确实没有绑定到mlx5_core

```
EAL: PCI device 0000:00:06.0 on NUMA socket -1"}
```
但是在k8s环境中，就有其他原因了。问题现象是，如果启动的pod有privileged权限，那dpdk是可以识别到网卡并且启动成功的，但是如果没有privileged权限，就会报上面的错误。

先分析下为什么报这个错误，dpdk代码如下

```
mlx5_pci_probe
```


要想知道为什么ret也为0，得分析下 libibverbs 源码，libibverbs 源码可以在&nbsp;OFED&nbsp;包中找到，路径如下 MLNX_OFED_LINUX-5.2-2.2.0.0-ubuntu16.04-x86_64/src/MLNX_OFED_SRC-5.2-2.2.0.0/SOURCES/rdma-core-52mlnx1/libibverbs

```
LATEST_SYMVER_FUNC(ibv_get_device_list,&nbsp;1_1,&nbsp;"IBVERBS_1.1",
```由上面代码可知，ibverbs会检查/dev/infiniband/uverbs0文件是否存在(一个网卡对应一个uverbs0)，如果不存在就认为没有找到网卡。
如果pod有privileged权限，pod内就可以读取/dev/infiniband/uverbs0这些文件，如果没有privileged权限，pod内部是没有/dev/infiniband这个目录的。

```
//pod没有privilege特权时
```


由上可知，pod里有没有这个文件 /dev/infiniband/uverbs0 是关键。如果pod内没有这些 /dev/infiniband 文件就会报上面的错误。

那这个文件怎么才能传到pod里呢？有两种办法
a. 给pod privileged权限，这种方式是不需要将 /dev/ 挂载到pod内部的，因为有特权的pod可以直接访问host上的这些文件
b. 使用 k8s 的&nbsp;sriov-network-device-plugin，要注意版本，高点的版本才能避免此问题。如果是mlx网卡，它会将需要的device通过 docker的 --device 挂载给container，比如下面的环境，将/dev/infiniband/uverbs2等文件挂载到container中

```
root# docker inspect 1dfe96c8eff4
```




sriov plguin 的 代码，将hostpath上的目录挂载到pod中

```
// NewRdmaSpec returns the RdmaSpec
```




sriov plguin 的 log，可看到它会把 /dev/infiniband 下面的几个文件传到pod

```
###/var/log/sriovdp/sriovdp.INFO
```


**没有特权，dpdk启动失败**
为了安全考虑，不会给pod特权，这样在pod内部启动dpdk会失败，报错如下

```
root@pod-dpdk:~/dpdk/x86_64-native-linuxapp-gcc/app# ./l2fwd -cf -n4 &nbsp;-w 00:09.0 -- -p1
```
dpdk的启动参数加上参数 -iova-mode=va，这样就不需要特权了

```
root@pod-dpdk:~/dpdk/x86_64-native-linuxapp-gcc/app# ./l2fwd -cf -n4 &nbsp;-w&nbsp;00:09.0&nbsp;--iova-mode=va -- -p1
```


**读取网卡统计计数失败**

dpdk提供了两个函数，用来获取网卡计数，rte_eth_stats_get和rte_eth_xstats_get，前者用来获取几个固定的计数，比如收发报文数和字节数，后者用来获取扩展计数，每种网卡都有它自己的计数。




对于mellanox网卡来说，它的dpdk driver mlx5也提供了对应的函数，如下

```
rte_eth_stats_get&nbsp;-&gt; stats_get -&gt; mlx5_stats_get&nbsp;
```

mlx5_stats_get 在pod内部可以正常读取计数，但是mlx5_xstats_get就会遇到问题。
mlx5_xstats_get -&gt; mlx5_read_dev_counters 这个函数会读取下面路径的文件获取计数

```
root# ls /sys/devices/pci0000\:00/0000\:00\:09.0/infiniband/mlx5_0/ports/1/hw_counters/
```




但是在pod内部同样的路径下是没有 hw_counters 目录下。因为这个目录是在加载驱动时生成，在pod内看不到。

```
root@pod-dpdk:~/dpdk/x86_64-native-linuxapp-gcc/app# ls /sys/devices/pci0000\:00/0000\:00\:09.0/infiniband/mlx5_0/ports/1/
```

可能的解决办法：

手动 mount /sys/devices/pci0000:00/0000:00:09.0/infiniband/mlx5_0/ports/1/hw_counters/ 到pod内

修改 sriov-network-device-plugin 代码，自动mount上面的目录
测试文件

```
root#&nbsp;cat&nbsp;dpdk-mlx.yaml
```
# &nbsp;参考



https://github.com/Amirzei/mlnx_docker_dpdk/blob/master/Dockerfile
https://github.com/k8snetworkplumbingwg/sriov-network-device-plugin/issues/123
https://github.com/DPDK/dpdk/commit/fc40db997323bb0e9b725a6e8d65eae95372446c
https://doc.dpdk.org/guides-18.08/linux_gsg/linux_drivers.html?highlight=bifurcation#bifurcated-driver
https://github.com/kubernetes/kubernetes/issues/60748
https://stackoverflow.com/questions/59290752/how-to-use-device-dev-video0-with-kubernetes

