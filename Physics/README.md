# 统一物理仿真工程基础

此目录与现有 Unity 工程共用主仓库。上游库放在隔离 Git 工作副本中，通过提交锁和独立构建接入，不混合复制源码，不修改主仓库 Git 索引。

已在本机运行 JSBSim、CoolProp、Cantera 的 Python 适配器、Chrono 的 C++ 自由落体桥接，以及 SU2 的独立 CFD 进程和结果解析。各模块的实测完成状态以 `evidence/status.json` 为准；未完成构建的组件保持禁用。JSBSim → CoolProp 是一条真实的单向、顺序数据传递链，不是 preCICE 耦合，也不是双向流固耦合。

当前验证配置：Apple Silicon、macOS、CPython 3.10.18、Apple Clang 17、CMake 4.1.2。Python wheel 锁要求 macOS 14+。其他机器、Python 版本、Linux/Windows，以及 Unity Play Mode 均不能据此视为已验证。

从仓库根目录运行：

```sh
cd Physics
sh scripts/bootstrap.sh
python3 scripts/deps.py fetch all
python3 scripts/deps.py submodules su2
python3 scripts/build.py eigen chrono jsbsim su2 --jobs 4
make test
make examples
make verify
```

若已有 CPython 3.10，可设置 `PHYSICS_PYTHON=/path/to/python3.10`。bootstrap 只写 `.venv`；pip 的每个直接和间接依赖都固定版本和 wheel SHA-256。已下载 wheel 可离线重装：

```sh
.venv/bin/python -m pip install --no-index --find-links artifacts/wheels \
  --require-hashes -r requirements-macos-arm64.lock.txt
```

单模块和数据链运行：

```sh
.venv/bin/python -m physim list
.venv/bin/python -m physim run jsbsim --output artifacts/flight.json
.venv/bin/python -m physim run coolprop --output artifacts/air.json
.venv/bin/python -m physim run cantera --output artifacts/cantera.json
.venv/bin/python -m physim run chrono --output artifacts/chrono.json
.venv/bin/python -m physim run su2 --output artifacts/su2.json
.venv/bin/python -m physim pipeline examples/atmosphere_pipeline.json --output artifacts/atmosphere.json
```

`run` 支持 `--config config.json`。JSBSim 示例取 100 个 0.01 秒步长，输出真实大气/速度/载荷/质量。CoolProp 逐样本读取温度压力并计算热物性。Cantera 用 `gri30.yaml` 进行甲烷空气 HP 平衡，并测试焓守恒。Chrono 以 1 ms 步长推进 1 s 自由落体，与解析解比较。SU2 在 32 个四边形单元网格上推进 10 次稳态 Euler 迭代，解析真实 CSV 残差，检验均匀流保持；不代表飞机 CFD 模型已验证。

文件入口：

- `dependencies.lock.json`：12 个候选仓库加 Eigen 的 URL、发布标签、完整提交、许可证摘要。
- `requirements-macos-arm64.lock.txt`：已实测 Python 原生二进制及全部运行依赖的哈希锁。
- `scripts/deps.py`：获取、提交校验、按上游 gitlink 获取子模块；不自动覆盖已修改源码。
- `scripts/build.py`：逐模块原生配置/构建/安装，失败返回非零并继续其他指定模块，日志位于 `artifacts/logs/`。
- `physim/`、`modules.json`：模块注册、进程生命周期、超时、流水线及真实适配器。
- `schema/`、`docs/CONTRACT.md`、`unity/`：公共协议和 Unity 预留接口。
- `tests/`：真实求解器测试、耦合扰动测试、协议与生命周期测试。
- `docs/MODULES.md`：逐模块接入状态、障碍、复现和后续工作。
- `licenses/`、`evidence/`：上游顶层许可原文、来源哈希、当前机器实测快照。

`external/`、`build/`、`install/`、`.venv/`、`artifacts/` 为可重建本机产物，默认不进入主仓库；锁文件、集成代码和证据快照进入版本控制。初次 fetch 使用浅克隆保留来源与提交关系，需要完整历史时运行 `git -C external/<id> fetch --unshallow`。

依赖更新要显式修改提交锁，重新下载 wheel、生成哈希、运行测试及证据导出；不要把可变分支当锁。原生附加依赖的 Homebrew 安装脚本仅是开发环境引导，未验证 profile 尚不是完整传递依赖锁。上游许可证仍分别适用，未替整个 Unity 工程选定新许可证。

SU2 8.1.0 有一个已实际触发的相对 include 路径错误，`scripts/build.py` 会幂等应用 `patches/su2-8.1.0-include.patch`。上游 HEAD 仍固定，修改单独留在补丁文件中。Chrono 的安装库使用当前工程的绝对安装名，移动目录后需重新配置/构建桥接，不应直接搬运旧二进制。
