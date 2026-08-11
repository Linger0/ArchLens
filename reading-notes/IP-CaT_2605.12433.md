# 论文精读：IP-CaT

## 1. 一句话总结

这篇论文提出 **IP-CaT**，通过联合优化 **L1I 跨页预取的地址翻译路径** 和 **L2 中由指令预取带入代码行的替换策略**，进一步放大现代 L1 instruction prefetcher 在大代码 footprint 服务器 workload 上的收益（摘要；Section IV；Figure 8）。

## 2. 研究背景与核心问题

### 背景

论文关注的是现代服务器 workload 的 **前端瓶颈**。作者指出，这类 workload 的 instruction footprint 很大，而且还在增长，导致前端结构如 **L1I** 和 **TLB** 承压，L1I miss 和 instruction-side TLB miss 会造成明显 stall（Section I；Section III-A）。

作者引用先前工作说明，工业服务器 workload 中，前端 stall 中相当一部分来自 **sTLB instruction miss** 与 **L1I miss**，甚至可占总执行周期的 10% 以上（Section III-A）。

### 核心问题

作者认为，现有 L1I prefetcher 已经有效，但其潜力仍被两个问题限制（Section I；Section III）：

1. **跨页 L1I 预取需要地址翻译**
   L1I prefetcher 工作在虚拟地址空间，允许跨页预取可以提升 coverage，但一旦跨页，就必须查 TLB 或触发 page walk。这个翻译延迟会削弱预取及时性（Section III-B；Figure 2）。

2. **L1I 预取带入 L2 的代码行复用差异很大**
   有些预取行是 dead-on-arrival，有些只被访问几次，少量行却非常关键、复用很多次。若统一按普通替换策略处理，会造成 L2 污染（Section III-C；Figure 3、Figure 4）。

### 为什么这很重要

这篇论文的重点不是“是否要做 L1I prefetching”，而是：**既然 L1I prefetching 已经有效，怎样把它的剩余潜力挖出来**。这使问题从“做不做预取”转向“如何让预取真正及时且不污染下层结构”。

## 3. 核心洞察与关键观察

### 观察 1：允许 L1I 跨页预取总体是值得的

作者比较了三种情形（Section III-B；Figure 2）：

- `No Page Cross`：丢弃跨页预取
- `Permit Page Cross`：允许跨页预取
- `Free Translation L1I Prefetching`：理想化地让跨页预取的翻译代价消失

结论是：

- `Permit Page Cross` consistently 优于 `No Page Cross`
- 若进一步消除翻译代价，还能继续提升性能

作者将其总结为 **Finding 1**：
允许 L1I prefetcher 跨页通常是有益的，而减少这类预取的地址翻译成本还能进一步提升性能（Section III-B）。

这是论文的第一个关键判断：**instruction stream 的跨页预取，和 data prefetch 跨页的收益逻辑并不完全一样**。作者解释原因是 instruction stream 更偏顺序/循环控制流，因此更可预测（Section III-B）。这部分属于作者明确结论。

### 观察 2：L2 中预取代码行复用是高度异质的

作者构造两个理想化实验（Section III-C；Figure 3）：

- `Ideal L2C (PGC Pref)`：只让跨页预取带入的代码行不占用 L2
- `Ideal L2C (All Pref)`：所有 L1I 预取带入的代码行都不占用 L2，直到 demand 访问才真正插入

对 EPI 来说，`Ideal L2C (All Pref)` 相比 `Permit Page Cross` 还能带来 **9.5%** 额外 speedup（Figure 3）。这说明 L2 污染是实质瓶颈。

更细的统计见 Figure 4：

- 平均 **36.1%** 的预取代码行在 L2 中从未被 demand 使用
- **51.6%** 的行只服务 **1 到 8 次** demand L2 访问
- **11.5%** 的行服务超过 **8 次**
- **0.8%** 的行服务超过 **128 次**

因此作者提出 **Finding 2**：
L1I 预取带入 L2 的代码行复用行为差异很大，需要能预测复用价值的策略（Section III-C）。

### 观察 3：问题集中在“预取带入的代码行”，不是所有 instruction line

