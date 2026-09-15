# Moka 漏斗导出器

从 Moka 招聘系统抓每个职位的招聘漏斗数据,提供 Web 报告 + Excel 下载,供 HR 团队日常招聘复盘用。

## 上手(两行命令)

```bash
git clone <本仓库地址>
cd moka-funnel-exporter && pip install -r requirements.txt && playwright install chromium
```

然后:

1. 复制 `.env.example` 为 `.env`,**填入你自己的 Moka 账号密码**(不要用同事的)
2. `python moka_client.py login` — 第一次会打开浏览器,输完账号密码自动保存登录态
4. `python app.py` — 启动 Web 服务
5. 浏览器打开 [http://localhost:5000](http://localhost:5000)

> 完整上手教程见下方「详细步骤」。

## 详细步骤

### 1. 准备 Python 环境

需要 Python 3.10+。建议用 venv 或 conda 创建独立环境,避免依赖冲突。

```bash
# 创建并激活虚拟环境(Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 或 macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

`playwright install chromium` 会下载 Chromium 浏览器(约 150MB),首次登录要用它开浏览器窗口。

### 3. 填账号

```bash
cp .env.example .env      # macOS / Linux
copy .env.example .env    # Windows CMD
```

编辑 `.env`,把这两行的注释去掉并填入**你自己的** Moka 账号密码:

```
MOKA_USERNAME=你的 moka 邮箱或手机号
MOKA_PASSWORD=你的 moka 密码
```

**重要**:
- 不要用同事的账号 — Moka 同一时间只允许一处登录,你一登同事就掉线
- 不要把 `.env` 文件提交到 Git、传给别人、截图发群里 — 它含你的明文密码
- 不要把你的账号密码写进代码、README、issue 任何地方

### 4. 首次登录

```bash
python moka_client.py login
```

会自动打开一个 Chromium 浏览器窗口,跳转到 Moka 登录页。**在浏览器里正常输入你的账号密码完成登录**,登录成功后程序会自动保存登录态到 `moka_session.json`(类似 cookie),下次直接用,不用再输密码。

如果看不到浏览器窗口弹出,检查是否被杀毒软件拦截,或在 `moka_client.py` 里把 `headless=False` 改回 `headless=True` 之后再调试。

### 5. 启动 Web 服务

```bash
python app.py
```

启动后浏览器访问 [http://localhost:5000](http://localhost:5000),看到「招聘漏斗报告」页面就成功了。

页面提供:
- 漏斗总览表(所有职位 × 9 个阶段 + 总数)
- 单职位详情(点击行展开)
- 「下载 Excel」按钮 → 导出 `exports/funnel_<时间戳>.xlsx`

### 6. 命令行单独导出 Excel(可选)

不需要 Web 界面,只要 Excel:

```bash
python exporter.py
```

输出在 `exports/funnel_test.xlsx`。**注意:导出前请关闭 Excel 文件**,否则会报权限错误。

## 常见问题

**Q: 打开页面报「未登录」或「session 过期」**
A: Moka cookie 失效了。重跑 `python moka_client.py login` 重新登录。

**Q: 抓到的职位数比 Moka 后台少**
A: 删掉 `jobs_cache.json`,重跑 `python moka_client.py jobs` 强制刷新职位列表(缓存 1 小时过期)。

**Q: 某个职位漏斗数据是 0**
A: 大概率该职位当前状态不是「开放中」(Moka 只对 open 状态的职位抓数据)。

**Q: 想换账号怎么办**
A: 删掉 `moka_session.json` 和 `.env`,重跑步骤 3-4。

## 安全清单(发布前自查)

- [ ] `.env` 文件**没**在仓库里(`git status` 不应该看到)
- [ ] `moka_session.json` **没**在仓库里(含你的 cookie,泄露 = 别人能用你的号)
- [ ] `jobs_cache.json` **没**在仓库里(可能含职位列表)
- [ ] `exports/*.xlsx` **没**在仓库里(可能含候选人姓名)
- [ ] 没把账号密码写进任何代码、注释、issue

## 文件结构

```
moka-funnel-exporter/
├─ app.py              # Flask 主入口(同事用的 Web UI)
├─ moka_client.py      # Moka 接口客户端 + 登录
├─ funnel.py           # 候选人 stageName 漏斗统计
├─ exporter.py         # openpyxl 写 Excel
├─ templates/          # HTML 模板
├─ .env.example        # 账号密码占位符(填好复制成 .env)
├─ .gitignore          # 排除 .env / session / cache / xlsx
├─ requirements.txt    # Python 依赖
├─ moka_session.json   # 你的登录态(自动生成,**不入库**)
├─ jobs_cache.json     # 职位列表缓存(自动生成,1 小时有效,**不入库**)
└─ exports/            # 导出的 Excel(可选,本地用就行,**不入库**)
```

## 技术栈

- **Flask 3.x** — Web 框架
- **Playwright** — 首次登录开浏览器,后续纯 API 抓数据
- **requests** — 调 Moka 后端接口
- **openpyxl** — 写 Excel
- **python-dotenv** — 读 `.env`

## 数据流(给好奇的同事)

```
1. moka_client.py login → Playwright 打开浏览器让你输密码 → cookie 存 moka_session.json
2. moka_client.py jobs → POST paging 接口(pageSize=200)一次拿全 94 个职位 → jobs_cache.json
3. funnel.py → 对每个 jobId 调 search-candidate/v2 接口拿候选人 application
4. 数每个 application.stageName 出现次数 → 9 阶段漏斗
5. 渲染 HTML 表格(app.py)/ 写 Excel(exporter.py)
```

## 反馈

有问题或建议,找 @陈洪新(原仓库维护者)。