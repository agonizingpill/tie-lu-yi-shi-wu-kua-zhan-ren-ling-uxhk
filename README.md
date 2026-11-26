# 北砾铁路拾遗交接

三座客运站共用公开线索匹配和封袋台账。受理站核验旅客提供的私密特征，区段调度安排转运，目的站扫描原封签后才能交付。

## 适用场景

北砾客运失物联络组模拟运营北砾、河桥关、远沙河三个车站。柜员原先在每班的拾获 Excel 里登记，调度靠电话询问邻站，最后用纸面签收。相似物件被误认、封袋跨站后责任边界模糊、重复来电时无法追索已交记录，是三个主要痛点。

列车员的拾获通知进入封袋台账。旅客向取件站提交可见描述，由柜员查找候选和核对隐藏标记。调度单和目的站签收回执供交班、监管和取件查账使用。

| 角色 | 账号 | 页面与权限 |
|---|---|---|
| 北砾柜员 | `beili@rail.test` | 入柜、本站受理、目的站扫描、交付 |
| 河桥关柜员 | `heqiao@rail.test` | 与北砾柜员权限相同，本站范围为河桥关 |
| 区段调度 | `dispatch@rail.test` | 查阅台账，为已核验跨站封袋安排车次 |
| 票务稽核 | `audit@rail.test` | 查阅封袋、线索和历史记录 |

口令均为 `RailDemo26`。演示数据的过去拾获日期是 2026-11-23。

## 运行

```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

- 前端 `http://localhost:18300`
- 后端与 Swagger `http://localhost:19300/docs`
- PostgreSQL `localhost:17800`，数据库和用户均为 `rail`

| 服务 | 职责 |
|---|---|
| frontend | nginx + 原生 HTML/CSS/ES modules，反向代理 API |
| backend | Python 3.11/FastAPI + Pydantic + psycopg |
| worker | Redis 队列、scikit-learn FeatureHasher、PostgreSQL 结果回写 |
| db | PostgreSQL 16，封袋、线索、候选、认领和转运事务 |
| redis | Redis 7，任务队列、健康心跳、登录配额 |

`data`、`queue`、`exchanges` 为 Compose 命名卷。开发时可以在 `backend/` 里以项目依赖启动 FastAPI 和 worker，设置 `DATABASE_URL` 与 `REDIS_URL` 连接已有服务。浏览器开发仍通过前端 nginx 同源代理。

| 环境变量 | 用途 |
|---|---|
| `COMPOSE_PROJECT_NAME` | Compose 项目与容器名前缀 |
| `FRONTEND_PORT`、`BACKEND_PORT`、`DB_PORT` | 本地端口 |
| `POSTGRES_PASSWORD` | PostgreSQL 的本地密码 |
| `TOKEN_SECRET`、`PROOF_SECRET` | JWT 和 HMAC 私密特征摘要各自使用的密钥 |
| `SEED_DEMO` | 启动时插入演示账号和封袋 |

本地运行结束后可执行 `docker compose down`。增加 `-v` 会删除本地业务数据卷。

## 柜台剧本

1. 08:05，北砾根据 `G216` 交班小票登记封签 `BL-261123-014`，公开描述为「双肩包 黄色拉链 织布 背带」。
2. 08:45，旅客在河桥关填写深蓝包袋和 11 月 23 日乘车日期。
3. 08:46，worker 匹配同日期窗口，给出原封袋和外观相近的 `BL-261123-017`。
4. 08:47，输入「紫色五角贴纸」会留下拒绝记录，封袋继续在柜可查。
5. 08:49，输入「内袋缝线是一枚白山刺绣」通过，封袋锁定给这张认领单。
6. 09:00，调度绑定 `D919` 承运车次。河桥关在途无法交付。
7. 10:00，河桥关实扫 `BL-261123-014` 确认入柜。北砾不能代扫。
8. 10:15，河桥关当面扫描封签并交付。稽核看到完整顺序，第二次交付被拒绝。

## 算法与代码

`backend/railway/services/encoding.py` 根据类别、主色、车次和规范化公开描述构造特征。类别权重为 3，主色为 2，车次和描述词/相邻双字符为 1。FeatureHasher 使用 64 维带符号映射，然后计算稀疏余弦，相似度至少 0.2 的前 12 件按分值和封签号排序。同一版本与同一批封袋的结果可复现。每项保留碰撞桶计数与未哈希特征交集。类别一致且有直接公开词证据才能进入私密核验。输入窗口为乘车日前一天至后两天，由日期和当前在柜状态限制。计算异常标记线索单失败。

- `backend/migrations/001_custody.sql` 建立领域表、外键及唯一性约束。
- `backend/railway/{models,services,routes}` 实现依赖交易和接口。
- `backend/scripts/seed_demo.py` 按站点、账号、封签幂等导入。
- `frontend/src/pages` 提供封袋台账、公开线索、跨站转运、认领交付。
- 枚举定义在 `backend/railway/enums.py` 和 `frontend/src/enums.js`。SQL 约束重复类别、角色、封袋、线索、认领、转运状态。后端请求 schema 使用类别，服务检查办理状态和权限。前端类别选择器用在台账和线索，布局展示角色，状态组件用于四页。

源码以 MIT 许可提供，见 `LICENSE`。
