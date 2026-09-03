# 代码扫描规则库 (Scan Rules Library)

> 本文件定义所有可自动检测的代码质量规则。每条规则包含：检测模式、严重程度、适用语言、误报抑制条件。
> 规则来源于 `test-methods.md` 中的测试方法论和 `defect-analysis.md` 中的缺陷模式。

---

## 规则索引

| 规则ID | 名称 | 方法来源 | 严重程度 | 适用语言 |
|--------|------|----------|----------|----------|
| **INPUT 组 - 输入验证规则** ||||
| INPUT-01 | 外部输入类型校验缺失 | 等价类划分 | BLOCKER | ALL |
| INPUT-02 | 参数范围校验缺失 | 边界值分析 | BLOCKER | ALL |
| INPUT-03 | 枚举/状态处理不完备 | 等价类划分 | CRITICAL | ALL |
| INPUT-04 | 字符串长度未限制 | 边界值分析 | CRITICAL | ALL |
| INPUT-05 | 正则/格式校验缺失 | 等价类划分 | MAJOR | ALL |
| **NULL 组 - 空值安全规则** ||||
| NULL-01 | 可能空值的解引用 | 错误推测 | BLOCKER | Java/Python/JS/TS |
| NULL-02 | 集合/数组越界访问 | 边界值分析 | BLOCKER | ALL |
| NULL-03 | 方法链式调用空指针风险 | 错误推测 | CRITICAL | Java/Python/JS/TS |
| NULL-04 | 可选值未处理 | 等价类划分 | CRITICAL | Java(Optiona)/Swift/TS |
| NULL-05 | Map/dict get无默认值 | 边界值分析 | MAJOR | Python/Java/JS |
| **BOUNDARY 组 - 边界处理规则** ||||
| BOUND-01 | 循环边界 off-by-one | 边界值分析 | CRITICAL | ALL |
| BOUND-02 | 切片/子串越界风险 | 边界值分析 | CRITICAL | Python/Java/JS |
| BOUND-03 | 整数运算溢出风险 | 边界值分析 | CRITICAL | Java/C/C++/Python |
| BOUND-04 | 除法运算除零保护 | 错误推测 | BLOCKER | ALL |
| BOUND-05 | 递归深度无限制 | 边界值分析 | MAJOR | ALL |
| BOUND-06 | 集合容量超限风险 | 边界值分析 | MAJOR | ALL |
| **EXCEPTION 组 - 异常处理规则** ||||
| EXCP-01 | 空catch块（异常被吞掉） | 错误推测 | CRITICAL | Java/Python/C#/JS |
| EXCP-02 | 宽泛异常捕获 | 错误推测 | MAJOR | Java/Python |
| EXCP-03 | 异常后资源未释放 | 错误推测 | CRITICAL | ALL |
| EXCP-04 | 受检异常未声明/处理 | 等价类划分 | MAJOR | Java |
| EXCP-05 | finally块中的异常覆盖 | 错误推测 | MAJOR | Java/Python |
| **LOGIC 组 - 逻辑完整性规则** ||||
| LOGIC-01 | if/else分支不完整 | 因果图 | MAJOR | ALL |
| LOGIC-02 | switch/default缺失 | 等价类划分 | CRITICAL | Java/C/Go/Swift |
| LOGIC-03 | 布尔表达式短路副作用 | 因果图 | MAJOR | ALL |
| LOGIC-04 | 浮点数等值比较 | 错误推测 | MAJOR | ALL |
| LOGIC-05 | 条件判断永真/永假 | 错误推测 | CRITICAL | ALL |
| **RESOURCE 组 - 资源管理规则** ||||
| RESC-01 | 资源未关闭(无try-with/using) | 错误推测 | CRITICAL | Java/Python/C# |
| RESC-02 | 连接池连接未归还 | 缺陷模式 | CRITICAL | Java/Python/Go |
| RESC-03 | 文件操作无finally保护 | 错误推测 | CRITICAL | ALL |
| RESC-04 | 大对象未及时释放 | 缺陷模式 | MAIOR | Java/Python |
| **STORAGE 组 - 存储/磁盘/权限规则** ⭐ ||||
| STORAGE-01 | 写入前未检查剩余磁盘空间 | 边界值分析 | CRITICAL | ALL |
| STORAGE-02 | 存储权限未申请直接访问（Android 23+/iOS） | 错误推测 | BLOCKER | Android/iOS/Swift/Kotlin |
| STORAGE-03 | 未处理路径异常（中文/空格/超长/特殊字符） | 边界值分析 | CRITICAL | ALL |
| STORAGE-04 | 文件写入无完整性保护（断电未用临时文件+原子重命名） | 错误推测 | CRITICAL | ALL |
| STORAGE-05 | 写入失败后未清理临时文件 | 错误推测 | MAJOR | ALL |
| STORAGE-06 | 未处理 `IOError / ENOSPC / EACCES / FileNotFoundError` | 错误推测 | CRITICAL | ALL |
| STORAGE-07 | localStorage/SP 写入无 try-catch（QuotaExceeded 会抛异常） | 错误推测 | MAJOR | JS/TS/Android |
| STORAGE-08 | 硬编码绝对路径 / 平台专属分隔符 | 缺陷模式 | MAJOR | ALL |
| STORAGE-09 | 未检测外部存储挂载状态（SD卡拔出/网络盘断开） | 错误推测 | MAJOR | Android/Desktop |
| STORAGE-10 | 大文件同步读写阻塞主线程/UI线程 | 性能 | CRITICAL | ALL |
| STORAGE-11 | 权限被运行时撤销后未感知（未监听权限变化） | 错误推测 | MAJOR | Android/iOS |
| STORAGE-12 | 卸载/清数据时敏感/私有数据未彻底清除（合规风险） | 安全/合规 | CRITICAL | ALL |
| STORAGE-13 | DB/文件 schema 迁移无版本号判断 | 错误推测 | CRITICAL | ALL |
| STORAGE-14 | 同一文件多进程/多线程并发写无锁保护 | 并发 | CRITICAL | ALL |
| **CONCURRENT 组 - 并发安全规则** ||||
| CONC-01 | 共享可变变量无同步 | 缺陷模式 | CRITICAL | Java/Go/C++/Python |
| CONC-02 | 非原子check-then-act | 缺陷模式 | CRITICAL | ALL |
| CONC-03 | Double-Check Locking错误实现 | 缺陷模式 | CRITICAL | Java |
| CONC-04 | 不可变对象在多线程中被修改 | 缺陷模式 | MAJOR | ALL |
| CONC-05 | synchronized范围过大/过小 | 缺陷模式 | MAJOR | Java |
| **SECURITY 组 - 安全规则** ||||
| SECU-01 | SQL注入风险(字符串拼接) | AI缺陷模式 | BLOCKER | ALL |
| SECU-02 | XSS风险(用户输入直接渲染) | AI缺陷模式 | BLOCKER | JS/TS/Java/Python |
| SECU-03 | 硬编码密钥/凭证 | AI缺陷模式 | CRITICAL | ALL |
| SECU-04 | 路径遍历风险 | 缺陷模式 | CRITICAL | ALL |
| SECU-05 | 不安全的反序列化 | 缺陷模式 | CRITICAL | Java/Python |
| SECU-06 | CSRF Token缺失 | 缺陷模式 | MAJOR | Web应用 |
| SECU-07 | 敏感信息日志输出 | AI缺陷模式 | CRITICAL | ALL |
| **AI-CODE 组 - AI代码专项规则** ||||
| AICD-01 | API调用不存在或签名错误(AI幻觉) | AI缺陷模式 | BLOCKER | ALL |
| AICD-02 | 只处理happy path无异常路径 | AI缺陷模式 | CRITICAL | ALL |
| AICD-03 | 函数过长(>50行, AI生成倾向) | AI缺陷模式 | MAJOR | ALL |
| AICD-04 | 过深的嵌套层次(>4层) | AI缺陷模式 | MAJOR | ALL |
| AICD-05 | 缺少文档注释(AI代码应更易读) | AI缺陷模式 | MINOR | ALL |
| AICD-06 | 魔法数字未提取为常量 | AI缺陷模式 | MAJOR | ALL |
| AICD-07 | 生成代码与项目风格不一致 | AI缺陷模式 | MINOR | ALL |
| **PERF 组 - 性能规则** ||||
| PERF-01 | N+1查询模式(循环内DB查询) | 缺陷模式 | CRITICAL | ALL |
| PERF-02 | 大表全量查询无分页 | 缺陷模式 | CRITICAL | SQL/ORM |
| PERF-03 | 循环内重复计算不变量 | 边界值分析 | MAJOR | ALL |
| PERF-04 | 字符串循环拼接(非StringBuilder) | 边界值分析 | MAJOR | Java/Python |
| PERF-05 | 同步阻塞异步上下文 | 缺陷模式 | CRITICAL | Node.js/JS |

