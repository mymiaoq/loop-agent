# api-standard

适用 Profile：enterprise-vue-java；仅在对应任务领域选择时加载。

### 3.2 前后端接口规范（api-standard.md）

> SSOT：API 任务必须遵守。即使被自动加载，非 API 任务也必须按
> `AGENTS.md` 忽略本文件。

#### 基础路径

-   前端开发代理：`/api` → `http://localhost:8081/main`。
-   yi-main-web：端口 `8081`，context-path `/main`。
-   yi-auth-server：端口 `8098`，context-path `/authserver`。
-   前端业务 API 路径不包含 `/main`，由代理负责重写。
-   生产地址从环境配置读取，禁止在业务代码中硬编码。

#### 响应与分页（强制）

``` json
{"code": 200, "message": "success", "data": {}}
{"code": 500, "message": "错误信息"}
{"code": 0, "count": 100, "data": []}
```

  场景       code   必需字段
  ---------- ------ ---------------
  普通成功   200    message、data
  失败       500    message
  分页成功   0      count、data

-   分页参数固定为 `page` 和 `limit`，页码从 1 开始，默认
    `page=1`、`limit=20`。
-   日期使用时间戳或 `yyyy-MM-dd HH:mm:ss`，同一接口前后端保持一致。
-   状态值和空值语义必须在 Spec 中明确，前后端保持一致。

#### 前端 API 封装

-   API 统一放在 `frontend/src/api/`，按业务模块划分。
-   必须使用 `src/service/request.js` 封装的 service
    实例，禁止直接使用原生 axios。
-   查询参数使用 `params`，请求体使用 `data`。
-   参数默认值使用 `params = {}`、`data = {}`，避免传递 undefined。
-   公共字典、上传和导出优先复用现有公共 API。
-   函数添加 JSDoc，说明参数和返回值。

**命名前缀：**

  操作        前缀
  ----------- ----------------------------------
  列表/详情   get、fetch、list
  新增        create、add
  修改        update、modify
  删除        delete、remove
  字典/选项   dict、options
  文件        export、import、upload、download

**请求类型：**

  类型   配置
  ------ -------------------------------------------------
  JSON   `dataType: 'json'`
  上传   `dataType: 'upload'` + FormData，可提供进度回调
  下载   `responseType: 'blob'`

#### 后端接口实现

-   Controller 命名为 `XxxEndpoint`，使用
    `@RestController`、`@RequestMapping` 并继承 `BaseController`。
-   使用 `@Resource` 或现有项目统一方式注入 Service。
-   Controller 只接收和校验参数、调用 Service、返回结果，禁止直接操作
    Mapper。
-   普通/GET 参数使用 `@RequestParam` 或项目现有 Map 形式；JSON
    请求体使用 `@RequestBody`。
-   参数校验失败返回 `code=500` 和明确、友好的 message。
-   返回使用项目现有 FastJSON `JSONObject` 格式。
-   Service 处理业务逻辑和事务；需要原子性的写操作使用
    `@Transactional(rollbackFor = Exception.class)`。
-   异常必须记录日志，禁止向客户端暴露敏感堆栈或内部配置。

**路径沿用项目约定：**

  操作        路径
  ----------- -----------------------------
  列表        `/xxx/list`
  详情        `/xxx/detail`
  新增        `/xxx/add`
  修改        `/xxx/update`
  删除        `/xxx/delete`
  字典/选项   `/xxx/dict`、`/xxx/options`

-   前端 API 路径必须与后端 `@RequestMapping` 完全一致。
-   本项目存在历史 POST 风格，不强制改造成
    RESTful；优先保持相邻接口风格一致。

#### 前端调用

-   使用 `try/catch/finally` 管理异常和 loading。
-   全局网络错误由 request 拦截器处理；业务错误在调用处给出友好提示。
-   禁止空 catch。
-   表单提交和数据变更成功后提示；常规列表查询不提示成功。
-   调用前校验关键参数并格式化日期、数字等字段。
-   高频搜索使用约 `300ms` 防抖，组件卸载时取消。
-   无依赖请求使用 `Promise.all`；字典等低频变化数据可缓存。

#### 文件接口

-   上传使用 FormData，校验类型、大小和业务必填项。
-   下载/导出使用 blob，正确处理文件名和失败响应。
-   文件名可加入时间戳，避免浏览器缓存或覆盖。

#### 环境与拦截器

-   开发环境基础地址使用 `/api`，代理重写为 `/main`。
-   环境变量以 `VITE_` 开头，生产地址由部署配置提供。
-   `vite.config.js`、`.env.*` 和 `src/service/request.js`
    属于禁区，除非用户明确要求。
-   GET 防缓存、登录超时和公共请求头沿用现有 request 拦截器，不在业务
    API 重复实现。

#### 联调门禁

API
验证必须覆盖：路径和请求方法一致；参数名、位置、类型和必填性一致；分页参数为
`page/limit`；普通、分页和失败响应格式一致；日期、状态值和空值语义一致；文件接口的
content type、文件名和错误响应正确。

未覆盖的契约不得进入 `verified`。
