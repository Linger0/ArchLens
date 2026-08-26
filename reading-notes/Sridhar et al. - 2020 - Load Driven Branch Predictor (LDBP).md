# Load Driven Branch Predictor (LDBP) 论文精读

> 论文：Akash Sridhar, Nursultan Kabylkas, Jose Renau, “Load Driven Branch Predictor (LDBP)”，2020。
>
> 阅读材料：原始 PDF、MinerU 全文 Markdown、MinerU JSON 及图像资源。文中“原文事实”均对应论文章节、图表或 Listing；“合理解释”是基于这些证据的架构分析；“工程扩展”不是论文已经验证的结论。

## 1. 一句话总结

LDBP 针对“分支结果取决于随机 load 数据、但 load 地址具有可预测步长”的分支，在退休阶段识别 load-branch backward slice 并提前发起真实 load，在取指阶段利用已经到达的 load 数据预计算分支结果；在 ESESC 的 Zen 2-like 配置上，它以 81 Kbit 的附加结构显著降低这类分支的 MPKI，并允许缩小主 IMLI 预测器。

## 2. 研究背景与核心问题

### 2.1 历史型预测器的剩余盲区

**原文事实。** 论文把分支误预测和数据 cache miss 视为限制单线程性能的两个主要因素（I）。TAGE 类预测器依赖历史相关性；当分支结果由近期 load 的随机数据决定时，结果历史可能过于任意或过长，难以被历史表捕获。论文引用 CBP-5 数据称，TAGE 从 64 Kbit 扩展到无限容量时，MPKI 仅从 3.986 降到 2.596；论文还指出，256-Kbit 预测器相对无限容量版本的误预测只多约 10%（I）。

**核心问题。** 扩大历史存储并不能直接恢复“当前 load 实际读到的值”。论文的关键观察是：数据值可以随机，但承载数据的地址在数组、map 等数据结构中经常呈现可预测的 stride。也就是说，预测对象应从“只预测分支结果”扩展为“提前获取会决定分支的输入，再计算分支结果”。

### 2.2 代表性场景

论文 Listing 1 遍历一个元素为随机 0/1 的向量：数组索引通过 `addi` 以固定增量推进，`lw` 的地址可预测，但紧随其后的 `bnez` 结果由随机数据决定。传统 TAGE 难以学习这种结果序列；LDBP 则可以提前触发后续 `lw`，在分支取指时使用其真实数据。论文在该示例上报告，将 LDBP 加到 Zen 2-like core 的 256-Kbit IMLI 后，IPC 提升 2.6 倍（I）。这个数字属于论文示例，不应外推为所有 workload 的平均收益。

## 3. 核心洞察与关键观察

### 3.1 地址可预测性与数据可预测性是两个不同维度

**原文事实。** LDBP 的目标不是预测随机 load data，而是利用 stride predictor 预测 load address，提前执行该 load，并用实际读出的值计算分支。LDBP 只对默认 IMLI 低置信度、且依赖 load-branch chain 的分支启用；其他分支仍由默认预测器处理（I）。

**合理解释。** 这相当于把 branch predictor 的输入从“分支历史”扩展为一条受限的数据依赖路径：地址规律负责提供时间，真实 load data 负责提供值。若地址规律消失，LDBP 既不能可靠地提前取数，也不应继续产生触发 load。

### 3.2 LDBP 能捕获的依赖链有明确边界

论文把链分为三类：

- trivial chain：分支源操作数直接来自一个或多个可预测 load；
- complex chain：load 与分支之间有简单 ALU 操作；
- load-load chain：一个 load 的地址由前一个 load 的数据决定。

当前实现只保留由可预测 load 或立即数开始、且操作数和 load 数量不超过阈值的 backward slice。复杂 ALU 操作会使 RTT 项失效；load-load chain 当前不支持。论文强调，分析的 hard-to-predict 分支中有相当比例属于 trivial chain（II-A）。

![通用 load-branch chain](../artifacts/sridhar-2020-load-driven-branch-predictor-ldbp/images/302b2f4ecf88ba8a8abde5a3eda5ccbbadadfec8e0b6be70d159b829ab7333b6.jpg)

### 3.3 及时性是正确预测的必要条件

