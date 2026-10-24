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

### SOFA v24.12.00

来源：[sofa-framework/sofa](https://github.com/sofa-framework/sofa)。LGPL-2.1-or-later；交互式多物理场与可变形体仿真。
已安装本机 Boost、tinyxml2、libxml2、cxxopts、googletest 依赖，以 Headless Release 配置原生从源码编译并安装 `runSofa` 至 `install/sofa/bin/runSofa`。
已提供真实场景 `examples/sofa/freefall.scn` 并通过 `runSofa -g batch -n 10` 执行 10 步 1 ms 自由落体。
统一适配器 `sofa_run` 解析真实刚体位置、速度与质量，输出 NED 规范状态帧并通过 `test_sofa_freefall` 验证。

复现：`python3 scripts/build.py sofa`，`.venv/bin/python -m physim run sofa`。

### preCICE 3.2.0

来源：[precice/precice](https://github.com/precice/precice)。LGPL-3.0-or-later；多物理场耦合框架。
由于 Boost 1.92 移除了已废弃的 `boost::asio::deadline_timer`，提供了源码级补丁 `patches/precice-3.2.0-boost-asio.patch` 替换为 `steady_timer`，哈希记录于 `dependencies.lock.json`。
原生编译出 `libprecice.dylib` 与 `precice-tools` 安装至 `install/precice`。
编译了 `precice-solverdummy`（SolverOne 与 SolverTwo），通过本地 TCP Socket 进行双向耦合测试，通过 `test_precice_coupling` 验证两时间步双向通信收敛。

复现：`python3 scripts/build.py precice`，`.venv/bin/python -m physim run precice`。

### OpenVSP / VSPAERO 3.42.3

来源：[OpenVSP/OpenVSP](https://github.com/OpenVSP/OpenVSP)。NASA Open Source Agreement 1.3。
绕过顶层打包 Libraries 中 Code-Eli 的 AppleClang 编译器识别错误与 libxml2 路径引号缺陷，直接从 `src/vsp_aero/StandAlone` 配合 Adept2 原生编译出完整 VSPAERO 气动套件（`vspaero`、`vspaero_complex`、`vspaero_adjoint`、`vspaero_opt`、`vsploads`），安装至 `install/openvsp/bin`。
提供了 Hershey 机翼输入 `examples/openvsp/hershey.vspaero` 与 `hershey.vspgeom`，在 Mach 0.11、迎角 5.0° 下执行涡格法/面板法气动求解。
在 `schema/state.schema.json` 中扩展了 `aero_analysis` 规范，适配器 `openvsp_run` 解析 `.polar` 极曲线文件，提取升力系数 $C_L$、阻力系数 $C_D$、升阻比 $L/D$ 及俯仰力矩，并通过 `test_openvsp_vspaero` 验证。

复现：`python3 scripts/build.py openvsp`，`.venv/bin/python -m physim run openvsp`。

### FERS 固定快照 f86c89fd7a50

来源：[stpaine/FERS](https://github.com/stpaine/FERS)。GPL-2.0-only；信号级灵活可扩展雷达仿真器。
在工作区内通过固定 baseline `9942fb5f996ea431c5ed8fb8d2a53f31d08df62e` 引导 vcpkg，为 `arm64-osx` 编译了 HDF5、HighFive、GeographicLib、libxml2、Catch2 等依赖，成功原生构建 `libfers.dylib` 及 `fers-cli` 安装至 `install/fers`。
提供了 FMCW 单基雷达仿真场景 `examples/fers/fmcw.fersxml`（载频 10 GHz、带宽 50 MHz、64 次扫频 chirp）。
在 `schema/state.schema.json` 中扩展了 `radar_analysis` 规范，统一适配器 `fers_run` 通过 `ctypes` 调用 C API 进行无锁仿真，并解析 HDF5 仿真结果元数据，由 `test_fers_simulation` 验证采样点数与脉冲时间参数。

复现：`python3 scripts/build.py fers`，`.venv/bin/python -m physim run fers`。

### Meep 1.30.0

来源：[NanoComp/meep](https://github.com/NanoComp/meep)。GPL-2.0-or-later；时域有限差分（FDTD）电磁场仿真。
配置 Autotools、FFTW、Guile 3.0、HDF5，构建了匹配的 libctl 4.7.1 与 Harminv 1.4.2。采用 `--without-mpi --without-python` 避开 Python 3.10 `<structmember.h>` 中宏 `READONLY` 与 Meep C++ 枚举名的冲突，成功原生编译出 Scheme CLI 程序 `meep` 及 `libmeep` 并安装至 `install/meep`。
提供了 3D 高斯脉冲电磁传播场景 `examples/meep/pulse.ctl`（特征尺寸 1 µm，仿真时间 $t=20.0$，800 时间步，物理时间按 $t_{\text{SI}} = t_{\text{meep}} \cdot 10^{-6} / c_0$ 换算）。
在 `schema/state.schema.json` 中扩展了 `em_analysis` 规范，统一适配器 `meep_run` 执行仿真并解析 HDF5 电场数据集（`pulse-ex-000020.00.h5`），计算最小/最大/均值/有效值（RMS）场强与峰值绝对场强，由 `test_meep_pulse` 验证。

复现：`python3 scripts/build.py meep`，`.venv/bin/python -m physim run meep`。

## 已获取，构建/接入仍受阻

以下模块在 `modules.json` 中保持禁用，并完整保留上游源码与依赖锁。

### MOOSE 2025-03-27-release

来源：[idaholab/moose](https://github.com/idaholab/moose)。有限元/有限体积多物理场框架，可通过模块构建热、固体和断裂应用。顶层 LGPL-2.1；不是单个可以直接替换的实时物理库。

前置检查实际失败：本机无 `mpicxx`，锁定源码中的 libMesh/PETSc 尚未构建。复现 `python3 scripts/build.py moose --configure-only`。需按该发布版本的 `conda/` 元数据与 `scripts/update_and_rebuild_petsc.sh`、`scripts/update_and_rebuild_libmesh.sh` 建立匹配环境，不能假定任意 Homebrew PETSc 兼容。

已提供真实但未验证的 `examples/moose/diffusion.i`。应用可用后的示例为 `external/moose/test/moose_test-opt -i examples/moose/diffusion.i`；Exodus 输出应在独立作业目录解析。尚无可用 arm64 工具链锁和真实适配器。

### RadarSim 候选：RadarSimPy v14.0.0

`RadarSim` 名称无法唯一确定项目。本次暂按 [radarsimx/radarsimpy](https://github.com/radarsimx/radarsimpy) 接入候选槽位，未声称它就是用户最初指的唯一仓库。该固定版本 Python 包装层许可证为 GPL-3.0；`.gitmodules` 指向 `git@github.com:rookiepeng/radarsimcpp.git`，实际核心源码不在已获取包装层中。上游也说明从源码构建需要单独获得 RadarSimCpp：[安装说明](https://github.com/radarsimx/radarsimpy/blob/master/gen_docs/user_guide/installation.rst)。

复现 `python3 scripts/build.py radarsim` 会明确报缺少后端，不会尝试私有 SSH 凭据或安装同名不相关 PyPI 包。下一步需要明确候选身份，并提供/选定有权使用的兼容 arm64 后端分发包，固定其版本/哈希/许可。此模块尚无真实运行适配器。

## 后续集成边界

1. 固定尚未验证模块的全部传递依赖与工具链；Homebrew recipe 不是这些 profile 的完整可复现锁。
2. 解决上述实际错误，逐一补齐真实输出解析与数值不变量测试，再启用模块。
3. 为 SU2 加入固定网格的翼型基准与收敛验证；当前均匀流不承担气动精度论证。
4. 为几何、坐标原点、姿态和网格拓扑定义更完整的跨模块约束。明确动力学状态的唯一权威，避免 JSBSim 与 Chrono 双重积分。
5. 测量持久进程/原生接口开销后再选择实时路径。当前调度器是独立作业编排，不是硬实时同步器。
6. 编写 Unity 编辑器/Play Mode 端到端测试。当前 C# DTO 已由本机 Mono 编译，但没有在 Unity 中执行。

未启动游戏功能开发。保留已有 Unity 修改，未创建提交、推送或改变上游 remote。