---

## 详细规则定义

### INPUT 组 — 输入验证规则

#### INPUT-01: 外部输入类型校验缺失
```yaml
规则ID: INPUT-01
名称: "外部输入类型校验缺失"
方法来源: 等价类划分
严重程度: BLOCKER
描述: 来自外部的输入(user input, API request body, query param, env var等)在使用前未进行类型检查
适用语言: ALL (Python/JS/TS 尤为重要)

检测模式:
  Python:
    pattern: |
      def \w+\([^)]*\):\n(?:.*\n)*.*(?<!isinstance\()(?:request\.(args|form|json)|input\(|os\.getenv|sys\.argv)
    # 函数参数中使用了外部输入但函数体内无 isinstance/type 检查
  
  JavaScript/TypeScript:
    pattern: "(req\\.body|req\\.query|req\\.params|process\\.env\\[)(?!.*typeof)"
    # 使用了外部输入但没有 typeof 检查
  
  Java:
    pattern: "@(RequestParam|RequestBody|PathVariable)\s+\w+\s+(\w+)(?!.*@NotNull|@Valid|@NotBlank)"
    # Controller参数没有注解校验

修复建议:
  Python: 
    "if not isinstance(value, expected_type): raise TypeError(...)"
  JS/TS:
    "if (typeof value !== 'expected') throw new TypeError(...)"
  Java:
    "添加 @Valid @NotNull @NotBlank 等 Bean Validation 注解"

示例:
  ❌ Bad (Python):
    def process_user(data):
        name = data["name"]      # data可能是None,可能没有name键
        age = data["age"]        # age可能是str而非int
        return f"{name} is {age}"
  
  ✅ Good (Python):
    def process_user(data):
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict, got {type(data)}")
        name = data.get("name")
        if not isinstance(name, str):
            raise ValueError("name must be a string")
        age = data.get("age")
        if not isinstance(age, int):
            raise ValueError("age must be an integer")
        return f"{name} is {age}"
```

#### INPUT-02: 参数范围校验缺失
```yaml
规则ID: INPUT-02
名称: "参数范围校验缺失"
方法来源: 边界值分析
严重程度: BLOCKER
描述: 数值型参数在使用前未做范围合法性校验

检测模式:
  通用:
    - 识别函数中的数值参数(int, float, long, double, number)
    - 该参数参与运算(+,-,*,/,/,比较等)
    - 函数体中不存在 >= / <= / > / < / Math.min / Math.max / clamp 范围检查
    - 排除: 参数是私有辅助函数且调用方已校验; 参数来自枚举/常量

修复建议:
  在使用数值参数前添加:
  "if value < MIN or value > MAX: raise ValueError('...')"

示例:
  ❌ Bad:
    def set_volume(level):
        self.volume = level          # level可以是负数或超过100
  
  ✅ Good:
    def set_volume(self, level):
        if not isinstance(level, (int, float)):
            raise TypeError("Level must be numeric")
        if level < 0 or level > 100:
            raise ValueError("Level must be between 0 and 100")
        self.volume = level
```

#### INPUT-03: 枚举/状态处理不完备
```yaml
规则ID: INPUT-03
名称: "枚举/状态处理不完备"
方法来源: 等价类划分
严重程度: CRITICAL
描述: switch/if-elif 未覆盖所有已知的枚举值或状态值

检测模式:
  Java:
    - 提取switch表达式中的enum类型
    - 统计该enum的所有常量
    - 检查case是否覆盖全部常量
    - 检查是否有default分支
  
  Python:
    - 检查 if/elif/elif 链
    - 最后是否有 else 兜底
    - 是否有字典映射 + .get(default) 模式

  TypeScript:
    - 检查 switch 是否 exhaustive (never 类型检查)
    - union type 的 switch 是否覆盖所有成员

修复建议:
  - 补全缺失的 case 分支
  - 添加 default 抛出 IllegalArgumentException
  - 或重构为策略模式/字典映射

示例:
  ❌ Bad (Java):
    void handleStatus(OrderStatus status) {
        switch(status) {
            case PENDING: doPending(); break;
            case PAID: doPaid(); break;
            // missing SHIPPED, DELIVERED, CANCELLED
            // no default
        }
    }
  
  ✅ Good (Java):
    void handleStatus(OrderStatus status) {
        switch(status) {
            case PENDING -> doPending();
            case PAID -> doPaid();
            case SHIPPED -> doShipped();
            case DELIVERED -> doDelivered();
            case CANCELLED -> doCancelled();
            default -> throw new IllegalArgumentException("Unknown: " + status);
        }
    }
```

#### INPUT-04: 字符串长度未限制
```yaml
规则ID: INPUT-04
名称: "字符串长度未限制"
方法来源: 边界值分析
严重程度: CRITICAL
描述: 来自外部的字符串未经截断就直接存入数据库、写入文件、发送网络请求

检测模式:
  - 变量赋值来自外部(input(), request, user_input等)
  - 该变量用于: DB插入/更新、文件写入、HTTP请求body、缓存key
  - 中间无 len() > MAX / substring / slice / [:N] 截断操作

修复建议:
  "value = value[:MAX_LENGTH] if len(value) > MAX_LENGTH else value"

示例:
  ❌ Bad:
    db.insert({"content": user_comment})   # 可能超长导致DB报错
    redis.set("user:" + user_id, json.dumps(large_data))  # 可能超出内存
  
  ✅ Good:
    MAX_COMMENT_LEN = 2000
    content = user_comment[:MAX_COMMENT_LEN]
    db.insert({"content": content})
```

---

### NULL 组 — 空值安全规则

#### NULL-01: 可能空值的解引用
```yaml
规则ID: NULL-01
名称: "可能空值的解引用"
方法来源: 错误推测
严重程度: BLOCKER
描述: 对可能为None/null/undefined的变量进行属性访问或方法调用

检测模式:
  Python:
    - obj.method() 或 obj.attr 其中 obj 可能是 None
    - obj 来自: 函数参数(默认值None), dict.get(), DB查询结果, API返回值
    - 前面无 `if obj is not None` 或 `obj and obj.method()` 保护
  
  JavaScript/TypeScript:
    - obj.prop 或 obj.method() 其中 obj 可能为 null/undefined
    - 无可选链 ?. 保护
    - 无前置 if (obj) 检查

  Java:
    - 方法返回值可能为null(无@NonNull注解)
    - 直接对返回值调用方法
    - 无Objects.requireNonNull/if-null检查

修复建议:
  Python: "if obj is None: return/default/raise" 或使用 Optional/maybe模式
  JS/TS: "使用 obj?.method() 或 obj && obj.method()"
  Java: 使用 @NonNull 注解 + Objects.requireNonNull()

示例:
  ❌ Bad (Python):
    user = get_user(user_id)     # 可能返回None
    return user.name             # AttributeError: 'NoneType'
  
  ✅ Good (Python):
    user = get_user(user_id)
    if user is None:
        raise UserNotFoundError(user_id)
    return user.name
```

#### NULL-02: 集合/数组越界访问
```yaml
规则ID: NULL-02
名称: "集合/数组越界访问"
方法来源: 边界值分析
严重程度: BLOCKER
描述: 通过索引访问集合元素时，未检查索引有效性和集合非空

检测模式:
  - arr[i], list[i], arr.at(i), vector[i] 等索引访问
  - 访问前无 len(arr)>i / arr.size()>i / i < arr.length 检查
  - 无 arr.empty()/isEmpty()/not arr 非空检查

修复建议:
  "if not items: return default; if index >= len(items): raise IndexError(...)"
  或使用 items.get(index, default) (Python)

示例:
  ❌ Bad:
    def first_element(items):
        return items[0]       # IndexError if empty
    
  ✅ Good:
    def first_element(items):
        if not items:
            return None
        return items[0]
    
    # 更好的方式: 使用get带默认值
    result = items[0] if items else None
```

