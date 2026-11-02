# 企业代码规范

适用 Profile：enterprise-vue-java。基础原则引用 ../code-standard.md。

#### 命名规范

**前端：**

  类型          规范                     示例
  ------------- ------------------------ ------------------------
  组件          PascalCase               `UserList.vue`
  页面          模块目录下 `index.vue`   `views/user/index.vue`
  JS/工具文件   camelCase                `formatDate.js`
  Composable    `use` + camelCase        `useTable.js`
  变量          camelCase                `tableData`
  布尔值        is/has/can 前缀          `isLoading`
  常量          全大写下划线             `MAX_PAGE_SIZE`
  函数          动词+名词                `fetchUserList`
  事件          handle 前缀              `handleSubmit`

**后端：**

  类型              规范
  ----------------- ------------------------------
  Controller        `XxxEndpoint`
  Service 接口      `IXxxService`
  Service 实现      `XxxServiceImpl`
  Mapper 接口/XML   `XxxMapper`、`XxxMapper.xml`
  Model             `Xxx`
  工具类            `XxxUtil` / `XxxUtils`

方法使用
`get/list/select`、`add/save/insert`、`update/modify`、`delete/remove`、`check/validate`
等明确动词。

#### 前端代码要点

-   使用 ES6+，优先 `const/let`、箭头函数、解构、可选链和空值合并，禁止
    `var`。
-   Vue 组件使用 `<script setup>`，结构顺序为 script → template → scoped
    SCSS。
-   Props 定义类型和默认值，Emits 显式声明。
-   `v-for` 使用稳定唯一 key；不得与 `v-if` 放在同一元素。
-   样式使用 `scoped`，深度选择器使用 `:deep()`。
-   页面私有状态使用 ref/reactive 或 composable；只有跨页面共享状态进入
    Pinia。
-   Store 命名为 `useXxxStore`，避免在 Store 中操作 DOM 或执行页面跳转。
-   路由名使用 kebab-case，路由组件懒加载。
-   环境变量以 `VITE_` 开头，敏感信息禁止硬编码。
-   定时器、事件监听和其他副作用在组件卸载时清理。
-   长列表考虑虚拟滚动，大组件和路由按需加载。

#### 后端分层（强制）

    Endpoint → Service → Mapper → Model

-   Endpoint 只接收/校验参数、调用 Service
    和返回结果，**绝对禁止直接操作 Mapper**。
-   Service 处理业务逻辑和事务，接口继承 `IService<T>`，实现继承
    `ServiceImpl<Mapper,T>`。
-   需要事务的方法使用 `@Transactional(rollbackFor = Exception.class)`。
-   Mapper 继承 `BaseMapper<T>`；自定义参数使用 `@Param`。
-   Mapper XML 的 namespace 必须是 Mapper 接口全限定名。
-   XML 定义 `BaseResultMap` 和 `Base_Column_List`；分页交给现有 MyBatis
    Plus 分页插件。
-   Model 使用 `@TableName`、`@TableId`、必要的 `@TableField`，包含
    `serialVersionUID` 和 getter/setter。
-   使用 Java 8 语法、4 空格缩进和 K&R 大括号风格。

#### 异常、日志和敏感信息

-   前端异步操作使用 `try/catch/finally`，失败给出友好提示，finally 恢复
    loading。
-   后端异常至少记录日志并返回友好信息，禁止向客户端暴露堆栈、SQL、密码或内部配置。
-   后端使用 Log4j2，禁止 `System.out.println`。
-   前端禁止遗留调试 `console.log` 和
    `debugger`；必要错误日志不得包含敏感数据。
-   密码、密钥、Token 和数据库连接信息不得硬编码或写入日志。

#### 性能

-   高频事件使用防抖/节流；无依赖异步任务可并行。
-   避免重复请求和无效计算，合理使用缓存。
-   大表查询必须分页，避免 N+1 和无条件全表扫描。
-   批量操作优先批量 SQL，合理利用索引。
-   Redis/Ehcache 只缓存适合的数据，并保持失效策略明确。

#### 文件与禁区

-   禁止在项目中生成无关临时脚本、截图、临时 node_modules、缓存或 `_tmp`
    目录。
-   临时验证产物放在工作区外，使用后清理。
-   可追溯 Spec 产物放在 `.docloop/changes/<change-id>/`。
-   不生成任务未要求的 README、示例、辅助脚本或备份文件。

**前端禁区：**
`src/main.js`、`src/App.vue`、`src/service/request.js`、`vite.config.js`、`.env.*`、`package.json`、`package-lock.json`

**后端禁区：** 根目录和模块
`pom.xml`（明确需要新增依赖时除外）、`application.yml`、`log4j2.xml`、`ehcache.xml`、`BaseController.java`
等公共框架类

#### 验证与提交

-   验证项由 `task_context.verification` 和 `verification-standard.md`
    决定，禁止执行非相关领域检查。
-   实现者快速检查不能替代 verify-agent 的独立证据。
-   提交前移除调试代码、格式化变更并确认对应构建/编译结果。
-   提交信息简洁说明前端、后端或全栈范围。
-   禁止提交任务外文件。
