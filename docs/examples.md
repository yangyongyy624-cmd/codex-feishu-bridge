# 使用示例

## 命令执行

### 基本命令

```
执行：echo hello
```

输出：
```
✅ 命令执行成功：
hello
```

### 复杂命令

```
执行：ls -la ~/Desktop | head -20
```

输出：
```
✅ 命令执行成功：
total 16
drwx------+  5 user  staff   160 May 30 10:00 .
drwxr-xr-x+ 20 user  staff   640 May 30 09:00 ..
-rw-r--r--   1 user  staff  1234 May 30 10:00 file.txt
...
```

### 后台运行

```
执行：python3 -m http.server 8000 &
```

输出：
```
✅ 命令执行成功（无输出）
```

## 打开网页

### 完整 URL

```
打开 https://www.google.com
```

输出：
```
✅ 已打开网页：https://www.google.com
```

### 关键词

```
打开 google
打开 百度
打开 github
```

输出：
```
✅ 已打开网页：https://www.google.com
```

## 打开应用

### 常用应用

```
打开 Google Chrome
打开 Safari
打开 Terminal
打开 Finder
打开 Xcode
打开 VSCode
```

输出：
```
✅ 已打开应用：Google Chrome
```

### 应用名称映射

| 输入 | 实际打开 |
|------|----------|
| Google 浏览器 | Google Chrome |
| 谷歌浏览器 | Google Chrome |
| 终端 | Terminal |
| 访达 | Finder |

## 列出文件

### 列出目录

```
列出桌面文件
查看 ~/Documents
```

输出：
```
✅ /Users/user/Desktop 目录内容：
total 16
drwx------+  5 user  staff   160 May 30 10:00 .
...
```

### 查看当前目录

```
列出文件
查看
```

输出：
```
✅ /Users/user 目录内容：
...
```

## AI 对话

### 一般问题

```
你好
帮我写一篇文章
解释一下量子计算
```

输出：
```
你好！我是智能助手...
```

### 代码问题

```
帮我写一个 Python 的快速排序算法
```

输出：
```python
def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    ...
```

## 组合使用

### 工作流示例

1. 生成文件
```
执行：echo "Hello World" > ~/Desktop/test.txt
```

2. 验证文件
```
查看 ~/Desktop/test.txt
```

3. 打开文件
```
打开 ~/Desktop/test.txt
```

## 最佳实践

### 命令格式

- 使用 `执行：` 前缀明确命令意图
- 命令尽量简洁
- 复杂命令使用引号包裹

### 应用名称

- 使用英文应用名称
- 不确定的应用名先查 `ls /Applications`

### 网址格式

- 优先使用完整 URL
- 常用网站可使用关键词

### 错误处理

- 命令执行失败会返回错误信息
- 根据错误信息调整命令
- 复杂命令建议先在终端测试