#### NULL-03: 方法链式调用空指针风险
```yaml
规则ID: NULL-03
名称: "方法链式调用空指针风险"
方法来源: 错误推测
严重程度: CRITICAL
描述: 多级方法链调用(a.b.c.d)，中间任一环节返回null都会导致NPE

检测模式:
  - 表达式中存在2个以上的 . 操作符链
  - 如: obj.getUser().getName().toUpperCase()
  - 无可选链(?.)或前置null检查
  - 链越长风险越高

修复建议:
  - 使用可选链: a?.b?.c?.d
  - 拆分为多步并每步检查
  - 使用 Optional 链式调用 (Java)

示例:
  ❌ Bad (Java):
    String city = user.getAddress().getCity().getName();  // NPE!
  
  ✅ Good (Java):
    String city = Optional.ofNullable(user)
        .map(User::getAddress)
        .map(Address::getCity)
        .map(City::getName)
        .orElse("Unknown");
```

---

### BOUNDARY 组 — 边界处理规则

#### BOUND-04: 除法运算除零保护
```yaml
规则ID: BOUND-04
名称: "除法运算除零保护"
方法来源: 错误推测
严重程度: BLOCKER
描述: 除法(/, //, %, div)运算的除数可能是零或来自外部输入且未做零值检查

检测模式:
  - 识别所有除法和取模运算
  - 除数为: 变量、参数、外部输入、函数返回值
  - 运算前无 != 0 / > 0 / != null 等零值检查
  - 注意: 常量字面量作为除数不需要检查

修复建议:
  "if divisor == 0: raise ZeroDivisionError(...) / return safe_default"

示例:
  ❌ Bad:
    avg = total / count           # ZeroDivisionError
    ratio = success / total * 100 # ZeroDivisionError
  
  ✅ Good:
    def safe_divide(a, b, default=0):
        if b == 0:
            return default
        return a / b
    
    avg = safe_divide(total, count)
    percentage = safe_divide(success, total, default=0) * 100
```

#### BOUND-03: 整数运算溢出风险
```yaml
规则ID: BOUND-03
名称: "整数运算溢出风险"
方法来源: 边界值分析
严重程度: CRITICAL
描述: 整数运算可能导致溢出，特别是乘法和大数累加场景

检测模式:
  - int/int64/long 类型的乘法运算: a * b
  - 大数累加: sum += large_value (循环内)
  - 数组长度计算涉及乘法: len * sizeof
  - 无 Math.multiplyExact / overflow 检查 / BigInteger 使用

修复建议:
  - 使用 Math.addExact / multiplyExact (Java)
  - 检查是否超过 Integer.MAX_VALUE / Long.MAX_VALUE
  - 大数场景使用 BigInteger

示例:
  ❌ Bad:
    total = price * quantity          # 溢出风险
    offset = row * columns + col      # 溢出风险
  
  ✅ Good (Java):
    try {
        total = Math.multiplyExact(price, quantity);
    } catch (ArithmeticException e) {
        throw new BusinessException("Calculation overflow");
    }
```

---

### EXCEPTION 组 — 异常处理规则

#### EXCP-01: 空catch块（异常被吞掉）
```yaml
规则ID: EXCP-01
名称: "空catch块（异常被静默吞掉）"
方法来源: 错误推测
严重程度: CRITICAL
描述: catch块体为空或仅有注释，异常被完全忽略，问题难以排查

检测模式:
  - catch (Exception e) { }  或  except Exception: pass
  - catch块内只有: // todo, // ignore, log无实际内容
  - 至少应有: logger.error(e) 或 throw 或 返回错误码

修复建议:
  - 至少记录日志: logger.error("Operation failed", e)
  - 或者向上抛出: throw new WrappedException(e)
  - 或者返回明确错误: return Result.error(e.getMessage())

示例:
  ❌ Bad:
    try {
        risky_operation()
    } except Exception:
        pass                    # 完全吞掉异常!
  
  ✅ Good:
    try:
        risky_operation()
    except Exception as e:
        logger.error(f"risky_operation failed: {e}", exc_info=True)
        raise                  # 或包装后重新抛出
```

#### EXCP-02: 宽泛异常捕获
```yaml
规则ID: EXCP-02
名称: "宽泛异常捕获(Exception/e/Throwable)"
方法来源: 错误推测
严重程度: MAJOR
描述: 使用过于宽泛的异常类型捕获，可能掩盖真正的程序错误

检测模式:
  - catch (Exception e), catch (Throwable t), except Exception
  - 应优先捕获具体的异常类型
  - 例外: 最外层的全局兜底可以捕获Exception

修复建议:
  替换为具体异常类型:
  - FileNotFoundError, ValueError, KeyError (Python)
  - IOException, SQLException, IllegalArgumentException (Java)

示例:
  ❌ Bad:
    try:
        config = load_config(path)
    except Exception as e:         # 太宽泛
        handle_error(e)
  
  ✅ Good:
    try:
        config = load_config(path)
    except FileNotFoundError:
        logger.error(f"Config file not found: {path}")
        use_default_config()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config: {path}, {e}")
        raise
```

#### EXCP-03: 异常后资源未释放
```yaml
规则ID: EXCP-03
名称: "异常发生时资源未被正确释放"
方法来源: 错误推测
严重程度: CRITICAL
描述: 打开的资源(file/connection/socket/lock)在异常发生时未能关闭

检测模式:
  - open() / getConnection() / new Socket() / acquire() 后的操作
  - 如果存在 try-except 但没有 finally / with / using
  - 资源不在 try-with-resources 语句中

修复建议:
  Python: 使用 with statement
  Java: 使用 try-with-resources (TWR)
  C#: 使用 using statement

示例:
  ❌ Bad (Python):
    f = open("data.txt")
    data = f.read()
    process(data)    # 若process抛异常,f不会关闭!
    f.close()        # 这行不会执行
  
  ✅ Good (Python):
    with open("data.txt") as f:
        data = f.read()
        process(data)   # 无论是否异常, f都会关闭
  
  ✅ Good (Java):
    try (Connection conn = dataSource.getConnection()) {
        conn.executeQuery(sql);   // 自动关闭
    }
```

---

### LOGIC 组 — 逻辑完整性规则

#### LOGIC-02: switch/default缺失
```yaml
规则ID: LOGIC-02
名称: "switch语句缺少default分支"
方法来源: 等价类划分
严重程度: CRITICAL
描述: switch/case语句缺少default分支，无法处理意外值

检测模式:
  - switch(expr) { ... } 无default子句
  - match expr { ... } 无 _ 通配分支 (Rust/Swift/Scala)

修复建议:
  添加 default 分支:
  "default: throw new IllegalArgumentException(\"Unexpected: \" + value)"

示例:
  ❌ Bad:
    switch(type) {
        case "A": handleA(); break;
        case "B": handleB(); break;
    }   // 其他值被静默忽略
  
  ✅ Good:
    switch(type) {
        case "A": handleA(); break;
        case "B": handleB(); break;
        default: throw new IllegalArgumentException("Unknown type: " + type);
    }
```

#### LOGIC-05: 条件判断永真/永假
```yaml
规则ID: LOGIC-05
名称: "条件判断恒为真或恒为假(死代码)"
方法来源: 错误推测
严重程度: CRITICAL
描述: if条件永远成立或永远不成立，说明逻辑有误或存在死代码

检测模式常见情况:
  - if (x = 5) vs if (x == 5) — 赋值vs比较 (C/C++/JavaScript)
  - if (true) ... if (false) — 硬编码布尔值
  - if (x > x) — 永远false
  - if (str.equals(str)) — 永远true
  - if (optional.isPresent() == true) — 冗余但非bug
  - if (x && !x) — 永远false
  - if (x || !x) — 永远true

修复建议:
  - 检查是否本意是比较(==)而非赋值(=)
  - 移除死代码
  - 检查逻辑表达式是否写错

示例:
  ❌ Bad:
    if (status = ACTIVE) {     // 赋值! 永远为真(C风格语言)
        ...
    }
    if (result && !result) {   // 永远为假
        ...
    }
  
  ✅ Good:
    if (status == ACTIVE) {    // 比较
        ...
    }
    if (hasData && isValid) {   // 合理的条件组合
        ...
    }
```

---

### RESOURCE 组 — 资源管理规则

#### RESC-01: 资源未关闭(无try-with/with/using)
```yaml
规则ID: RESC-01
名称: "IO/连接资源未使用安全释放模式"
方法来源: 错误推测
严重程度: CRITICAL
描述: 打开了文件/数据库连接/网络连接/流，但未使用语言提供的安全释放语法

检测模式:
  Java:
    - new FileInputStream(...) / getConnection() / new Scanner(...)
    - 不在 try(...) 中
    - 手动close()但在try块中且无finally保证
  
  Python:
    - open(...) / urlopen() / connect()
    - 不在 with 语句中
    - 手动 .close() 但可能在异常时跳过

修复建议:
  全部改用 try-with-resources / with statement / using

示例:
  ❌ Bad (Java):
    InputStream is = new FileInputStream("file.txt");
    byte[] data = is.readAllBytes();  // 异常则泄漏
    is.close();

  ✅ Good (Java):
    try (InputStream is = new FileInputStream("file.txt")) {
        byte[] data = is.readAllBytes();
    }  // 自动关闭
```

