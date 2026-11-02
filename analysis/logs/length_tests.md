| 输入长度 | 退出状态 | stdout 摘要 |
|---:|---:|---|
| 0 | 0 | Enter an expression (length up to 15): / 42_is_The_Ànswer |
| 1 | 0 | 1 / Enter an expression (length up to 15): / Executing: echo $((1)) / Enter an expression (length up to 15): / 42_is_The_Ànswer |
| 3 | 0 | 111 / Enter an expression (length up to 15): / Executing: echo $((111)) / Enter an expression (length up to 15): / 42_is_The_Ànswer |
| 8 | 0 | 11111111 / Enter an expression (length up to 15): / Executing: echo $((11111111)) / Enter an expression (length up to 15): / 42_is_The_Ànswer |
| 15 | 0 | 111111111111111 / Enter an expression (length up to 15): / Executing: echo $((111111111111111)) / Enter an expression (length up to 15): / 42_is_The_À |
| 16 | 0 | 111111111111111 / Enter an expression (length up to 15): / Executing: echo $((111111111111111)) / Enter an expression (length up to 15): / 42_is_The_À |
| 20 | 0 | 111111111111111 / Enter an expression (length up to 15): / Executing: echo $((111111111111111)) / Enter an expression (length up to 15): / 42_is_The_À |
| 23 | 0 | 111111111111111 / Enter an expression (length up to 15): / Executing: echo $((111111111111111)) / Enter an expression (length up to 15): / 42_is_The_À |
| 24 | -7 |  |
| 31 | -11 |  |
| 47 | -11 |  |
| 48 | -11 |  |
| 64 | -11 |  |
| 200 | -11 |  |