load 通常紧邻依赖分支，按正常程序顺序执行时，分支取指已经发生而 load data 尚未返回。因此 LDBP 的性能不只取决于“地址能否预测”，还取决于 trigger load 是否在分支取指之前完成。

**原文事实。** 论文使用退休时生成 trigger load 的方式，借助 stride 预测把请求推到未来，并通过 `tl_dist` 调节距离。示例中 load latency 为 6 cycles、load 地址 delta 为 8 时，要达到 IPC=1，至少需要提前 16 cycles 发起地址 `x + 8 * 16` 的 load（IV-E）。trigger load 是真实 load，不是可能被丢弃的普通 prefetch。

**合理解释。** 预取距离存在双向风险：太短会导致 BOT 没有有效结果，太长则需要更大的缓冲，stride 改变时会产生无用访问，还可能污染 cache、驱逐有用 cache line。该机制的关键设计点因此是“用可预测地址换取足够的提前量”，而不是单纯增加预测表容量。

## 4. 技术方案与机制设计

### 4.1 两个时序位置

![LDBP retirement block](../artifacts/sridhar-2020-load-driven-branch-predictor-ldbp/images/891f03f8841ee344bda252e2f780c5e47aa678a6552677f100f449b07d1e0644.jpg)

![LDBP fetch block](../artifacts/sridhar-2020-load-driven-branch-predictor-ldbp/images/e361affa2ff0b1a327010d43e16b96526344599dbf271d5c5dc44d0b9b9800ac.jpg)

论文将 LDBP 分成 retirement block 和 fetch block：

1. retirement block 只使用已退休的非猜测信息，识别依赖链、建立 backward slice，并在条件满足时生成未来 trigger load。
2. fetch block 保存 trigger load 的返回值，运行 slice 对应的有限状态机（FSM），将未来分支结果放入 BOT，分支取指时直接消费已经有效的 outcome。

这种分工把“学习与安全状态更新”和“低延迟预测消费”分开，避免在每次退休指令上持续做完整 slice 构建。

### 4.2 Retirement block 的结构

![LDBP flow](../artifacts/sridhar-2020-load-driven-branch-predictor-ldbp/images/6f63805a389563c65f3827a2556cf6bbbf392bee5f0c6b7e91802483e2f7cb0b.jpg)

- **Stride Predictor（SP）**：按 load PC 记录 tag、上次退休地址、地址 delta、delta confidence 和 tracking bit。只有 confidence 饱和且该 load 已被纳入链时，才允许它成为 trigger load。
- **Rename Tracking Table（RTT）**：按逻辑寄存器跟踪依赖链中的操作数数量和 SP 指针列表。简单 ALU 退休时，按源寄存器累计操作数；超过 load/operation 阈值则使该项失效。
- **Branch Trigger Table（BTT）**：按分支 PC 关联 load 列表，并记录 LDBP 对该分支的准确性。只有同时满足“所有 load 地址可预测、分支对 IMLI 低置信度、链长度在阈值内”才分配 BTT 项。
- **Code Snippet Builder（CSB）**：在建立 BTT 项时构建 load 到 branch 的操作序列；论文特意没有把 CSB 与 RTT 合并，以避免 RTT 持续更新带来的额外功耗。
- **Pending Load Queue（PLQ）**：延迟 trigger load 生成，并在分支退休前检查所跟踪 load 的 delta 是否发生变化。变化时停止触发，以避免用旧 stride 产生错误访问。

### 4.3 Fetch block 的结构

- **LOR/LOT**：LOR 记录可供当前及未来分支使用的 load 地址范围和 delta；LOT 保存这些地址对应的完整 load data 及 valid 位。地址落在范围内且满足 stride 对齐时，完成的 trigger load 才会被写入 LOT。
- **BOT**：按分支 PC 保存预计算的 1-bit outcome 队列、valid 位、关联 load 指针和 CST 指针。取指命中 BOT 且 outcome 有效时，BOT outcome pointer 指向的结果就是预测值；该 pointer 是 fetch block 中唯一被投机更新的值。
- **CST/FSM**：CST 保存已建立的 backward slice。当关联 load data 都有效时，FSM 每周期执行一个 ALU 操作，完成后把结果写入 BOT 的未来 outcome 队列。

### 4.4 从链建立到预测的流程