---

### CONCURRENT 组 — 并发安全规则

#### CONC-01: 共享可变变量无同步
```yaml
规则ID: CONC-01
名称: "共享可变变量缺乏同步保护"
方法来源: 缺陷模式库
严重程度: CRITICAL
描述: 多个线程/协程可能同时读写同一个共享可变变量，但无任何同步机制

检测模式:
  - 类级别的实例变量(static field / class attribute)在非private方法中被修改
  - 无 synchronized / Lock / mutex / atomic / threading.Lock 保护
  - 该类看起来会在多线程环境中使用(extends Thread / implements Runnable / 有async方法)

修复建议:
  - 使用线程安全容器: ConcurrentHashMap, AtomicInteger
  - 加锁: synchronized / ReentrantLock / threading.Lock
  - 使用不可变数据结构

示例:
  ❌ Bad (Java):
    public class Counter {
        private int count = 0;          // 共享可变
        public void increment() {
            count++;                    // 非原子操作! 无同步!
        }
        public int getCount() { return count; }
    }

  ✅ Good (Java):
    public class Counter {
        private final AtomicLong count = new AtomicLong(0);
        public void increment() { count.incrementAndGet(); }
        public long getCount() { return count.get(); }
    }
```

#### CONC-02: 非原子check-then-act
```yaml
规则ID: CONC-02
名称: "先检查后操作的竞态条件"
方法来源: 缺陷模式库
严重程度: CRITICAL
描述: 先读取共享状态的值进行判断，然后基于判断结果执行操作，两步之间可能被其他线程打断

检测模式:
  - if (map.containsKey(k)) { map.put(k, v); } — 典型模式
  - if (list.isEmpty()) { list.add(item); }
  - if (instance == null) { instance = create(); }
  - 两步之间无锁保护

修复建议:
  - 使用原子方法: putIfAbsent, computeIfAbsent
  - 将check-and-act放在同步块内
  - 使用 ConcurrentMap 的复合操作

示例:
  ❌ Bad:
    if (cache.get(key) == null) {     // check
        cache.put(key, value);        // act — 竞态!
    }

  ✅ Good:
    cache.computeIfAbsent(key, k -> value);   // 原子操作
    // 或
    synchronized(lock) {
        if (cache.get(key) == null) {
            cache.put(key, value);
        }
    }
```

---

### STORAGE 组 — 存储/磁盘/权限规则 ⭐

> 所有涉及"把数据/文件写到某处"的代码都应检查本组规则。
> 方法论参见 `boundary-techniques.md` 维度 D9。

#### STORAGE-01: 写入前未检查剩余磁盘空间
```yaml
规则ID: STORAGE-01
名称: "写入前未检查剩余磁盘空间"
方法来源: 边界值分析
严重程度: CRITICAL
描述: 在下载/导出/备份等大量写入前，未调用磁盘空间检查API，导致写入失败无预警

检测模式:
  触发: 存在大文件写入但 30 行内无空间检查
  正向信号（需存在至少一个）:
    - Java: `new StatFs(path).getAvailableBytes()` / `File.getFreeSpace()`
    - Kotlin: `StatFs(path).availableBytes`
    - Python: `shutil.disk_usage(path).free`
    - Node.js: `fs.statfs(...)` / `check-disk-space`
    - Swift: `URL.volumeAvailableCapacityKey`
    - C/C++: `GetDiskFreeSpaceEx` (Windows) / `statvfs` (POSIX)
  反向信号（有写入但缺少上面正向信号）:
    - `download(...)` / `FileOutputStream / FileWriter / open(..., 'wb')`
    - `writeFile / saveAs / export`

修复建议:
  - 下载/导出前预检空间 ≥ 预计写入大小 + 安全阈值
  - 不足时明确提示并终止（进入场景法备选流 C）
```

#### STORAGE-02: 存储权限未申请直接访问
```yaml
规则ID: STORAGE-02
名称: "存储权限未申请直接访问"
方法来源: 错误推测
严重程度: BLOCKER
适用: Android / iOS

检测模式:
  Android:
    - 存在 `Environment.getExternalStorageDirectory()` 或
      `MediaStore` / `ContentResolver.openInputStream(...)` 但
      未见 `ContextCompat.checkSelfPermission` / `ActivityResultContracts.RequestPermission`
    - targetSdk >= 33 未使用 READ_MEDIA_IMAGES/VIDEO/AUDIO 细分权限
  iOS:
    - 访问 Photos / Files / Documents 前未调用 PHPhotoLibrary.requestAuthorization
    - Info.plist 缺少 NSPhotoLibraryUsageDescription 等说明

修复建议:
  - 写入前执行权限状态机: 未申请→申请→授权/拒绝/部分授权处理
  - 拒绝后引导"设置"页面，不直接崩溃
```

#### STORAGE-03: 未处理路径异常（中文/空格/超长/特殊字符）
```yaml
规则ID: STORAGE-03
名称: "未处理路径异常"
方法来源: 边界值分析
严重程度: CRITICAL

检测模式:
  - 字符串拼接路径未使用 Path/Paths API
    Java: `str + "/" + str`    → 应使用 Paths.get()
    Python: `a + '/' + b`      → 应使用 os.path.join / Path
    Node.js: `a + '/' + b`     → 应使用 path.join
  - Windows 未处理 MAX_PATH 260 限制（长路径需 `\\?\` 前缀或启用 LongPathsEnabled）
  - 未对路径进行 trim / normalize / realpath
  - 用户输入直接作为文件名（含路径遍历风险，与 SECU-04 联动）

修复建议:
  - 使用平台中立的 Path API
  - 测试用例必须覆盖：中文/空格/emoji/>260字符/符号链接
```

#### STORAGE-04: 文件写入无完整性保护
```yaml
规则ID: STORAGE-04
名称: "文件写入无完整性保护(无临时文件+原子重命名)"
方法来源: 错误推测
严重程度: CRITICAL

描述: 写入过程被中断（断电/杀进程）会留下损坏的目标文件

检测模式:
  反向信号:
    - 直接 open(target, 'wb') / FileOutputStream(target) → 期望模式是先写临时文件再 rename
  正向信号（规避检测）:
    - 先 write to `target.tmp` / `target.part`，完整后 `Files.move(...StandardCopyOption.ATOMIC_MOVE)`

修复建议:
  - 写入模式：`write(target.tmp) → fsync → rename(target.tmp, target)`
  - 启动时扫描残留 `.tmp/.part` 清理
```

#### STORAGE-05: 写入失败后未清理临时文件
```yaml
规则ID: STORAGE-05
名称: "写入失败后未清理临时文件"
方法来源: 错误推测
严重程度: MAJOR

检测模式:
  - 创建了临时文件但 catch 分支未 delete
  - 下载暂停/取消后未清理 .part 文件

修复建议:
  - try/finally 或 使用上下文管理器（Python with / Java try-with）
  - 应用启动时兜底扫描清理
```

#### STORAGE-06: 未处理典型 I/O 异常
```yaml
规则ID: STORAGE-06
名称: "未处理 IOError/ENOSPC/EACCES/FileNotFound"
方法来源: 错误推测
严重程度: CRITICAL

检测模式:
  - open/read/write 无 try-catch
  - catch 后只 log 无用户提示 / 无恢复动作

必须明确处理的错误:
  - ENOSPC (No space left) / DiskFullException → 提示空间不足
  - EACCES / PermissionException → 引导授权
  - ENOENT / FileNotFoundException → 友好提示+重试
  - EROFS (Read-only FS) / 只读介质 → 回退到可写位置
```

#### STORAGE-07: localStorage/SP 写入无异常保护
```yaml
规则ID: STORAGE-07
名称: "localStorage/SharedPreferences 写入无 try-catch"
方法来源: 错误推测
严重程度: MAJOR
适用: JS/TS / Android

检测模式:
  JS: `localStorage.setItem(...)` 无 try-catch
    → 超限抛 `QuotaExceededError`
  Android: SharedPreferences.Editor.commit/apply 后未判断返回值/未捕获异常
  iOS: UserDefaults 大对象未监控大小

修复建议:
  - try-catch 包裹 + 降级：清理最旧数据/提示用户
  - 大对象改用文件/IndexedDB/SQLite
```