作者明确说，他们**不针对 demand 带入 L2 的代码行做同样管理**，因为分析显示这部分相对已有工作提升空间较小（Section III-C）。后文也用消融实验支持：把策略同时用于 demand 和 prefetch 代码行反而更差（Section VI-C；Figure 17）。

这是很重要的设计边界：**IP-CaT 不是通用 instruction cache replacement policy，而是 instruction-prefetch-centric policy。**

## 4. 技术方案与机制设计

### 4.1 总体结构

IP-CaT 包含两个模块（Section IV）：

1. **tPB（translation Prefetch Buffer）**
   解决 L1I 跨页预取的翻译延迟问题。

2. **TIPRP（Trimodal Instruction Prefetch Replacement Policy）**
   解决 L1I 预取行在 L2 中的污染与保留问题。

作者强调两者是协同的：tPB 减少 page walk 与翻译开销，TIPRP 减少 L2 污染并保住真正有价值的预取代码行（Section IV；Figure 7）。

### 4.2 tPB：面向跨页 L1I 预取的翻译缓冲

#### 核心思想

tPB 是一个放在 **sTLB 旁边**的小 buffer，只存放 **由 L1I 跨页预取触发 page walk 后得到的 instruction PTE**（Section IV-A；Figure 5）。

关键点：

- **L1I page-cross prefetch miss in iTLB/sTLB 时**，再查 tPB
- 若 tPB hit，则把对应翻译插回 sTLB，并失效该 tPB entry
- 若 tPB miss，则发起 prefetch page walk
- 这个 page walk 得到的翻译写入 **iTLB 和 tPB**，**不写 sTLB**，避免污染 sTLB（Section IV-A）

#### 为什么这样有效

如果把预取触发得到的翻译直接塞进 sTLB，会污染 demand translation 的工作集。tPB 的设计本质上是：

- **允许预取提前把翻译“抓回来”**
- **但不让这些 speculative translation 占据正式 sTLB 容量**

等之后 demand instruction miss 或新的 L1I prefetch 真的需要这个翻译时，再从 tPB 转入 sTLB（Section IV-A）。

这相当于给 instruction prefetch 的 translation 建了一个“旁路暂存区”。

#### 硬件代价

为了区分“这个 miss 是不是由 L1I page-cross prefetch 发起”，作者在 **sTLB MSHR** 上增加 1 个 `cb`（cross-bit）位（Section IV-A）。这是 tPB 能只拦截“预取发起的翻译”而不影响普通 demand translation 的关键。

#### 与 sTLB 的集成

作者进一步指出，tPB 不必一定做成独立结构，也可以通过扩充若干 set 的方式集成到 sTLB 中（Section IV-A1）。后文敏感度实验显示，这样做的性能接近独立 tPB（Section VI-E；Figure 20）。

### 4.3 TIPRP：专门管理 L1I 预取代码行的 L2 替换策略

#### 核心思想

TIPRP 不是单一策略，而是三种策略的动态切换（Section IV-B；Figure 6）：

1. **PIP（Prioritize Instruction Prefetch）**
   优先保留由 L1I prefetch 带入 L2 的代码行。
2. **NPIP（Non-Prioritize Instruction Prefetch）**
   让这些预取代码行更容易被淘汰。
3. **BIP（Bypass Instruction Prefetch）**
   对这类预取代码行直接 bypass，不插入 L2。

作者的判断是：由于预取行价值高度不一致，所以不存在单一最优策略；最优动作取决于 program phase（Section IV-B）。

#### 三种策略分别在解决什么

- **PIP**：适合“预取行未来有高复用”的阶段，避免关键代码行被过早驱逐。
- **NPIP**：适合“预取有些用，但不值得强保护”的阶段，给预取行较低优先级，减少污染。
- **BIP**：适合“很多预取行根本没用”的阶段，直接不让它们占 L2。

#### 为什么是 decision tree，而不是普通 set dueling

TIPRP 用两个饱和计数器 `PSEL1`、`PSEL2` 形成两级决策树（Section IV-B3；Figure 6）：

- 如果 `PSEL1 > T1`，选 `PIP`
- 否则再看 `PSEL2`
  - `PSEL2 > T2` 选 `NPIP`
  - 否则选 `BIP`

缓存集合被划分为：

- `Leader Sets for PIP`
- `Leader Sets for NPIP`
- `Leader Sets for BIP`
- `Follower Sets`