1. load 退休时更新 SP；若已被跟踪，则把对应指针放入 PLQ，同时用高 confidence 的 load 初始化 RTT。
2. 简单 ALU 退休时合并源寄存器对应的 RTT 项，累计操作数和 load 指针。
3. 低置信度分支退休时检查 RTT。如果链满足阈值且所有 load 地址可预测，则分配 BTT、PLQ、LOR/LOT、BOT，并启动 CSB。
4. 后续同一分支退休时，BTT 根据 PLQ 和 LOR 状态生成未来 trigger load。论文给出的地址形式为 `tl_addr = lor.ldstart + lor.delta * tl_dist`。
5. trigger load 完成后写入匹配的 LOT 数据队列并置 valid；CST FSM 使用这些值计算未来 branch outcome。
6. 分支取指时，BOT 消费有效 outcome；发生误预测、链变化或 load delta 变化时，清空相关 fetch 状态并从 retirement block 重建。

### 4.5 安全性设计

**原文事实。** retirement block 只在指令非投机退休后更新；fetch block 只从 retirement block 获取信息；trigger load 在安全目标分支退休后发起；LOR 虽可能投机更新，但在 pipeline flush 后清空。论文据此认为 LDBP 结构本身不会像投机更新且不修复的预测器那样新增 speculative leak，但投机路径上的 load 仍需由其他机制保护（II-D）。

## 5. 实验设置与性能结果

### 5.1 实验设置

**原文事实。** 论文使用 ESESC timing simulator，配置接近 AMD Zen 2。SPEC CINT2006 跳过 8 billion instructions、建模 2 billion instructions，只选基线 IMLI 预测准确率低于 95% 的 `hmmer`、`astar`、`gobmk`；GAP 使用 `-g 19 -n 30`，跳过初始化。所有 benchmark 用 gcc 9.2、`-Ofast -flto` 编译为 RISC-V RV64。基线采用 1-cycle fast branch predictor 加 2-cycle、较准确的 IMLI predictor，并比较 150-Kbit、256-Kbit、1-Mbit IMLI 与 81-Kbit LDBP 的组合（III）。

基线选择本身限定了结论范围：作者刻意排除了原本 MPKI 已很低的 SPEC 程序，因此结果反映的是 LDBP 对“难预测分支子集”的收益，而不是 SPEC CINT2006 全集的平均收益。

### 5.2 总体结果

![相对基线的 IPC 结果](../artifacts/sridhar-2020-load-driven-branch-predictor-ldbp/images/58de6980ff39732458c48d4fb4c0e0ed96ce788b1d777a0475df6104ded60dbb.jpg)

**原文事实。** 相对 standalone 256-Kbit IMLI：

- 256-Kbit IMLI + LDBP：平均 MPKI 降低 22.7%，平均 IPC 提升 13.7%；GAP 和 SPEC CINT2006 的 MPKI 分别降低 17.9% 和 27.5%（IV）。
- 150-Kbit IMLI + LDBP：分支误预测降低 20%，IPC 提升 13.1%，硬件预算比 standalone 256-Kbit IMLI 低 9.7%。150-Kbit IMLI 本身比 256-Kbit 小约 41%，但 LDBP 组合后的 MPKI/IPC 接近或在个别 benchmark 超过较大组合。
- standalone 1-Mbit IMLI 相对 baseline 256-Kbit IMLI 只修复 9.7% 的分支 miss，说明仅扩展历史型预测器容量对该类 data-dependent branch 的帮助有限。

这里的“提升”都是论文在其 ESESC 配置和筛选 benchmark 上的平均值，不能直接解释为硬件芯片上的保证收益。

### 5.3 代表性 benchmark

| 案例 | 原文观察 | LDBP 结果 | 归因 |
|---|---|---:|---|
| GAP BFS | 最易错分支约占全 benchmark 误预测的 30% | 该分支约 94% 的误预测被修复；总体 MPKI 降 59%，speedup 38% | 图节点遍历顺序可预测，但 `parent[u]` 数据和分支结果不规则 |
| SPEC HMMER | 目标 `bge` 约占全部误预测的 39% | 修复该分支 67% 的误预测；IPC 提升 29%，总体 MPKI 降 56% | 两个分支源操作数各依赖两个、地址可追踪的 load，共跟踪四个 load 和中间 ALU 操作 |
| SPEC ASTAR | 最易错分支约占误预测 22% | 无法修复该分支，但总体 miss 仍降 25.4% | 该分支依赖的 load 地址 delta 波动，不能形成稳定 trigger load |
| GAP CC | 目标分支略高于全误预测的三分之一 | 当前 LDBP 无法捕获该链 | recipient load 的地址由 donor load 的数据决定，属于当前不支持的 load-load chain |