#### STORAGE-08: 硬编码路径/平台分隔符
```yaml
规则ID: STORAGE-08
名称: "硬编码绝对路径或平台专属分隔符"
方法来源: 缺陷模式
严重程度: MAJOR

检测模式:
  - 正则: `/(sdcard|data|Users|home|opt|var)\/` 出现在字符串字面量
  - 正则: 代码中混用 `\\` 和 `/`
  - Windows 风格 `C:\\xxx` 或 `\\?\xxx` 硬编码

修复建议:
  - 使用标准目录 API: Environment.getExternalFilesDir / NSSearchPathForDirectoriesInDomains / os.path.expanduser
  - 路径拼接用 Path.join
```

#### STORAGE-09: 未检测外部存储挂载状态
```yaml
规则ID: STORAGE-09
名称: "未检测外部存储挂载状态"
方法来源: 错误推测
严重程度: MAJOR
适用: Android / Desktop

检测模式:
  Android: 使用外部存储但未调用 `Environment.getExternalStorageState()` 判断 MEDIA_MOUNTED
  Desktop: 访问 U 盘 / 网络盘未处理设备消失

修复建议:
  - 读写前判断挂载
  - 监听介质变更事件 (Android StorageEventListener / Win32 WM_DEVICECHANGE)
```

#### STORAGE-10: 大文件同步 I/O 阻塞主线程
```yaml
规则ID: STORAGE-10
名称: "大文件同步读写阻塞主线程/UI线程"
方法来源: 性能
严重程度: CRITICAL

检测模式:
  - 在 UI 线程 / 主线程中执行大文件 I/O
    Android: StrictMode 会提示 DiskReadViolation
    JS: 使用 readFileSync 在渲染进程
    Swift: MainActor 中同步 I/O

修复建议:
  - 异步化: Android 用 Coroutine/RxJava / JS 用 fs.promises / Swift 用 async-await
  - 进度回调到 UI
```

#### STORAGE-11: 权限运行时撤销未感知
```yaml
规则ID: STORAGE-11
名称: "权限运行时撤销未感知"
方法来源: 错误推测
严重程度: MAJOR
适用: Android / iOS

描述: 用户在运行中去系统设置撤销存储权限，App 继续读写会崩溃

检测模式:
  - 长生命周期的读写循环未在每次 I/O 前判断权限
  - 未监听 onActivityResult / permission revoke 事件

修复建议:
  - 每次读写前 checkSelfPermission
  - 捕获 SecurityException 优雅降级
```

#### STORAGE-12: 卸载/清数据时敏感数据未彻底清除
```yaml
规则ID: STORAGE-12
名称: "卸载/清数据时敏感/私有数据未彻底清除"
方法来源: 安全/合规
严重程度: CRITICAL

描述: 隐私合规要求"用户卸载后残留为零"；静默残留触发监管事故

检测模式:
  - 数据写入在多个位置（数据库/SP/Keychain/外部存储/Cookie/IndexedDB）但
    卸载/退出流程只清理了一部分
  - 敏感数据（token/密码/身份证/手机号）落盘未加密

修复建议:
  - 建立"清除清单"覆盖全部落盘点
  - 敏感数据加密存储 + 卸载时同步清除
```

#### STORAGE-13: 存储 schema 迁移无版本号判断
```yaml
规则ID: STORAGE-13
名称: "DB/文件 schema 迁移无版本号判断"
方法来源: 错误推测
严重程度: CRITICAL

检测模式:
  - SQLite 升级未实现 onUpgrade / migrate
  - 本地 JSON 配置文件直接读取，新字段缺失抛异常
  - iOS CoreData 缺 Migration Plan

修复建议:
  - 所有持久化结构带 version 字段
  - 升级时检查 version 并执行迁移脚本
  - 参考 test-strategy HIST-01 数据迁移策略
```

#### STORAGE-14: 同一文件并发写无锁保护
```yaml
规则ID: STORAGE-14
名称: "同一文件多进程/多线程并发写无锁保护"
方法来源: 并发
严重程度: CRITICAL

检测模式:
  - 多线程共享 FileWriter/FileOutputStream 无 synchronized
  - 多进程写同一日志文件无 file lock (`flock` / `LockFileEx`)

修复建议:
  - Java: FileChannel.lock()
  - Python: fcntl.flock / portalocker
  - Node.js: proper-lockfile
  - 设计上规避并发写：每进程独立文件名 + 日志合并
```

---

### SECURITY 组 — 安全规则

#### SECU-01: SQL注入风险
```yaml
规则ID: SECU-01
名称: "SQL拼接注入风险"
方法来源: AI缺陷模式库
严重程度: BLOCKER
描述: 使用字符串拼接构建SQL查询，用户输入可直接注入SQL代码

检测模式:
  - "SELECT ... " + variable / f"SELECT ... {var}" / "SELECT ... ${var}"
  - execute("..." + userInput) / raw(sql_string)
  - 未使用参数化查询: ? / :param / %s / $1
  - ORM框架中的 raw/rawsql/execute_sql 方法中使用字符串拼接

修复建议:
  全部改为参数化查询:
  - JDBC: PreparedStatement
  - SQLAlchemy: text(query).bindparams(k=v)
  - Django: Model.objects.filter(field=value)
  - MyBatis: #{param} (不要用 ${param})

示例:
  ❌ Bad:
    query = f"SELECT * FROM users WHERE name = '{user_input}'"   # 注入!
    cursor.execute(query)
  
  ✅ Good:
    query = "SELECT * FROM users WHERE name = %s"
    cursor.execute(query, (user_input,))   # 参数化,安全
```

#### SECU-02: XSS风险
```yaml
规则ID: SECU-02
名称: "跨站脚本攻击(XSS)风险"
方法来源: AI缺陷模式库
严重程度: BLOCKER
描述: 用户输入未经转义直接渲染到HTML页面中

检测模式:
  - innerHTML = userInput / dangerouslySetInnerHTML={userInput}
  - response.write(user_input) / echo $user_input (模板中无escape)
  - jQuery $(selector).html(userVar)
  - v-html="userContent" (Vue)
  - [innerHTML] = "userStr" (Angular)

修复建议:
  - 使用textContent代替innerHTML
  - 模板引擎默认开启auto-escape
  - 对输出进行HTML实体编码
  - 使用CSP(Content Security Policy)额外防护

示例:
  ❌ Bad:
    element.innerHTML = userComment       // XSS!
    document.write(searchQuery)           // XSS!

  ✅ Good:
    element.textContent = userComment     // 安全,自动转义
    element.innerHTML = escapeHtml(userComment) // 显式转义
```

#### SECU-03: 硬编码密钥/凭证
```yaml
规则ID: SECU-03
名称: "硬编码敏感信息(密钥/密码/Token/API Key)"
方法来源: AI缺陷模式库
严重程度: CRITICAL
描述: 密钥、密码、API Key等敏感信息以明文硬编码在源码中

检测模式:
  - password = "...", secret = "...", api_key = "...", token = "..."
  - 字符串值为: 长度>16的随机字符串, 含 "sk-" "ghp_" "AKIA" 等前缀
  - 排除: 明显的测试/示例值 ("password", "test-key", "xxx")

修复建议:
  - 使用环境变量: os.getenv("SECRET_KEY")
  - 使用密钥管理系统: AWS Secrets Manager, HashiCorp Vault
  - 使用配置中心: Spring Cloud Config, Apollo
  - 最低要求: 配置文件(.env/.properties)不入版本控制

示例:
  ❌ Bad:
    API_KEY = "sk-abc123456789xyz"      # 泄露风险!
    DB_PASSWORD = "SuperSecretPass123"  # 泄露风险!
  
  ✅ Good:
    API_KEY = os.environ.get("API_KEY")
    if not API_KEY:
        raise ValueError("API_KEY environment variable not set")
```

#### SECU-07: 敏感信息日志输出
```yaml
规则ID: SECU-07
名称: "日志中输出敏感信息"
方法来源: AI缺陷模式库
严重程度: CRITICAL
描述: 日志中打印了密码、Token、身份证号、银行卡号等敏感数据

检测模式:
  - logger.info/debug/warn 中包含: password, passwd, pwd, secret, token, credit_card, ssn, id_card
  - print/console.log 中包含上述关键字
  - request/response 对象整体序列化到日志(可能含敏感header/body)

修复建议:
  - 脱敏处理: mask_password(pwd) → "****"
  - 仅记录必要字段,排除敏感字段
  - 生产环境日志级别设为INFO以上,避免DEBUG泄露

示例:
  ❌ Bad:
    logger.info(f"User login: {username}, password={password}")
    logger.debug(f"Request: {request.__dict__}")  # 可能含token
  
  ✅ Good:
    logger.info(f"User login attempt: username={username}")
    # 密码绝对不出现在任何日志中
```

