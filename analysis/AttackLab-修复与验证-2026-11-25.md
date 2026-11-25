# AttackLab 修复与最终回归记录（2026-11-25）

基线：`d54873fdab7ecfe25d5650f3534767b792d45d95`。本轮针对两轮审计中发现的代码、工具链、报告证据和提交工程问题实施修复，并在 Oracle VirtualBox Ubuntu 24.04 中验证。课程 `attack/` 四个原始文件未修改。

## 一、核心代码

- `payload.py`：仍然通过栈溢出进入 `eval` 的 `system(command_buf)` 调用点。现在 saved rbp 保存 `fixed_stack_top-0x10`，即固定 `main` 帧的位置，而非无效的 `B*8`。`system` 返回后经 `eval` 的 `leave` 和未改写的包装函数返回地址回到 `__wrap_main`，**实际 exit(0)**。输入仍为 33 字节（含换行），不是伪造成功输出。
- `payload_dark.py`、`payload_rop.py`：保留原本已正确且 exit(0) 的方案。
- `payload_canary.py`：保留已验证的 input Canary 保留绕过；`grade_eval` 输出并 flush 后按当前设计进入无效填充并 SIGSEGV。没有将未成功的清理链写成已完成改进，官方 stdout 判分仍通过。
- `attacklab.py`：只承诺当前课程 ELF 布局下的地址解析，不再宣称任意 rebuild 兼容。加入非 PIE/x86-64、ELF/节/段长度、表项尺寸和地址读取边界检查；不支持的格式明确失败。四个 payload 的标准库依赖与跨工作目录执行保持不变。

## 二、可信复现与工具链

- 新增 `tools/prepare_lab.sh`：先验证四个官方 SHA256，再创建全新、可执行的隔离工作副本。已有目录拒绝覆盖；不删除 `~/lab3`。
- `tools/run_evidence.py`：不再使用未校验的 `~/lab3`，直接使用仓库 `attack/` 的隔离副本；生成器返回码、非空输出、超时和预期 stdout 均纳入判定。全部成功后发布日志，失败非零退出；ASLR 和 GDB 配置是真实运行/查询结果。
- `tools/verify_ci.sh`：核验哈希、私有临时副本、生成器和目标各 15 秒超时、`ulimit -c 0`；核心 stdout 判分与官方一致，记录目标真实退出状态。
- `tools/hash_check.sh`、`tools/capture_disassembly.sh`、`tools/capture_gdb.sh`：失败传播、非空检查和原子替换，不再用空文件覆盖证据后仍返回成功。
- `tools/make_inputs.py`：支持绝对 `ATTACKLAB_FIXTURE_DIR`，先完整生成再发布；新增长度观察输入，拒绝相对路径和符号链接目标。
- `tools/gadgets.py`：检查 objdump 返回码，拒绝空/非法 pattern 和非正窗口。
- `tools/screens/`：隔离靶机与 fixture，逐字节比对复用目录，不再删除 `~/lab3` 或读取固定 `/tmp/lab3-inputs`。
- `tools/capture_command_substitution.py`：正式记录旁路观察，分开 stdout/stderr；证明命令替换可触发 malware，但成功横幅在 stderr，不能通过只查 stdout 的 CI。
- `tools/check_pdf.py`：结构与 DOCX 源码哈希检查在失败时非零退出；若有 `pypdf`，直接读取 PDF 页面文字验证必需标记。没有该包时明确 SKIP 正文验证，不声称通过完整文本提取。
- `requirements-tools.txt`：声明可选文档工具 `python-docx`、`pypdf` 与系统依赖；核心 payload 不需要这些包。
- README 明确 `attacklab.py` 是必需提交文件、运行平台和有限适配范围。

## 三、报告与真实证据

- 修正任务三终点、`mov edi` 与 `pop rdi` 的区别、NX `grade_eval` 无 Canary、伪造 rbp 的实际用途等技术错误。
- 补齐官网指定观察：
  - `analysis/gdb/00_call_return.txt`：`call input` 前单步、prologue、`leave/ret` 回调用者。
  - `analysis/gdb/06_length_overflow.txt`：20/32 字节 gets 后栈转储，24 字节 SIGBUS 与 48 字节守卫页异常。
  - `analysis/gdb/07_main_memory.txt`：`x/9bx main`、前三条指令区间与 `rip` 单步变化。
