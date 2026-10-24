# VECTOR / INTERCEPT — hackathon demo

Unity 场景：`Assets/AirInterceptDemo/AirInterceptDemo.unity`。
菜单入口：`Tools > Air Intercept > Open Demo`，然后点击 Play 并聚焦 Game 窗口。

两架 F-16 由同一个持久 Python 进程中的两个真实 JSBSim 实例推进，固定步长 1/120 秒，30 Hz JSON 行遥测。Unity 启动和回收该进程、读取状态并显示飞机；不再次积分位置。对手机自动朝玩家转向。双机均有独立探测判定，初始双方均能探测到对方。

- W / S：提高 / 降低目标高度；有姿态与高度辅助。
- A / D：左右压坡度转弯，松开后回平。
- Q / E：方向舵。
- Shift / Ctrl：增加 / 减少油门。
- P 或界面按钮：暂停 / 继续。
- R 或界面按钮：重置双机和任务时间。
- Tab：在蓝机和橙机的跟随视角之间切换；始终操控蓝机。

HUD 参照提供的手绘草图：左上飞行与载荷，左下真实燃油和续航估计，右上自动扫描 AESA，右侧可见光 EO 实时画面，右下机体姿态示意。目标框由雷达有效航迹或 EO 接触驱动。所有显示量采用 SI：m、m/s、rad、s、kg、kg/s、K、Pa、Hz、W；Mach、油门、增益、SNR 用无量纲数值。弹药区域显示未装载，机体图不伪造损伤。

初始高度约 1829 m，双机间距约 4211 m，迎面飞行。没有武器、碰撞和联机。接地后停止推进并显示重置提示。飞机为运行时生成的简化几何模型，场景不依赖外部美术资产。

前置环境是已有的 `Physics/.venv` 和锁定的 JSBSim 1.2.3。编辑器默认从当前项目的 Physics 目录启动。可用 `PHYSICS_ROOT` 指向另一份完整 Physics 目录。当前交付以 macOS Unity Editor 为入口，独立应用分发需要另外打包 Python 与原生库。

后台快速检查（45 秒仿真，不用等待 45 秒实际时间）：

```sh
cd Physics
.venv/bin/python -m physim.air_demo --smoke
```

检查覆盖双机初始化、初始互相探测、爬升/转弯后继续飞行、远距离低 SNR 和机尾目标不被探测、暂停和重置。传感器公式测试运行 `.venv/bin/python -m unittest discover -s tests -p test_demo_sensors.py -v`。

编辑器验证入口为 `Tools > Air Intercept > Verify Demo`。也可创建 `Physics/artifacts/air-demo-verify.request` 触发当前已打开编辑器验证。它会在场景无未保存修改时打开 demo、进入 Play Mode、等待真实遥测、截图并退出 Play Mode；结果位于 `Physics/artifacts/air-demo-unity-result.json`。截图为 `Physics/artifacts/air-demo.png`。

本次检查：45 秒 JSBSim 双机仿真检查通过；JSON 行进程通信的启动、初始互相探测、暂停、重置和正常退出通过；C# 已使用本机 Unity 引用与 Input System 编译通过。另在 Unity 6000.3.15f1 隔离临时工程中进入 Play Mode，确认真实遥测推进到 5 秒且双方均探测成功。HUD 现已改为相机空间 Canvas，批处理预览也包含实际仪表、扫描和 EO 画面；键盘手动操作和主工程 URP 画面还需要在 Game 窗口验收。主工程已在另一 Unity 实例打开，故未用第二个实例直接打开主工程。

给 Antigravity 的后续范围：先核实此 demo 的 Unity 运行结果，再改进画面/操控和展示流程。原有模块的耗时构建可继续单独运行，避免同时修改本 demo 文件。不要把 VSPAERO 离线升力直接叠加到现有 JSBSim 气动力上。

## 雷达与光电模型

公式和参数见 `docs/DEMO_SENSORS.md`。UI 上三按钮切换 1e9、1e10、9.4e10 Hz 的理想孔径模型。它们分别覆盖分米、厘米与毫米波；此处表示三种理想配置，不宣称一副真实阵面可无损覆盖整个频带。

雷达以有限宽度波束逐点扫描；可见光已经发现目标时，允许 EO 线索引导电子波束。雷达仅在回波超过接收机噪声门限时建立航迹，丢失照射后最多沿用最后一次测量 2 s，随后清除；不在搜索状态泄漏真实目标位置。EO 画面是场景相机，接触判断是视场与理想衍射分辨率几何模型，不是红外测温。