---

### AI-CODE 组 — AI代码专项规则

#### AICD-01: AI幻觉 — API调用不存在或签名错误
```yaml
规则ID: AICD-01
名称: "调用了不存在的API或使用了错误的签名"
方法来源: AI缺陷模式库(#2幻觉)
严重程度: BLOCKER
描述: AI生成的代码可能编造不存在的库函数名、方法名、参数名或使用错误的签名

检测模式:
  - 需要配合项目依赖解析:
    - 代码中 import/require/from 的模块是否存在
    - 调用的方法在该模块/类中是否存在
    - 方法签名(参数数量和类型)是否匹配
  - 高频幻觉模式:
    - .format() 用于 datetime (Python中是 strftime)
    - .toJson() 用于普通对象 (应该是 JSON.stringify / json.dumps)
    - str.trim().toLowerCase() (Python中是 strip().lower())
    - 不存在的 pandas 方法 (.read_csv 的错误参数)

修复建议:
  - 必须通过编译器/解释器执行确认
  - IDE中开启类型检查和自动补全
  - 单元测试必须真实运行(不能mock掉被测方法)

示例 (AI幻觉典型):
  ❌ Bad (Python - AI幻觉):
    df = pd.read_csv("file.csv", encoding='utf8', delimiter=',')
    result = df.groupBy('category').agg('mean')  # groupBy不存在! 应该是 groupby
    date_str = now.format("%Y-%m-%d")             # format不存在! 应该是 strftime
  
  ✅ Good:
    df = pd.read_csv("file.csv")
    result = df.groupby('category').mean()
    date_str = now.strftime("%Y-%m-%d")
```

#### AICD-02: 只处理happy path无异常路径
```yaml
规则ID: AICD-02
名称: "只实现了正常流程,缺少异常/边缘路径处理"
方法来源: AI缺陷模式库(#1边界缺失,出现率35%)
严重程度: CRITICAL
描述: AI倾向于生成最简的正确代码，只处理正常的输入情况，忽略各种异常路径

检测模式:
  - 函数体中只有正常业务逻辑
  - 无 try-except / try-catch 结构
  - 无 if-error 检查
  - 无默认值/兜底逻辑
  - 函数涉及: I/O操作, 网络请求, 数据库操作, 外部API调用

修复建议:
  为每个可能失败的操作添加:
  - try-except + error handling
  - 或 Result/Either 类型返回
  - 至少要有 fallback/default value

示例:
  ❌ Bad (AI典型输出):
    def fetch_user_data(user_id):
        response = requests.get(f"{BASE_URL}/users/{user_id}")  # 可能超时/500
        data = response.json()                                  # 可能JSON解码失败
        return data["name"]                                    # 可能KeyError
  
  ✅ Good:
    def fetch_user_data(user_id):
        try:
            response = requests.get(
                f"{BASE_URL}/users/{user_id}",
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            return data.get("name", "Unknown")
        except requests.Timeout:
            logger.warning(f"Timeout fetching user {user_id}")
            return None
        except (requests.HTTPError, ValueError, KeyError) as e:
            logger.error(f"Failed to fetch user {user_id}: {e}")
            return None
```

#### AICD-06: 魔法数字未提取为常量
```yaml
规则ID: AICD-06
名称: "魔法数字(Magic Number)未提取为命名常量"
方法来源: AI缺陷模式库
严重程度: MAJOR
描述: 代码中出现未命名的数字字面量，含义不清晰且难以维护

检测模式:
  - 数字字面量出现在代码中(非0, 1, -1, 0.0, 1.0等通用值)
  - 数字不是明显自解释的(如24*60*60表示秒数尚可,但1428就不行)
  - 同一数字出现多次但每次含义不同
  - 排除: 初始值0/1, 步进1, 标志位0/-1/1, 数学常数

修复建议:
  - 定义命名常量: MAX_RETRY_COUNT = 3, TIMEOUT_SECONDS = 30
  - 使用枚举替代相关联的一组数字

示例:
  ❌ Bad:
    if retry_count > 3:              # 3是什么?
        timeout = 30                  # 30是什么?
        page_size = 20                # 20是什么?
    
  ✅ Good:
    MAX_RETRIES = 3
    REQUEST_TIMEOUT_SEC = 30
    DEFAULT_PAGE_SIZE = 20
    
    if retry_count > MAX_RETRIES:
        timeout = REQUEST_TIMEOUT_SEC
        page_size = DEFAULT_PAGE_SIZE
```

---

### PERF 组 — 性能规则

#### PERF-01: N+1查询模式
```yaml
规则ID: PERF-01
名称: "N+1查询问题(循环内执行数据库查询)"
方法来源: 缺陷模式库
严重程度: CRITICAL
描述: 在循环体内执行数据库查询，导致N条数据触发N+1次DB查询

检测模式:
  - for/while/foreach 循环内部
  - 包含: Session.query / db.session / connection.execute / Model.objects.get/find
  - / SELECT / .find() / .query()
  - 查询参数引用了循环变量

修复建议:
  - 改为批量查询: WHERE IN (...) / batch_get
  - 使用ORM的 eager loading: joinedload / select_related / prefetch_related
  - 先批量获取再内存中关联

示例:
  ❌ Bad:
    for order in orders:
        user = db.query(User).filter_by(id=order.user_id).first()  # N次查询!
        order.user_name = user.name
  
  ✅ Good:
    # 批量查询,只查1次
    user_ids = list(set(o.user_id for o in orders))
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
    for order in orders:
        order.user_name = users[order.user_id].name
```

#### PERF-04: 字符串循环拼接
```yaml
规则ID: PERF-04
名称: "循环中使用+拼接字符串(O(n²)复杂度)"
方法来源: 边界值分析
严重程度: MAJOR
描述: 在循环中使用 + 运算符拼接字符串，时间复杂度为O(n²)

检测模式:
  - for/while 循环内部
  - result += something 或 result = result + something
  - result 是字符串类型
  - 循环次数不确定或可能较大

修复建议:
  Python: 使用 ''.join(list) 或 io.StringIO
  Java: 使用 StringBuilder
  JavaScript: 使用 Array.join() 或模板字符串(少量时)

示例:
  ❌ Bad (Python):
    result = ""
    for item in large_list:
        result += item + ","    # O(n²)!
  
  ✅ Good (Python):
    result = ",".join(str(item) for item in large_list)  # O(n)
    
  # 或大量拼接时:
  buf = StringIO()
    for item in large_list:
        buf.write(str(item))
        buf.write(",")
    result = buf.getvalue()
```

---

## REQ 组 — 需求文档分析规则 (多来源适配)

> ⚠️ **按需加载提示**: 以下 REQ 组规则（约 530 行）仅在进行**需求文档扫描**时需要加载。
> 纯代码扫描场景可跳过此部分。
>
> 以下规则用于从需求文档中提取测试关注点，支持**文本文档、图片需求文档、Figma设计稿**三类来源。
> 在代码扫描前，先对需求进行预处理和分析，确保生成的代码覆盖了需求中的所有场景。

### 需求来源适配架构

```
┌──────────────────────────────────────────────────────────────┐
│                   多来源需求 → 统一规则引擎                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  来源A: 文本需求文档 (PRD/用户故事/需求规格说明书)             │
│  ├── 直接提取: 业务规则、验收条件、约束条件                   │
│  ├── 解析方式: 正则 + NLP关键词匹配 + LLM语义理解             │
│  └── 输出: 需求规则清单 (requirement_rules.json)              │
│                                                              │
│  来源B: 图片需求文档 (截图/手绘草图/PDF扫描件)                │
│  ├── OCR识别: 将图片中的文字提取为文本                        │
│  ├── 视觉元素识别: 表格/流程图/状态图中的分支和状态           │
│  ├── 解析方式: OCR + 多模态LLM(GPT-4V/Claude Vision)         │
│  └── 输出: 需求规则清单 (requirement_rules.json)              │
│                                                              │
│  来源C: Figma/设计稿 (交互原型/UI设计/标注文件)               │
│  ├── API提取: 通过Figma API获取组件树/交互标注/设计Token      │
│  ├── 交互分析: 按钮状态、表单校验规则、页面跳转逻辑           │
│  ├── 标注解析: 尺寸约束、颜色规范、字体要求                   │
│  ├── 解析方式: Figma REST API + 设计Token解析 + LLM           │
│  └── 输出: UI规则清单 (ui_rules.json)                         │
│                                                              │
│  统一 ─────→ 规则化引擎 ─────→ 代码扫描规则                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### REQ-TEXT: 文本需求文档分析规则

#### REQ-TEXT-01: 需求边界条件提取
```yaml
规则ID: REQ-TEXT-01
名称: "从需求文档提取边界条件"
方法来源: 边界值分析
严重程度: CRITICAL
适用来源: 文本需求文档(PRD/用户故事/BRD/AC)