Follower set 用计数器选择当前最优策略（Section IV-B3）。

相对传统 set dueling，这里有两个增强点：

1. **不只在 eviction 时训练，也在 hit 时训练**
2. **训练时区分该行是否由 L1I prefetch 带入**

#### `pb` 位的作用

TIPRP 依赖每个 L2 cache line 上的 `pb`（prefetch bit）来标记它是否由 L1I prefetch 带入（Section IV-B3）。如果底层设计没有这个位，作者要求在 L1I MSHR 和 L2C MSHR 中传递该元信息（Section IV-C；Figure 7 附近）。

#### 一个重要的工程判断

作者特意把 PIP 放在 **eviction 时生效**，而 NPIP/BIP 放在 **insertion 时生效**（Section IV-B2）。这是因为：

- PIP 的目标是“保护”已有预取行，所以在 eviction 时更直接
- NPIP/BIP 的目标是控制“新来的预取行是否值得放入/高优先级放入”，所以在 insertion 时更自然

## 5. 实验设置与性能结果

### 5.1 实验平台

根据 Table I 和 Section V：

- 模拟器：**ChampSim**
- 核心：OOO，**6-wide issue**
- 频率：**4GHz**
- ROB：**352-entry**
- FTQ：**128-entry**
- iTLB/dTLB：**64-entry, 4-way**
- sTLB：**1536-entry, 12-way, 8 cycles**
- L1I：**32KB, 8-way, 4 cycles**
- L2：**1MB, 16-way, 10 cycles**
- LLC：**1.375MB/core, 11-way, 36 cycles**

页表部分，文中同时提到 **5-level radix tree page table**，但 Table I 写的是 **4-level Split PSC**；这里并不矛盾，后者是 page structure cache 配置。若进一步问 page walk 细节层级，当前材料能确认的是作者模拟了 x86 page-table walker 与 MMU caches（Section V）。

### 5.2 Workload

- **105 个单核 server workloads**
- **160 个 4-core mixes**（60 homogeneous + 100 heterogeneous）
- **75 个 SMT workload pairs**（Section V）

作者只保留 instruction sTLB MPKI 至少 0.5 的单核 workload 进入主单核集合（Section V）。这意味着主结果更偏向 **instruction-side TLB 压力明显** 的场景。

### 5.3 对比对象

作者评估了多类 state-of-the-art policy（Table II）：

- TLB 侧：`CHiRP`, `Morrigan`
- code-aware cache：`CLIP`, `EMISSARY`
- prefetch-aware/general-purpose cache：`PACIPV`, `PACMAN`, `SRRIP`, `DRRIP`, `SHiP++`, `Mockingjay`
- 以及 `TIPRP`、`tPB`、和各种 `tPB + baseline-policy` 组合

### 5.4 主结果

#### 单核结果

Figure 8 / Section VI-A：

- `TIPRP` 单独使用时，对
  - EPI：**2.9%**
  - Barca：**4.8%**
  - FNL+MMA：**5.0%**
  的 geomean speedup
- `IP-CaT = tPB + TIPRP` 时，对
  - EPI：**6.1%**
  - Barca：**8.3%**
  - FNL+MMA：**7.9%**
  的 geomean speedup

而且作者明确说，IP-CaT 超过了 CHiRP、Morrigan、CLIP、EMISSARY、PACIPV、PACMAN、DRRIP、SHiP++、Mockingjay，以及这些方案再与 tPB 组合后的结果（Section VI-A；Figure 8）。

#### 对非 TLB-intensive workload 的影响

作者额外去掉 MPKI 过滤，在 788 个 workload 上比较 `IP-CaT` 和 Figure 8 中最佳基线 `tPB+SRRIP`（Figure 9）：

- 对 EPI，IP-CaT 仍比 `tPB+SRRIP` 高 **2.9%** geomean

说明它不是只在筛选后的强 TLB 压力 workload 上才成立（Section VI-A）。

#### 多核结果

Section VI-H；Figure 23：

- 在 160 个 4-core mixes 上，IP-CaT 仍优于所有对比方案
- 以 EPI 为例，相对 CHiRP / Morrigan / CLIP / EMISSARY / PACIPV / SHiP++ / Mockingjay，分别高 **7.2% / 6.8% / 7.8% / 9.1% / 9.3% / 9.0% / 14.2%**

