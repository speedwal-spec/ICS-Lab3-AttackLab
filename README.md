# Lab 3 实验仓库

## 仓库结构

```
.
├── attack              # 二进制目录
│   ├── dark-calc
│   ├── dark-calc-nx
│   ├── dark-log
│   └── malware
├── payload_canary.py
├── payload_dark.py
├── payload.py
├── payload_rop.py
├── attacklab.py        # 四个 payload 共用的标准库 ELF 解析器，必须一并提交
├── README.md
└── src                 # 部分源码目录，仅供参考
    ├── aslr.c
    ├── dark-calc.c
    └── dark-log.c
```

除了上述文件之外，提交时在根目录中还应当有一份 PDF 格式的实验报告。

所有任务需要使用的二进制都在 `attack` 中，大家不需要自行编译。给大家提供的源码仅包含核心逻辑；不要用重编译的参考源码替换给定二进制。

## 运行与依赖

- 四个 payload 在课程给定的 **Linux x86-64、非 PIE** 二进制上运行；生成 payload 只需要 Python 3 标准库。请完整提交 `attacklab.py`、四个 payload 和原始 `attack/` 文件。
- 克隆后的 Git 文件可能没有可执行位。`tools/verify_ci.sh` 会自行创建可执行临时副本，可直接运行 `bash tools/verify_ci.sh`；手工执行靶机前可用 `bash tools/prepare_lab.sh` 准备隔离副本。
- 本地验证：`bash tools/verify_ci.sh`。证据采集：`bash tools/capture_gdb.sh`、`bash tools/capture_disassembly.sh`、`python3 tools/run_evidence.py`、`python3 tools/capture_command_substitution.py`。它们使用隔离工作目录，不依赖 `~/lab3`。
- 重建报告的工具链另需 `python-docx`、`pypdf` 和 LibreOffice；调试用具为 GDB、binutils、gcc，`malware` 使用 `pstree`/`ps`，Shell 测试使用 GNU `timeout`。这些不是官方 payload CI 的额外安装要求。详见 `requirements-tools.txt`。
- 地址从给定 ELF 解析，但栈帧、结构体和 gadget 布局有意对应课程二进制，**不保证任意重编译的靶机兼容**。`payload_canary.py` 在目标输出后按当前设计异常结束，官方检查只要求目标 stdout 中的字符串。


## 任务列表

以下内容需要包含在实验报告当中：

- 任务：观察栈帧 `input` (20 pts 报告)
- 用不同长度的字符串输入测试 `dark-calc` (5 pts 报告)
- 任务：利用缓冲区漏洞执行 `./malware` (25 pts 测试 + 5 pts 报告)
- 用 GDB 检查 main 函数的机器码 (5 pts 报告)
- 任务：栈空间执行 (25 pts 测试 + 5 pts 报告)
- 任务：ROP (10 pts 测试 + 10 pts 报告)
- 任务：Canary (10 pts 测试 + 10 pts 报告)

共 130 分。即使没有通过测试，也需要在报告当中记录自己的想法和尝试，你依然可以拿满报告分数。

本实验中所有报告都会被批改。

## 分数比重

本实验共占课程总分数 13 / 100 分。