提取模式:
  关键词匹配:
    - 范围类: "不超过|至少|最多|最少|大于|小于|等于|范围|限制|区间|上限|下限"
    - 数量类: "N个|M条|最大值|最小值|最多允许|不得超过|至多|至少"
    - 长度类: "长度|字数|字符数|不超过X位|最长|最短"
    - 时间类: "X天内|超时|过期|有效期|T+N|XX秒后"
    - 金额类: "最低消费|封顶|限额|免密|起步"
  
  结构化提取:
    - 从验收条件(AC)中提取 Given/When/Then 的边界参数
    - 从约束表格中提取 min/max/default/required 字段
    - 从业务规则列表中提取条件判断的临界值

输出格式:
  {
    "boundaries": [
      {"field": "username", "min_length": 2, "max_length": 20},
      {"field": "amount", "min": 0.01, "max": 999999.99},
      {"field": "retry_count", "max": 3, "timeout_sec": 30}
    ]
  }

代码验证:
  提取出的边界必须在代码中有对应的校验逻辑
  如 "用户名不超过20个字符" → 代码中必须有 len(username) <= 20 的检查
```

#### REQ-TEXT-02: 需求等价类提取
```yaml
规则ID: REQ-TEXT-02
名称: "从需求文档提取等价类/状态枚举"
方法来源: 等价类划分
严重程度: CRITICAL
适用来源: 文本需求文档

提取模式:
  关键词匹配:
    - 状态类: "状态|阶段|流程|生命周期|流转|变更"
    - 角色类: "角色|权限|类型|分类|级别|等级"
    - 枚举类: "包括|分为|分别|可选|支持以下类型"
    - 条件类: "当...时|如果...则|若...则|分支|场景"
  
  结构化提取:
    - 从流程描述中提取所有状态节点
    - 从角色权限表中提取角色列表
    - 从业务规则中提取条件分支

输出格式:
  {
    "equivalence_classes": [
      {"field": "order_status", "valid": ["pending","paid","shipped","delivered"], "invalid": ["unknown","null","empty"]},
      {"field": "user_role", "valid": ["admin","editor","viewer"], "invalid": ["superadmin","hacker"]}
    ]
  }

代码验证:
  - 代码中的switch/if-elif必须覆盖需求中列举的所有状态
  - 必须有default/else处理需求未定义的异常状态
```

#### REQ-TEXT-03: 需求因果关系提取
```yaml
规则ID: REQ-TEXT-03
名称: "从需求中提取因果条件组合"
方法来源: 因果图法
严重程度: MAJOR
适用来源: 文本需求文档

提取模式:
  关键词匹配:
    - 因果类: "当...且...时|同时满足|或者|并且|除非|否则|当且仅当"
    - 依赖类: "前提是|必须先|依赖于|基于|在...条件下"
    - 互斥类: "不能同时|互斥|二选一|只能选择一个"
    - 约束类: "至少一个|最多一个|恰好|有且仅有"

输出格式:
  {
    "cause_effects": [
      {
        "causes": ["is_vip", "order_amount > 100"],
        "effect": "apply_double_discount",
        "logic": "AND"
      },
      {
        "causes": ["is_expired", "is_cancelled"],
        "effect": "deny_refund",
        "logic": "OR"
      }
    ]
  }

代码验证:
  - 代码中的多条件判断必须覆盖需求中定义的所有因果组合
  - 特别注意因果图中的"约束"(互斥/包含/唯一/要求)
```

### REQ-IMAGE: 图片需求文档分析规则

#### REQ-IMAGE-01: 图片OCR文本提取+规则化
```yaml
规则ID: REQ-IMAGE-01
名称: "图片需求文档OCR解析与规则提取"
方法来源: 多模态分析
严重程度: CRITICAL
适用来源: 截图/手绘草图/PDF扫描件/白板照片

解析流程:
  Step 1 - OCR文本提取:
    工具选择:
      - Tesseract OCR (开源,适合标准文本)
      - PaddleOCR (中英文混合,表格优化)
      - Cloud Vision API (Google/Azure/腾讯云, 高精度)
    输出: 结构化文本(含坐标信息)

  Step 2 - 视觉元素识别:
    工具选择:
      - 多模态LLM (GPT-4V/Claude Vision/Qwen-VL)
      - YOLO + 自定义训练 (流程图/状态图识别)
    识别目标:
      - 表格 → 提取行列数据,识别字段约束
      - 流程图 → 提取节点+连线+判断分支
      - 状态图 → 提取状态列表+转换条件
      - 原型图 → 提取UI元素+交互约束

  Step 3 - 规则转换:
    对识别出的文字和结构应用 REQ-TEXT-01~03 的规则提取逻辑

Prompt模板 (用于多模态LLM):
  ```
  你是一个测试分析专家。请分析以下需求文档图片:
  1. 识别所有文字内容并结构化输出
  2. 识别流程图/状态图中的所有分支和状态转换
  3. 提取以下信息:
     - 数值边界条件 (最大值/最小值/范围)
     - 状态枚举 (所有可能的状态及转换)
     - 条件组合 (多条件的逻辑关系)
     - 异常场景 (错误提示/降级策略)
  4. 以JSON格式输出提取结果
  ```

输出格式:
  {
    "source_type": "image",
    "ocr_text": "...",
    "visual_elements": {
      "flowcharts": [...],
      "state_diagrams": [...],
      "tables": [...],
      "ui_mockups": [...]
    },
    "extracted_rules": {
      "boundaries": [...],
      "equivalence_classes": [...],
      "cause_effects": [...]
    }
  }
```

#### REQ-IMAGE-02: UI原型图交互规则提取
```yaml
规则ID: REQ-IMAGE-02
名称: "从UI原型图提取交互规则和表单校验"
方法来源: 等价类划分 + 边界值分析
严重程度: CRITICAL
适用来源: UI原型截图/Axure导出图/手绘线框图

识别目标:
  表单元素:
    - 输入框 → 提取: placeholder(类型提示), 长度限制, 必填标记(*)
    - 下拉选择 → 提取: 选项列表(等价类)
    - 复选框/单选 → 提取: 互斥关系, 默认选中
    - 日期选择 → 提取: 日期范围, 格式要求
    - 文件上传 → 提取: 类型限制, 大小限制, 数量限制

  交互元素:
    - 按钮 → 提取: 启用/禁用条件, 点击后状态变化
    - 弹窗 → 提取: 触发条件, 确认/取消逻辑
    - 列表/表格 → 提取: 分页, 排序, 筛选规则
    - 标签页 → 提取: 切换逻辑, 数据联动

  错误提示:
    - Toast/Alert → 提取: 触发条件和提示文案
    - 表单校验红字 → 提取: 校验规则和提示内容
    - 空状态 → 提取: 何时显示, 引导操作

输出格式:
  {
    "ui_rules": [
      {"element": "email_input", "type": "text", "required": true,
       "validation": "email_format", "max_length": 100},
      {"element": "submit_btn", "enabled_when": "all_required_filled && no_errors"},
      {"element": "file_upload", "accept": [".jpg",".png",".pdf"],
       "max_size_mb": 10, "max_count": 5}
    ]
  }
```

### REQ-FIGMA: Figma设计稿分析规则

#### REQ-FIGMA-01: Figma组件树与交互分析
```yaml
规则ID: REQ-FIGMA-01
名称: "Figma设计稿组件树解析与交互规则提取"
方法来源: 等价类划分 + 因果图法
严重程度: CRITICAL
适用来源: Figma设计文件(通过API访问)