这些案例说明，LDBP 的收益来自匹配的依赖形态和地址规律，而不是仅仅因为分支“难预测”。

## 6. 瓶颈归因与设计权衡

### 6.1 主要瓶颈转移

**原文事实。** LDBP 缓解的是前端分支误预测造成的 flush 和错误路径执行，并提高可用的 MLP；它没有解决所有 load latency 或 cache miss。论文还报告，LDBP 平均使 DL1 access 增加 10.9%，因此内存子系统访问能耗会上升（IV-C）。

**合理解释。** 机制把瓶颈从“无法知道 branch outcome”部分转移到三个条件：stride 学习是否稳定、trigger load 是否及时、LOT/BOT/FSM 是否有足够容量。若 memory bandwidth 紧张或 delta 改变，LDBP 可能在正确性保护下停止触发，收益下降。

### 6.2 容量与关键参数

作者用“除被测表外其他表均设为 512 entries”的近似无限 LDBP，采用相对无限配置 MPKI 增加不超过 2% 作为 sizing cutoff（IV-B）。得到的 81.06-Kbit 结构如下：

| 结构 | entries | 大小（Kbit） |
|---|---:|---:|
| Stride Predictor | 48 | 2.39 |
| RTT | 32 | 3.09 |
| PLQ | 48 | 0.33 |
| BTT | 8 | 0.88 |
| CSB | 32 | 4 |
| LOR | 16 | 1.44 |
| LOT | 16 | 65 |
| BOT | 8 | 1.93 |
| CST | 8 | 2 |
| **Total** |  | **81.06** |

作者的敏感度结论是：SP/PLQ 各 48 entries；LOR/LOT 各 16 entries；BOT 的 outcome queue 和 LOT data queue 各 64 entries；BTT/BOT 各 8 entries；链最多跟踪 5 个 load、3 个 ALU operation，CSB 每个逻辑寄存器索引保留 4 个子项。LOT 占绝大多数容量，可使用面积效率更高的 single-port SRAM（IV-B）。

### 6.3 能耗与性能的交换

**原文事实。** 论文用 CACTI 6.0 估算 EPA，模型中 LDBP 的 EPA 比 IMLI 低 55%；但触发真实 load 使 DL1 access 平均增加 10.9%。作者没有把减少错误路径执行和 13.3% 较短执行时间带来的节能计入 LDBP 的估算，因此其模型对 LDBP 偏保守。通过连续 100,000 cycles 没有预测到分支来进入低功耗模式，除 SP 和 RTT 外关闭 LDBP 组件；LDBP 平均有 38.5% 的执行时间处于该模式。

**需要注意的反例。** `bc` 和 `sssp` 几乎不使用 LDBP，低功耗模式占比分别为 99.5% 和 98.2%；`gobmk` 虽然几乎没有预测收益，却因多个分散的低频分支使能耗增加 8%。这说明 gating 能缓解低利用率，但不能自动解决跨阶段、低频命中的控制开销。

![能耗-性能权衡](../artifacts/sridhar-2020-load-driven-branch-predictor-ldbp/images/3c4f79873073d1b02f1c9ee9a50a737de9b2f0f2520becef6ecf6f389e4f54b9.jpg)

## 7. 优势、局限与适用边界

### 7.1 优势

- 对随机 data-dependent branch，直接使用实际 load value，绕开了历史序列不可学习的问题。
- 不需要修改 ISA 或编译器；链和阈值由硬件运行时识别。
- 只在默认预测器低置信度且地址可预测时启用，避免把 LDBP 变成所有分支的并行高功耗路径。
- 结构总容量小于主 256-Kbit IMLI；150-Kbit IMLI + LDBP 还展示了容量替代空间。
- retirement-only 学习和 flush 机制降低了新增 speculative state 的安全风险。

### 7.2 作者明确的局限

