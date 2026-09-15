# Moka 漏斗导出器

从 Moka 招聘系统抓每个职位的招聘漏斗数据,提供 Web 报告 + Excel 下载,供 HR 团队日常招聘复盘用。

## 上手 — 双击两个文件就行

```
1. 浏览器打开 https://github.com/lesue1/moka
   → 点绿色 "Code" 按钮 → "Download ZIP" → 解压到任意目录

2. 双击 install.bat (一次性,装 Python 依赖 + Playwright 浏览器,约 2-5 分钟)

3. 双击 start.bat (每次启动服务)
   → 浏览器自动打开 http://localhost:5000
   → 首次会让你填 Moka 账号密码(Web 页面填,不用碰文件)
   → 提交后自动弹浏览器完成登录(若有验证码手动处理)
   → 跳到漏斗报告页面

4. 用完了,关闭 start.bat 的 cmd 窗口 = 关闭服务
```

## 前提(只装一次)

电脑必须**已经装了 Python 3.10+**。检查方法:打开 cmd 跑 `python --version`,能打印出版本号就 OK。

没装的话去 https://www.python.org/downloads/ 下载,**安装时务必勾 "Add Python to PATH"**。

## 日常使用

启动后浏览器开 http://localhost:5000,看到漏斗报告页:
- 顶部:刷新按钮 + 下载 Excel 按钮
- 中部:统计概览(总职位数、总申请数)
- 表格:每个职位 × 9 个阶段漏斗 + 总数

点「下载 Excel」导出当前数据为 xlsx(文件名带时间戳,不会覆盖)。

session 失效时会自动弹浏览器让你重新登录(账号密码已存在 `.env`,不用重新填)。

## 常见问题

**Q: 双击 install.bat 报"没检测到 Python"**
A: 没装 Python 或 PATH 没配。去 python.org 下载,**勾 "Add Python to PATH"**。

**Q: 双击 start.bat 报"没找到虚拟环境 .venv"**
A: 没跑 install.bat 或装失败。重新双击 install.bat。

**Q: 浏览器开 http://localhost:5000 后没反应**
A: 可能 5000 端口被占。关掉 cmd 重开,或改 .env 里 FLASK_PORT=5001。

**Q: 弹出的浏览器里提示"登录超时(3 分钟)"**
A: 账号密码错了,或 moka 有验证码没处理。关浏览器,删 `.env`,重新双击 start.bat → 重新填账号。

**Q: 抓到的职位数比 Moka 后台少**
A: 删 `jobs_cache.json`,然后点页面「刷新」按钮(强制刷新职位缓存)。

**Q: 想换 moka 账号**
A: 删 `.env`,重新双击 start.bat → Web 表单重新填。

## 安全清单

- [ ] `.env` **绝不**入库(`.gitignore` 已配) — 含你的明文密码
- [ ] `moka_session.json` **绝不**入库 — 含你的 cookie
- [ ] `jobs_cache.json` **绝不**入库 — 含职位列表
- [ ] `exports/*.xlsx` **绝不**入库 — 含候选人姓名
- [ ] `.venv/` **绝不**入库 — Python 虚拟环境
- [ ] 没把账号密码写进任何代码、注释、issue

## 文件结构

```
moka-funnel-exporter/
├─ install.bat              # 同事双击:一次性装依赖
├─ start.bat                # 同事双击:启动服务 + 自动开浏览器
├─ app.py                   # Flask 主入口(同事用的 Web UI)
├─ moka_client.py           # Moka 接口客户端 + 登录
├─ funnel.py                # 候选人 stageName 漏斗统计
├─ exporter.py              # openpyxl 写 Excel
├─ templates/
│  ├─ index.html            # 漏斗报告页
│  ├─ login.html            # 首次账号密码表单
│  ├─ login_pending.html    # 等待浏览器登录完成页
│  └─ error.html            # 错误页
├─ .env.example             # 账号密码占位符
├─ .gitignore               # 排除敏感文件
├─ requirements.txt         # Python 依赖
├─ .venv/                   # 同事本地虚拟环境(自动生成,**不入库**)
├─ moka_session.json        # 登录态(自动生成,**不入库**)
├─ jobs_cache.json          # 职位缓存(自动生成,**不入库**)
└─ exports/                 # 导出的 Excel(可选,**不入库**)
```

## 技术栈

- **Flask 3.x** — Web 框架
- **Playwright** — 首次登录开浏览器(自动填账号密码,用户只处理验证码)
- **requests** — 调 Moka 后端接口
- **openpyxl** — 写 Excel
- **python-dotenv** — 读 `.env`

## 数据流

```
1. start.bat 启动 → Flask 起来 → webbrowser.open_new 打开 http://localhost:5000
2. 没 .env → 同事填账号密码(Web 表单) → save_credentials 写到 .env
3. 有 .env 没 session → Playwright headless=False 弹浏览器
   → 自动填账号密码 → 用户处理验证码 → 等 URL 变化 / cookie 出现
   → 登录成功 → storage_state 存到 moka_session.json
4. Flask 渲染 dashboard:
   - fetch_jobs_via_browser → POST paging 接口(pageSize=200)一次拿全 94 个职位
   - funnel_for_all_jobs → 对每个 jobId 调 search-candidate/v2 接口
   - 数 stageName → 9 阶段漏斗
5. 渲染 HTML 表格 / 写 Excel
```

## 反馈

有问题或建议,找 @陈洪新(原仓库维护者)。