#### SMT 结果

Section VI-I；Figure 24：

- 在 75 个 SMT workload pairs 上，趋势与单线程类似，但绝对收益更高
- 以 EPI 为例，IP-CaT 相对 CLIP / PACIPV / PACMAN 分别高 **7.1% / 9.3% / 10.3%**

作者解释原因是 SMT 下 sTLB 和 L2C 竞争更强，因此方案收益被放大（Section VI-I）。

## 6. 瓶颈归因与设计权衡

### 6.1 新方案到底缓解了什么瓶颈

#### tPB 缓解的是 instruction-side translation latency

Section VI-A1；Figure 10、Figure 11：

- sTLB MPKI（定义为 miss in sTLB and tPB）下降：
  - EPI：**31.6%**
  - FNL+MMA：**18.2%**
  - Barca：**32.3%**

这说明大量原本会触发 page walk 的 demand sTLB miss，被 tPB 吸收了。

#### TIPRP 缓解的是 L2 污染与下游 miss 成本

作者观察到：

- TIPRP 改善了预取代码行在 L2 的管理
- LLC misses 减少
- 同时 L2C/LLC/sTLB 的 average miss latency 下降（Section VI-A1；Figure 10、Figure 11）

这里有个很关键的工程点：**TIPRP 不一定总让 L2 MPKI 下降。** 文中给出：

- EPI：L2 指令 MPKI **+6.5%**
- Barca：**+5.1%**
- FNL+MMA：**-8.1%**

但即便有时 L2 MPKI 上升，整体性能仍提高，因为：

1. 更差的行被 bypass / 更早淘汰，降低了污染
2. 真正关键的预取行被保住
3. tPB 减少 page walk，又反过来减轻 L2/LLC 压力

所以这篇论文的收益逻辑不是“让所有层 miss 都更少”，而是**让更有价值的内容占据更稀缺的层级资源**。

### 6.2 两个模块之间有协同效应

Section VI-C；Figure 15、Figure 16：

在 EPI 下：

- `tPB`：**2.9%**
- `TIPRP`：**2.9%**
- 两者相加不是简单 5.8%，而是 `IP-CaT` 达到 **6.1%**

作者解释为：tPB 减少了 page walk，而 page walk 本身会访问 L2C，因此 tPB 也降低了 L2 竞争，使 TIPRP 更有效（Section VI-C）。

### 6.3 成本与复杂度

#### 存储开销

Section IV-C / Section V 前：

- 总额外存储：**0.79KB**
  - 64-entry tPB：**6452 bits**
  - sTLB MSHR `cb` 位：**16 bits**
  - `PSEL1`：**10 bits**
  - `PSEL2`：**10 bits**

作者说这只相当于 L2 容量的 **0.08%**，能耗影响可忽略。

#### 复杂度代价

原文没有给出门级时序、面积布局图或关键路径分析。因此：

- **关键路径影响：原文未说明**
- **TIPRP 命中/替换逻辑是否增加 L2 access latency：原文未说明**
- **验证复杂度：作者未量化**

不过从结构上看，tPB 和 TIPRP 都属于较小状态机、位标记、局部选择器级别，属于相对克制的微架构增强。这是基于原文机制的合理工程判断，不是作者直接量化结论。

## 7. 优势、局限与适用边界

### 7.1 方案最强的地方

1. **定位非常准确**：它不是泛化做大 TLB 或做更复杂替换，而是专门围绕“L1I 预取的剩余损失”展开。
2. **模块正交性强**：tPB 管翻译，TIPRP 管 L2 预取代码行，职责清晰。
3. **对多个强 prefetcher 都有效**：EPI、Barca、FNL+MMA 都受益，说明不是绑定单一预测器（Section VI）。
4. **在多核和 SMT 下仍成立**：这点对服务器场景尤其关键（Section VI-H、VI-I）。

### 7.2 作者明确给出的局限或边界

#### 大页会削弱收益

Section VI-G；Figure 22：

- 当 2MB page 比例提升时，IP-CaT 收益下降
- 以 EPI 为例，speedup 从 **7.5%**（0% large pages）降到 **1.8%**（100% large pages）