- 当前不支持 load-load chain；GAP CC 正是失败案例。
- 同一分支可能有多个 runtime 生成的 backward slice。论文认为在 GAP 中不常见、在 SPEC 中略多，但承认其他 workload 可能更严重，并留作 future work。
- 复杂 ALU、乘法和浮点操作不受支持；链太长也会失效。
- stride 改变需要重新学习；论文在 `tc` 中观察到不可预测或延迟的 load 占比较大，并提出 memory bandwidth congestion 也是可能原因。
- trigger load 不是普通 prefetch，过远会增加 buffer 压力和 cache pollution；过近又无法保证数据及时到达。

### 7.3 适用边界

**原文支持较强的场景：** 数组/向量顺序遍历、map 或图结构中地址访问规律而数据值不规律的循环，尤其是目标分支位于大循环入口或循环体中，能够给 LDBP 留出学习和预取距离。

**合理推断的低收益场景：** 间接寻址由前一个 load 的数据决定、stride 经常改变、内存带宽已经饱和、链跨越较多复杂操作，或目标分支低频且分散在多个阶段。这些判断分别由 CC、ASTAR、TC 和 GOBMK 的结果支持，但论文没有在更广泛 workload 上系统验证。

**原文未验证的工程边界：** 更宽发射、更深流水线、多核/SMT 共享预测器、真实工业实现的时序和面积布线约束，以及现代安全策略下真实 load 的隔离成本。不能仅凭论文的 Zen 2-like simulator 结果确认这些场景的收益。

## 8. 对微架构设计的启示

### 8.1 设计检查清单

1. 对剩余 branch miss 做依赖分析：分支源操作数是否来自近期 load？load data 是否难以预测？
2. 单独测量 load address delta 的稳定性，不要用 data randomness 代替 address predictability。
3. 统计 backward slice 的 load 数、简单 ALU 数、链跨分支比例和多路径比例，先确认目标 workload 落在硬件阈值内。
4. 用 load latency、前端推进速度、in-flight iteration 数量和 delta 计算所需 trigger distance。
5. 分别做 capacity 和 timeliness ablation：SP/PLQ、LOT data queue、BOT outcome queue 的容量瓶颈并不相同。
6. 把真实 load 带来的 DL1 access、带宽、cache pollution、错误路径减少和执行时间缩短放到同一能耗模型中。
7. 明确所有投机更新字段的 flush/rebuild 规则，并验证 trigger load 在安全模型中的可见性。

### 8.2 复现或扩展优先级

**原文基础上的复现优先级：** 先复现 256-Kbit IMLI、150-Kbit IMLI 和 1-Mbit IMLI 的 MPKI/IPC 对比，再分别复现 BFS/HMMER/CC 三个依赖链案例，最后复现 trigger timeliness、表项容量和 gating 实验。这样可以把“机制有效”“容量足够”“及时性成立”三个因素分开验证。

**工程扩展（非论文结论）：** 首先值得扩展的是 load-load chain，因为它直接覆盖 CC 类失败模式；其次是动态调整 trigger distance 和对 memory pressure 感知的 gating；再次是多路径分支的 slice 版本管理。每项扩展都应同时报告误预测、额外 DL1/带宽访问、LOT/BOT occupancy、能耗和安全 flush 次数，避免只报告 IPC。

## 9. 总结

LDBP 的本质贡献是识别出一个历史型分支预测器难以处理、但地址驱动机制可以利用的分支类别：结果数据随机，地址规律。它在退休阶段建立受限的 load-branch slice，在未来迭代中提前执行真实 load，再由取指侧用 LOT 中的实际数据计算并缓存 branch outcome。

论文结果表明，81-Kbit LDBP 在筛选出的 SPEC CINT2006 和 GAP workload 上能够显著降低 MPKI；256-Kbit IMLI + LDBP 平均 MPKI 降 22.7%、IPC 提升 13.7%，150-Kbit IMLI + LDBP 相对 standalone 256-Kbit IMLI 达到 20% 更少误预测和 13.1% IPC 提升。最重要的工程判断不是“LDBP 应该替代历史预测器”，而是：应先确认 workload 是否同时具有稳定 load 地址、足够的预取距离和可容纳的依赖 slice；否则额外的真实 load 只会增加内存系统压力而没有预测收益。
