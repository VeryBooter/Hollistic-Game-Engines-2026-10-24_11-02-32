# 模块接入记录

2026-10-24，在当前原生 Apple Silicon Mac 上实际获取、构建和运行。精确提交见 `dependencies.lock.json`；每一步的布尔状态见 `evidence/status.json`。`built_from_source` 与 `installed_binary_wheel` 分开记录，避免将 wheel 安装说成本机源码构建。所有默认启用模块均有真实求解器，不使用替代数学公式冒充上游。

## 已运行并接入

### JSBSim 1.2.3

来源：[JSBSim-Team/jsbsim](https://github.com/JSBSim-Team/jsbsim)。飞行动力学、推进、控制系统与大气模型，LGPL-2.1-or-later。固定源码已获取，CMake 原生静态库/命令行已构建；命令行 `scripts/c1721.xml --end=0.1` 已运行。统一适配器使用相同版本的哈希锁定 Python 原生 wheel，真实载入 `c172p` 并推进状态。

复现：`python3 scripts/build.py jsbsim`，以及 `.venv/bin/python -m physim run jsbsim`。原生程序运行：`install/jsbsim/bin/JSBSim --root=external/jsbsim --script=scripts/c1721.xml --end=0.1`。

与 CoolProp 的单向数据交换已验证：时间/温压保持、单位转换以及高度扰动后密度改变。它尚未接入 Chrono 的刚体状态反馈，避免双重积分。

### Project Chrono 9.0.1

来源：[projectchrono/chrono](https://github.com/projectchrono/chrono)。BSD-3-Clause；CPU 刚体、多体和 FEA 等核心已原生构建并安装，最小适配器只验证刚体自由落体。Eigen 固定 3.4.0；Homebrew Eigen 5 无法被该版本查找脚本识别。CUDA、传感器、车辆等可选模块未启用/验证。

复现：`python3 scripts/build.py eigen chrono`，`.venv/bin/python -m physim run chrono`。C++ bridge 的 CTest 已通过。2 kg 刚体 1 秒后 NED 下落距离约 4.908228 m、速度约 9.806650 m/s；位置误差符合 1 ms 离散步长的容差。

macOS 安装名通过 CMake 指向工程 `install/chrono/lib`；移动工程后需重配/重建。没有使用全局 DYLD 环境变量掩盖加载问题。尚未和其他模块耦合。

### SU2 8.1.0

来源：[su2code/SU2](https://github.com/su2code/SU2)。LGPL-2.1-or-later；CFD/气动分析，按离线求解器接入。所有 gitlink 子模块已按上游固定提交获取。串行 CPU 配置，MPI、OpenMP、CGNS、TecIO 关闭。

复现：`python3 scripts/deps.py submodules su2`，`python3 scripts/build.py su2`，`.venv/bin/python -m physim run su2`。上游 8.1.0 的 `CFlowTractionInterface.cpp` 少一层 `../`，实际编译报错后采用 `patches/su2-8.1.0-include.patch` 修复；构建脚本幂等应用，不改写上游提交或许可证。

已运行 `examples/su2/uniform.cfg` 和本工程生成的 32 单元网格，10 次迭代后解析真实 `history.csv`。测试要求各 RMS 残差 log10 < -8。此例验证求解器调用、网格/配置和输出读取；尚未验证翼型、湍流、气动数据库生成或与飞行模型耦合。

### Cantera 3.1.0

来源：[Cantera/cantera](https://github.com/Cantera/cantera)。BSD-3-Clause；热力学、化学反应和输运。源码已获取，使用固定哈希的 arm64 Python wheel；未在本机重建 Cantera C++ 库。

复现：`sh scripts/bootstrap.sh`，`.venv/bin/python -m physim run cantera`。真实 `gri30.yaml` 甲烷空气 HP 平衡，300 K/101325 Pa 初态得到约 2225.525 K；测试检验焓守恒与摩尔分数归一化。当前是静态平衡示例，不是燃烧室瞬态模型。

### CoolProp 7.1.0

来源：[CoolProp/CoolProp](https://github.com/CoolProp/CoolProp)。MIT；热物性，不能当作流动求解器。源码已获取，使用固定哈希的 arm64 wheel；未在本机重建 C++ 库。

复现：`.venv/bin/python -m physim run coolprop`。JSBSim → CoolProp 100 个样本链路已通过；1000 m 初态约 281.651 K、89876.731 Pa，得到空气密度约 1.112171 kg/m³、声速约 336.547 m/s。CoolProp 只消费数据，没有修改 JSBSim 内部大气模型。

## 已获取，构建/接入仍受阻

以下模块在 `modules.json` 默认禁用。已有独立构建 recipe 或明确的前置依赖诊断，不能记为已接入；通用 `external_run` 仅是独立进程边界，不是这些求解器已实现的物理结果解析器。

### SOFA v24.12.00

来源：[sofa-framework/sofa](https://github.com/sofa-framework/sofa)。以交互式多物理场、可变形体和有限元为主；框架 LGPL-2.1-or-later，应用/插件应分别查许可。

已尝试 headless CMake 配置，具体失败：`Sofa/framework/Type/CMakeLists.txt: Boost (1.54.0 or higher) is mandatory`。复现 `python3 scripts/build.py sofa --configure-only`。安装入口 `sh scripts/install-native.sh sofa`；之后重跑构建。已提供真实场景输入 `examples/sofa/freefall.scn`，但尚未运行，后续命令为 `install/sofa/bin/runSofa -g batch -n 10 examples/sofa/freefall.scn`。组件装载和输出解析仍需验证，SofaPython3 未接入。

### MOOSE 2025-03-27-release

来源：[idaholab/moose](https://github.com/idaholab/moose)。有限元/有限体积多物理场框架，可通过模块构建热、固体和断裂应用。顶层 LGPL-2.1；不是单个可以直接替换的实时物理库。

前置检查实际失败：本机无 `mpicxx`，锁定源码中的 libMesh/PETSc 尚未构建。复现 `python3 scripts/build.py moose --configure-only`。需按该发布版本的 `conda/` 元数据与 `scripts/update_and_rebuild_petsc.sh`、`scripts/update_and_rebuild_libmesh.sh` 建立匹配环境，不能假定任意 Homebrew PETSc 兼容。接着运行本工程 build recipe 编译 `test` 应用。

已提供真实但未验证的 `examples/moose/diffusion.i`。应用可用后的示例为 `external/moose/test/moose_test-opt -i examples/moose/diffusion.i`；Exodus 输出应在独立作业目录解析。尚无可用 arm64 工具链锁和真实适配器。

### OpenVSP / VSPAERO 3.42.3

来源：[OpenVSP/OpenVSP](https://github.com/OpenVSP/OpenVSP)。OpenVSP 是参数化几何建模；VSPAERO 是同仓库中的气动分析程序，不等同于 SU2 的通用 CFD。顶层 NASA Open Source Agreement 1.3；内置依赖/子组件许可保留在源码中。

实际构建了部分内置依赖。首先触发 CMake 4 删除旧策略兼容的错误；脚本已向子构建传递 `CMAKE_POLICY_VERSION_MINIMUM=3.5`。随后仍在 Code-Eli 的 `cmake/ConfigureCompiler.cmake:242` 失败：`Need to fix ConfigureCompiler.cmake to support AppleClang compiler!`。复现 `python3 scripts/build.py openvsp`，完整失败日志在 `artifacts/logs/openvsp-build.log`。

后续需针对固定 Code-Eli 归档提供可审查补丁，或验证 VSPAERO 独立构建目录 `src/vsp_aero/StandAlone`。未将部分 Libraries 构建标为 OpenVSP/VSPAERO 已构建，也没有生成虚假气动系数。

### RadarSim 候选：RadarSimPy v14.0.0

`RadarSim` 名称无法唯一确定项目。本次暂按 [radarsimx/radarsimpy](https://github.com/radarsimx/radarsimpy) 接入候选槽位，未声称它就是用户最初指的唯一仓库。该固定版本 Python 包装层许可证为 GPL-3.0；`.gitmodules` 指向 `git@github.com:rookiepeng/radarsimcpp.git`，实际核心源码不在已获取包装层中。上游也说明从源码构建需要单独获得 RadarSimCpp：[安装说明](https://github.com/radarsimx/radarsimpy/blob/master/gen_docs/user_guide/installation.rst)。

复现 `python3 scripts/build.py radarsim` 会明确报缺少后端，不会尝试私有 SSH 凭据或安装同名不相关 PyPI 包。下一步需要明确候选身份，并提供/选定有权使用的兼容 arm64 后端分发包，固定其版本/哈希/许可。此模块尚无真实运行适配器。

### FERS 固定快照 f86c89fd7a50

来源：[stpaine/FERS](https://github.com/stpaine/FERS)。Flexible Extensible Radar Simulator，信号级雷达仿真；本次固定源码头部标注 GPL-2.0-only。完整 SHA 已锁，初始 HEAD 后续变化不会自动更新。

已运行 CMake，失败于缺少 vcpkg toolchain。复现 `python3 scripts/build.py fers --configure-only`。上游 `vcpkg.json` 的 builtin-baseline 为 `9942fb5f996ea431c5ed8fb8d2a53f31d08df62e`；后续应固定该工具链/ports，设置 `VCPKG_ROOT` 并使用 `arm64-osx` triplet。上游 `examples/` 有真实场景，尚未运行，不能报告雷达仿真已接入。

### Meep 1.30.0

来源：[NanoComp/meep](https://github.com/NanoComp/meep)。GPL-2.0-or-later，时域有限差分电磁场求解。不是可直接以米/秒输入的 SI 飞行动力学模块。

前置检查失败：缺少 `autoreconf`，并且 FFTW/HDF5/Guile/libctl/Harminv 科学计算栈尚未配置。复现 `python3 scripts/build.py meep --configure-only`；依赖安装入口 `sh scripts/install-native.sh meep`，然后重跑构建。`examples/meep/pulse.ctl` 是未验证的真实输入，使用长度单位 1 µm，时间映射必须是 `t_SI=t_meep*1e-6/c0`。后续在独立作业目录运行 `install/meep/bin/meep <absolute-path>/pulse.ctl`，解析场文件后才能启用适配器。

### preCICE 3.2.0

来源：[precice/precice](https://github.com/precice/precice)。LGPL-3.0-or-later，数据映射与耦合库，不是独立物理求解器。

实际尝试关闭 MPI、PETSc 映射、Python actions 的最小配置，仍缺少 Boost ≥1.74 的 CMake package。复现 `python3 scripts/build.py precice --configure-only`。安装入口 `sh scripts/install-native.sh precice`。后续先构建核心，再接入上游 `examples/solverdummies` 两参与者测试，才能标记通信可用；之后还需真实求解器接口和收敛控制。当前 JSBSim → CoolProp 链路完全没有用 preCICE，不计作其已验证耦合。

## 后续集成边界

1. 固定尚未验证模块的全部传递依赖与工具链；Homebrew recipe 不是这些 profile 的完整可复现锁。
2. 解决上述实际错误，逐一补齐真实输出解析与数值不变量测试，再启用模块。
3. 为 SU2 加入固定网格的翼型基准与收敛验证；当前均匀流不承担气动精度论证。
4. 为几何、坐标原点、姿态和网格拓扑定义更完整的跨模块约束。明确动力学状态的唯一权威，避免 JSBSim 与 Chrono 双重积分。
5. 测量持久进程/原生接口开销后再选择实时路径。当前调度器是独立作业编排，不是硬实时同步器。
6. 编写 Unity 编辑器/Play Mode 端到端测试。当前 C# DTO 已由本机 Mono 编译，但没有在 Unity 中执行。

未启动游戏功能开发。保留已有 Unity 修改，未创建提交、推送或改变上游 remote。