原因是 large page 减少了 sTLB miss，tPB 的空间被压缩；同时整体 translation 压力下降，TIPRP 的相对价值也会降低。

#### LLC 越大，相对收益越小

Section VI-F；Figure 21：

- EPI 下，LLC 从 1MB 增到 4MB 时，IP-CaT speedup 从 **12.7%** 降到 **2.6%**

作者解释是大 LLC 能容纳更多 working set，降低 miss rate，使 L2 replacement policy 的重要性下降。

#### 不适合同时管 demand instruction line

Section VI-C；Figure 17：

- 把 TIPRP 同时应用到 demand 和 prefetch instruction line（IP-CaT D+P）会变差
- 在 EPI 下，IP-CaT 比 IP-CaT D+P 高 **10.1%**

这说明该策略的成功依赖于一个边界：**只针对 prefetch-inserted code lines**。

### 7.3 工程上还需要额外关注的问题

以下属于基于原文的工程推断，不是作者明确实验结论：

- 若真实产品中 L2 tag pipeline 很紧，TIPRP 的决策逻辑是否会压关键路径，需要实现验证
- 若系统有更复杂的 TLB shootdown / page migration / virtualization 机制，tPB 的一致性处理可能要细化。论文只说“将 tPB 纳入 shootdown 过程即可”，但没有展开 OS/hypervisor 级实现细节（Section IV-C）
- 对 chiplet、多 socket、NUMA 的影响，原文未说明
- 对更宽发射、更深 front-end pipeline 的适配，原文未说明

## 8. 对微架构设计的启示

### 这篇论文给出的新判断

最重要的不是“再做一个 instruction prefetcher”，而是：

- **instruction prefetch 的收益很大程度上取决于 translation 配套**
- **预取行的 cache 管理不能沿用统一的替换策略**
- **前端优化要把预取、TLB、L2 视为耦合系统，而不是孤立模块**

### 设计 checklist

如果要做类似设计，建议优先检查：

- L1I page-cross prefetch 的比例有多高
- page-cross prefetch 的 sTLB miss / page walk 代价有多高
- 由 L1I prefetch 带入 L2 的代码行中，dead-on-arrival 比例是多少
- 这些预取行的 demand reuse 分布是否呈明显长尾
- page walk 对 L2/LLC 流量和平均 miss latency 的贡献有多大
- large pages 会不会已经把 translation 压力基本消掉

### 最值得调的参数

基于原文，最值得优先调的是：

- `tPB` 容量与组织方式。64-entry 被作者选为 practical sweet spot（Section VI-D）
- TIPRP 的 leader set 分配与 `PSEL1/PSEL2` 位宽。论文给出经验配置，但没有做大范围参数搜索报告
- 是否把 tPB 集成进 sTLB。实现上更实用，性能接近独立 tPB（Section VI-E）

### 复现/扩展优先方向

1. 先复现 Figure 2/3/4，验证论文的两个核心动机是否在你的 workload 上成立
2. 再分别实现 tPB 和 TIPRP，做消融
3. 最后再考虑与其他 front-end 机制联动，例如：
   - code layout optimization
   - 更强的 indirect branch predictor
   - instruction-side TLB replacement / prefetch 协同

## 9. 总结

IP-CaT 的本质贡献，是把 **“L1I prefetch 已经有效，但还没吃满收益”** 这个问题拆成两个可落地的微架构瓶颈：

- **跨页 instruction prefetch 的地址翻译延迟**
- **预取代码行在 L2 中的价值分化与污染**

为此，论文提出：

- 用 **tPB** 暂存由 L1I page-cross prefetch 带来的 translation，减少 page walk，又避免污染 sTLB
- 用 **TIPRP** 按 phase 在 `PIP / NPIP / BIP` 三种模式之间切换，专门管理由 L1I prefetch 带入 L2 的代码行

从工程视角看，这篇论文最有价值的启示是：**前端预取优化不能只盯 prefetcher 本身，translation path 和 lower-cache residency policy 往往同样决定最终收益。**

如果继续追问，最值得深入的是三点：

1. TIPRP 在真实时序约束下的实现代价
2. tPB 与更复杂虚拟内存机制的交互细节
3. 在 large-page 普及、超大 LLC、或更激进前端架构下，IP-CaT 的收益是否还稳定