解析方式:
  Step 1 - Figma API数据获取:
    API: GET /v1/files/{file_key}
    获取: 组件树(nodes), 样式(styles), 原型交互(prototyping)
    
    ```python
    # Figma API调用示例
    import requests
    
    FIGMA_TOKEN = os.getenv("FIGMA_TOKEN")
    headers = {"X-Figma-Token": FIGMA_TOKEN}
    
    def get_figma_file(file_key):
        url = f"https://api.figma.com/v1/files/{file_key}"
        resp = requests.get(url, headers=headers)
        return resp.json()
    
    def get_figma_components(file_key):
        url = f"https://api.figma.com/v1/files/{file_key}/components"
        resp = requests.get(url, headers=headers)
        return resp.json()
    ```

  Step 2 - 组件类型识别与规则提取:
    INPUT类组件:
      识别: name包含 "input/field/text/search/email/phone"
      提取: placeholder, maxLength(从constraints), 必填标记
      生成: INPUT-01~04规则校验项

    SELECT/DROPDOWN类组件:
      识别: name包含 "select/dropdown/picker/menu"
      提取: option列表(从子节点文本)
      生成: INPUT-03枚举完备性校验项

    BUTTON类组件:
      识别: type=COMPONENT, name包含 "button/btn/cta"
      提取: variant状态(default/hover/disabled/loading)
      生成: 按钮状态机校验项

    FORM类组件:
      识别: 包含多个input的Frame/Group
      提取: 必填字段列表, 校验规则, 提交条件
      生成: 表单完整性校验清单

  Step 3 - 交互原型分析:
    获取: prototyping.flows (Figma原型流程)
    提取:
      - 页面跳转关系 (flow connections)
      - 触发条件 (trigger: ON_CLICK, ON_HOVER, etc.)
      - 动画/过渡 (transition)
      - 条件逻辑 (通过Variant切换推断)

输出格式:
  {
    "figma_source": {
      "file_key": "abc123",
      "file_name": "MyApp Design",
      "last_modified": "2026-04-10T00:00:00Z"
    },
    "components": [
      {
        "id": "node_1",
        "name": "Email Input",
        "type": "INPUT",
        "constraints": {"required": true, "format": "email", "max_length": 100}
      },
      {
        "id": "node_2",
        "name": "Order Status Dropdown",
        "type": "SELECT",
        "options": ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"]
      }
    ],
    "interactions": [
      {
        "trigger": "Submit Button Click",
        "source_page": "Order Form",
        "target_page": "Order Confirmation",
        "condition": "all_fields_valid"
      }
    ],
    "extracted_rules": {
      "boundaries": [...],
      "equivalence_classes": [...],
      "ui_rules": [...]
    }
  }
```

#### REQ-FIGMA-02: Figma设计Token与样式规范校验
```yaml
规则ID: REQ-FIGMA-02
名称: "Figma设计Token与代码实现一致性校验"
方法来源: 等价类划分 (视觉一致性)
严重程度: MAJOR
适用来源: Figma设计系统/Design Tokens

提取内容:
  颜色规范:
    - 从Figma Styles中提取颜色变量 → 检查代码CSS是否使用了规范颜色
    - 生成: CSS变量 / Tailwind config / Theme token
  
  字体规范:
    - font-family, font-size, font-weight, line-height
    - 检查代码中是否存在未引用设计规范的硬编码字体/字号
  
  间距/尺寸规范:
    - padding, margin, border-radius, width/height
    - 检查代码中的魔法数字是否应替换为设计Token
  
  组件状态规范:
    - 各组件的hover/active/disabled/error状态
    - 检查代码实现是否覆盖了所有设计中定义的状态

输出格式:
  {
    "design_tokens": {
      "colors": {"primary": "#1A73E8", "error": "#D93025", ...},
      "typography": {"heading-1": {"size": 24, "weight": 700}, ...},
      "spacing": {"xs": 4, "sm": 8, "md": 16, "lg": 24, ...},
      "border_radius": {"sm": 4, "md": 8, "lg": 16}
    },
    "component_states": {
      "Button": ["default", "hover", "active", "disabled", "loading"],
      "Input": ["default", "focus", "error", "disabled", "readonly"]
    }
  }
```

#### REQ-FIGMA-03: Figma交互流程与代码路由一致性
```yaml
规则ID: REQ-FIGMA-03
名称: "Figma原型交互流程与代码路由/状态机一致性"
方法来源: 因果图法 + 等价类划分
严重程度: CRITICAL
适用来源: Figma原型模式(Prototyping)

校验内容:
  页面路由完整性:
    - Figma中的每个页面/Frame → 代码中应有对应的路由
    - Figma中的跳转关系 → 代码中路由跳转逻辑的一致性
  
  交互逻辑完整性:
    - Figma中定义的点击事件 → 代码中对应的事件处理
    - Figma中的条件跳转 → 代码中的条件分支
    - Figma中的返回/后退 → 代码中的导航栈管理
  
  状态流转完整性:
    - Figma Variants定义的组件状态 → 代码中状态管理覆盖所有变体
    - 状态切换的触发条件 → 代码事件绑定完整

代码检查生成:
  从Figma交互数据自动生成以下代码检查项:
  - LOGIC-02: switch/路由是否覆盖所有Figma页面
  - INPUT-03: 状态枚举是否覆盖所有Figma Variants
  - AICD-02: 交互流程中的异常路径是否有代码处理(网络错误页/空状态页)
```

### 需求来源统一处理流程

```
┌──────────────────────────────────────────────────────────────────┐
│              需求 → 规则 → 代码扫描 统一流程                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 需求输入 (多来源)                                            │
│     ┌─────────┐  ┌─────────┐  ┌─────────┐                      │
│     │ 文本PRD │  │ 图片文档 │  │  Figma  │                      │
│     └────┬────┘  └────┬────┘  └────┬────┘                      │
│          │            │            │                             │
│  2. 预处理 (格式统一化)                                          │
│          │            │            │                             │
│     ┌────┴────┐  ┌────┴────┐  ┌────┴────┐                      │
│     │ NLP解析 │  │ OCR+VLM │  │ API解析 │                      │
│     └────┬────┘  └────┬────┘  └────┬────┘                      │
│          │            │            │                             │
│  3. 提取 (统一规则格式)                                          │
│          └────────────┼────────────┘                             │
│                       ↓                                          │
│          ┌─────────────────────────┐                            │
│          │  requirement_rules.json │  ← 统一的规则中间格式       │
│          │  ├── boundaries[]       │                             │
│          │  ├── equivalence_classes[]│                            │
│          │  ├── cause_effects[]    │                             │
│          │  ├── ui_rules[]         │                             │
│          │  └── design_tokens{}    │                             │
│          └────────────┬────────────┘                             │
│                       │                                          │
│  4. 规则映射 (需求→代码检查项)                                    │
│                       ↓                                          │
│          ┌─────────────────────────┐                            │
│          │ 生成代码扫描检查清单     │                            │
│          │ ├── 输入校验是否覆盖边界 │                            │
│          │ ├── 状态处理是否完备     │                            │
│          │ ├── 条件组合是否全覆盖   │                            │
│          │ ├── UI约束是否实现       │                            │
│          │ └── 设计规范是否一致     │                            │
│          └────────────┬────────────┘                             │
│                       │                                          │
│  5. 执行 (代码扫描)                                              │
│                       ↓                                          │
│          code-scanner.py --requirements requirement_rules.json   │
│                       │                                          │
│  6. 输出 (质量报告)                                              │
│                       ↓                                          │
│          quality_report.json / quality_report.html               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 规则配置与扩展

### 自定义规则格式

按照以下格式添加新规则:

```yaml
---
规则ID: RULE-XX
名称: "简短描述"
方法来源: 来源(边界值/等价类/因果图/正交实验/错误推测/AI缺陷模式/自定义)
严重程度: BLOCKER|CRITICAL|MAJOR|MINOR
描述: 一句话说明问题和影响
适用语言: ALL|Java|Python|JavaScript|TypeScript|Go|C/C++|...
检测模式:
  - 模式1: 正则/AST模式/语义描述
  - 模式2: ...
误报抑制:
  - 条件1: 何时不应报告
  - 条件2: ...
修复建议:
  具体的修复代码示例

示例:
  ❌ Bad: 反面示例
  ✅ Good: 正确示例
---
```

### 按项目定制规则集

```yaml
# rules-config.yaml (项目级规则配置)
project: my-project
language: python
rules:
  # 启用的规则
  enabled:
    - INPUT-01
    - INPUT-02
    - NULL-01
    - NULL-02
    - BOUND-04
    - EXCP-01
    - SECU-01
    - SECU-02
    - SECU-03
    - AICD-01
    - AICD-02
    - PERF-01
  
  # 禁用的规则及原因
  disabled:
    - rule: LOGIC-04
      reason: "项目允许浮点金额精确到分,不做高精度要求"
    - rule: AICD-05
      reason: "暂不强制要求文档注释"
  
  # 严格度调整
  severity_overrides:
    - rule: INPUT-03
      from: CRITICAL
      to: BLOCKER    # 本项目要求枚举完备性为阻断级
    - rule: PERF-04
      from: MAJOR
      to: MINOR     # 本项目字符串较小,不关注此问题
```