- 修正固定栈/NX 日志筛选，ROP“实测”与验收表来自结构化运行记录；区分静态分析文字、生成器输入转储和真实目标运行输出。
- 删除无原始证据的“翻车三遍”等叙事，改为设计推导或事后复现；不根据文风推断作者身份。
- 命令替换旁路明确 stdout/stderr 和 CI 边界。
- 当前本地记录：前三项 payload `target_rc=0`，Canary `target_rc=-11`；`payload.py` 的 GDB 明确 `[Inferior ... exited normally]`。
- 新 DOCX 和 PDF 已生成；PDF 48 页。结构、真实文本标记、五份核心源码哈希均通过。姓名/学号保留空白，需由提交人填写。
- LibreOffice 导出报告缺失 Courier 字体；未做本模型无法支持的截图视觉核验，因此不宣称截图已完全认证。

## 四、VirtualBox 实测结果

### 正向干净候选包

- 四个课程二进制 SHA256 全匹配。
- `bash tools/verify_ci.sh`：`RESULT: PASS (4/4)`，退出状态 `0/0/0/139`（Shell 的 128+signal）。
- `bash tools/capture_disassembly.sh`：419/317/294 行反汇编成功。
- `bash tools/capture_gdb.sh`：9 个 GDB 场景全部完成。
- `python3 tools/run_evidence.py`：四个 PASS、15 个长度行、6 次不同 ASLR 地址，`RESULT: PASS`。
- `python3 tools/capture_command_substitution.py`：stderr 横幅验证通过。
- 五个 `tools/screens/` 场景均真实执行成功。
- 主机 `tools/check_docx.py`：PASS；`tools/check_pdf.py`：结构、48 页真实文本和五个源码 hash 全部 PASS。
- 干净虚拟机缺少 pypdf 时正文检查明确 SKIP，不冒充已验证；宿主环境的真实 PDF 文本检查通过。

### 负向失败注入

以下均正确返回非零，完整记录位于 `analysis/repair-negative-results/summary.json`：

- 修改一个课程二进制后：`prepare_lab.sh`、`verify_ci.sh`、`hash_check.sh`、`run_evidence.py` 拒绝执行。
- 生成器返回 42：证据生成与本地 CI 均失败，不能把 stdout 当免死金牌。
- 相对 fixture 路径：拒绝。
- 无效 PDF/DOCX：拒绝。
- 注入 GDB/objdump 失败：对应采集与 gadget 工具失败，不留下假成功日志。

## 五、提交前剩余操作

1. 填写 DOCX 封面的姓名和学号；如修改文档需重新导出 PDF并复跑文档检查。
2. 仅暂存预期源码、工具、证据、依赖说明、README 和新 DOCX/PDF；不要 `git add -A` 把审计临时文件加入提交。
3. 查看暂存差异后提交，再由新提交的实际 GitHub Actions 验证。旧 run 的成功不能自动代表新提交。
4. 报告文字、代码和证据已尽力核对，但不能保证人工评分或所有环境/字体/截图视觉效果绝对完美。

## 六、终验补充（2026-11-25）

- 复核发现图 2、图 5 仍是 payload.py 修复前的旧截图（图 2 显示 Bus error、图 5 的 saved rbp 为 42×8），与 §11 表格和附录 A 转储矛盾。已在 VM 文本控制台重跑 s1–s5 场景并重拍全部五张截图，替换 analysis/figs 后重建 DOCX/PDF。
- §9 补写 gadget 范围对照（0x4019d0–0x401ae3；pop rdi/裸 ret 在范围内，grade_eval/exit 为函数与现成调用点），时间线补 11-25 重拍一行；封面日期更新为 11-25。当前 PDF 为 48 页。
- 仓库外的审计临时产物已移出仓库（保留在 E:\attacklab-final-audit\moved-from-repo），仓库仅剩 75 个提交相关文件。
- 仍待办：封面姓名/学号需本人填写；改后需重新导出 PDF 并复跑 check_pdf/check_docx，再由新提交触发 CI。
