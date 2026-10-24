"""按课程模板生成四份实验报告（只填写“五、实验结果分析”和“六、实验总结与思考”）。

python3 docs/reports/build_reports.py [输出目录]，默认 docs/reports/。需要 LibreOffice（把 .doc 模板转为 .docx）。
数字全部从 evidence/ 读取，源码片段从仓库代码截取；封面的姓名、学号、实验时间、成绩与签字留给本人填写。
截图由 docs/reports/shoot.mjs 在 Osaka 用 headless Chromium 生成，不含浏览器地址栏（带地址栏截图见 #8）。
"""

import ast
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_fill import fill  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "docs" / "template"
SHOTS = ROOT / "docs" / "reports" / "screenshots"
EVIDENCE = ROOT / "evidence"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def load(path):
    return json.loads(read(path))


def source(path, name, keep=None):
    """截取函数或类的源码；keep 为保留的最大行数，超出部分以省略号表示。"""
    text = read(path)
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.ClassDef) and node.name == name:
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            lines = text.splitlines()[start - 1 : node.end_lineno]
            if keep and len(lines) > keep:
                lines = lines[:keep] + ["    ..."]
            return [f"# {path}"] + lines
    raise KeyError(f"{path} 中没有 {name}")


def snippet(path, first, last):
    lines = read(path).splitlines()
    i = next(k for k, line in enumerate(lines) if first in line)
    j = next(k for k in range(i, len(lines)) if last in lines[k])
    return [f"# {path}"] + lines[i : j + 1]


def shot(name):
    return SHOTS / f"{name}.png"


def pct(value):
    return f"{value * 100:.1f}%"


# ---------------- 实验一 ----------------


def report1():
    http = [line for line in read("evidence/exp01/http.txt").splitlines() if line.startswith("GET")]
    rows = [re.match(r"GET (\S+) status=(\d+) content_type=(.*)", line).groups() for line in http]
    startup = read("evidence/exp01/startup.txt").splitlines()[:8]
    s5 = [
        ("h", "1. 实现方式与运行环境"),
        (
            "p",
            "本实验在课程项目“词汇诊断与个性化复习系统”中完成，四次实验共用同一个 Flask 应用。开发与运行环境为 Osaka 服务器"
            "（Linux ARM64，Neoverse-N1 2 核），使用 Docker Compose 运行 web 服务（Python 3.12.15、Flask 3.1.3）和"
            " MySQL 8.4；在 Mac 上用 Chrome 浏览器经 SSH 隧道访问 http://127.0.0.1:5000。",
        ),
        (
            "p",
            "与模板示例的单文件 app.py 不同，本项目采用 Flask 的应用工厂 create_app() 与 Blueprint 组织路由："
            "首页由应用直接注册，实验页面放在 lab 蓝图（URL 前缀 /lab）中，页面使用 Jinja 模板继承同一个 base.html，"
            "静态图片与样式放在 app/static/ 下。这样后续实验可以在同一个应用中增加账户、练习和模型页面，测试时也能为每个用例创建独立配置的应用。",
        ),
        ("h", "2. 关键源代码"),
        ("code", source("app/blueprints/lab.py", "hello")),
        ("code", ["# app/blueprints/lab.py（蓝图定义）", 'bp = Blueprint("lab", __name__, url_prefix="/lab")']),
        ("code", snippet("app/templates/lab/hello.html", "{% block content %}", "{% endblock %}")),
        (
            "p",
            "应用工厂按顺序读取配置、校验 SECRET_KEY、初始化 CSRF 保护与数据库连接管理，再注册各蓝图；"
            "页面通过 url_for('static', filename=...) 生成静态资源地址，避免在模板里写死路径。",
        ),
        (
            "code",
            [
                "# app/__init__.py（create_app 节选：配置读取省略）",
                "def create_app(test_config=None):",
                "    app = Flask(__name__)",
                "    ...",
            ]
            + snippet("app/__init__.py", 'if not app.config.get("SECRET_KEY")', "return app")[1:],
        ),
        ("h", "3. 运行结果"),
        ("p", "启动开发服务器后用 curl 依次请求首页、实验页和静态图片，结果如下（evidence/exp01/http.txt）："),
        ("table", ["请求路径", "HTTP 状态", "内容类型"], rows),
        ("code", ["# evidence/exp01/startup.txt（启动日志节选）"] + startup),
        ("img", EVIDENCE / "exp01" / "home.png", "图 1  首页（Mac Chrome 经 SSH 隧道访问，网页视口截图）"),
        ("img", EVIDENCE / "exp01" / "hello.png", "图 2  /lab/hello 页面：Hello Flask 文字与静态图片"),
        ("h", "4. 探讨分析"),
        (
            "p",
            '（1）路由与视图：@bp.get("/hello") 把 GET /lab/hello 映射到视图函数 hello()，视图用 render_template 渲染模板后返回；'
            "日志中 /lab/hello 与 /static/images/learning-loop.svg 均返回 200，说明路由、模板和静态文件三条链路都正常。"
            "日志里 /favicon.ico 返回 404，是浏览器自动请求网站图标而项目未提供该文件，不影响功能。",
        ),
        (
            "p",
            "（2）自动化检查：tests/test_app.py 用 Flask 测试客户端验证首页、实验页、静态图片的状态码与内容，"
            "并验证在没有数据库和模型时基础页面仍可访问、未实现的路由返回 404 而不是伪造成功。"
            "这些检查在每次合并前与全部测试一起运行。",
        ),
        (
            "p",
            "（3）配置与安全：调试模式关闭；Cookie 设置 HttpOnly、SameSite=Lax，生产环境启用 Secure；SECRET_KEY 只从环境变量读取，"
            "未设置时应用拒绝启动。开发服务器只用于本地或隧道演示，日志中的警告也提示它不适合生产部署。",
        ),
    ]
    s6 = [
        (
            "p",
            "本实验完成了 Python 运行环境与 Flask 框架的搭建，实现了路由到视图函数的映射、Jinja 模板渲染和静态图片展示，"
            "并通过浏览器与自动化测试验证了页面的请求与响应。",
        ),
        (
            "p",
            "思考：应用工厂与蓝图比单文件写法多了一层结构，但让配置、测试和后续功能扩展都更清晰；"
            "用 Docker 固定 Python 与依赖版本，减少了“在我电脑上能运行”的环境差异。实验也说明静态资源路径应由 url_for 生成，"
            "部署路径变化时不需要修改模板。",
        ),
    ]
    return s5, s6


# ---------------- 实验二 ----------------


def report2():
    schema = read("evidence/exp02/schema.txt")
    ddl = schema[schema.index("CREATE TABLE `users`") :].strip().splitlines()
    auth = read("evidence/exp02/auth-http.txt").splitlines()
    steps = []
    for i, line in enumerate(auth):
        if line.startswith("## "):
            code = next((x for x in auth[i + 1 :] if x.startswith("HTTP ")), "").split()[1]
            detail = auth[i + 2] if i + 2 < len(auth) and not auth[i + 2].startswith(("## ", "HTTP")) else ""
            if '"username": "demo_e2"' in detail:
                detail = "返回 demo_e2 的账户信息"
            elif match := re.search(r"'code': '(\w+)'", detail):
                detail = f"错误码 {match.group(1)}"
            elif code == "302":
                detail = "重定向：" + auth[i + 1].split("Location=")[-1].replace("http://127.0.0.1:5000", "")
            steps.append((line[3:].split("（")[0], code, detail))
    hash_row = [r for r in read("evidence/exp02/password-hash.txt").splitlines() if "demo_e2" in r][0]
    hash_cells = [c.strip() for c in hash_row.strip("|").split("|")]
    review = read("evidence/exp02/review-path.txt")
    today = read("evidence/exp02/today-http.txt")
    s5 = [
        ("h", "1. 数据库设计"),
        (
            "p",
            "项目数据库 vocab_review 运行在 MySQL 8.4（InnoDB、utf8mb4），表结构由按序编号的迁移脚本创建（flask db upgrade），"
            "共 14 张业务表，覆盖账户、词表与词义、题目版本、练习与作答、学习状态和模型推理记录。本实验涉及的用户表如下"
            "（SHOW CREATE TABLE 实际输出）：",
        ),
        ("code", ["# evidence/exp02/schema.txt"] + ddl),
        (
            "p",
            "与模板示例相比：用户名另存规范化小写形式 username_norm 并建唯一索引（大小写不同的用户名视为同一个）；"
            "password_hash 只保存 Werkzeug 生成的带盐 scrypt 哈希，数据库中不出现明文密码；role 通过 CHECK 约束限定为 learner 或 admin。",
        ),
        ("h", "2. 关键源代码"),
        ("p", "数据访问层只写参数化 SQL，提交与回滚由业务层用显式事务控制："),
        ("code", source("app/repositories/users.py", "find_by_username_norm")),
        ("code", source("app/services/accounts.py", "authenticate")),
        (
            "p",
            "登录视图：先在事务中校验，成功后清空旧会话再写入身份；失败时无论是密码错误还是用户不存在，都返回同一提示。",
        ),
        ("code", source("app/blueprints/auth.py", "login")),
        ("code", snippet("app/templates/auth/login.html", '<form class="auth-form"', "</form>")),
        ("h", "3. 运行结果"),
        ("p", "对运行中的服务按顺序发起请求（evidence/exp02/auth-http.sh，演示账户 demo_e2，密码随机生成且未记录）："),
        ("table", ["步骤", "HTTP", "结果"], steps, [5, 1, 4]),
        (
            "p",
            f"数据库中该用户的密码字段：哈希算法前缀 {hash_cells[4]}，长度 {hash_cells[5]} 个字符，"
            "确认为 Werkzeug scrypt 哈希（为避免泄露，只导出前缀与长度）。",
        ),
        ("img", shot("e2_login_failed"), "图 1  错误密码登录：返回 401，提示“用户名或密码错误”"),
        ("img", shot("e2_dashboard"), "图 2  正确登录后进入概览页"),
        (
            "p",
            "功能扩展：在登录的基础上，系统实现了注册、退出和完整的背单词学习闭环——选择目标词表、三类题型练习"
            "（服务端判分，作答与学习状态在同一事务中提交）、复习计划与统计，以及汇总当天待复习、每日 10 个新词义与连续学习天数的今日任务。"
            "下表摘自答辩路径与今日任务实测（evidence/exp02/review-path.txt、today-http.txt）：",
        ),
        (
            "table",
            ["环节", "实测结果"],
            [
                ("含错误的 5 题练习", "2 题答错（meaning），3 题答对，练习完成"),
                (
                    "复习计划",
                    re.search(r"已到期 (\d+) ；未到期错题 (\d+)", review).group(0) + "（错题约 10 分钟后到期）",
                ),
                ("六级目标统计", re.search(r"词条 已练习/总数 .*", review).group(0)[:60]),
                (
                    "增加雅思目标",
                    "合计词条 "
                    + re.search(r"合计词条（共有词只计一次） (\d+)", review).group(1)
                    + "（两个词表共 10 个共有词只计一次）",
                ),
                ("学习状态重建核对", re.search(r"学习状态与作答记录一致.*", review).group(0)),
                (
                    "今日任务（新账户）",
                    "新词义 0/10；完成 10 个新词义（2 题答错）后显示已完成，连续学习 "
                    + re.search(r"连续学习 (\d+) 天", today).group(1)
                    + " 天；再学新词时与已作答词义重叠 "
                    + re.search(r"与已作答词义重叠：(\d+) 题", today).group(1)
                    + " 题",
                ),
            ],
        ),
        ("img", shot("e2_practice_feedback"), "图 3  练习页：提交后显示服务端判分结果"),
        ("img", shot("e2_review"), "图 4  复习计划：已到期与未到期错题"),
        ("img", shot("e2_today"), "图 5  今日任务：连续学习天数、今日新词义进度与各题型待复习"),
        ("h", "4. 探讨分析"),
        (
            "p",
            "（1）密码存储：模板示例用 SHA2(password, 256) 存储，相同密码得到相同哈希且计算很快，泄库后容易被彩虹表或暴力破解。"
            "本实验改用 Werkzeug 的 generate_password_hash/check_password_hash（scrypt，自动加盐、计算成本可调）。",
        ),
        (
            "p",
            "（2）SQL 注入：所有查询都用 %s 占位符由 PyMySQL 转义参数，不拼接用户输入；测试中用 a' OR '1'='1 这类用户名注册，"
            "会被字段校验拒绝（422），且数据库中不会出现对应记录。",
        ),
        (
            "p",
            "（3）登录安全细节：错误密码与不存在的用户返回相同提示，并且不存在的用户也计算一次哈希，避免通过提示或响应时间判断用户名是否存在；"
            "登录前清空旧会话，防止会话固定；所有表单与接口启用 CSRF 校验（缺少令牌返回 403）；退出必须用 POST，GET /auth/logout 返回 405。",
        ),
        (
            "p",
            "（4）正确性验证：账户相关的 22 项自动化测试连接独立的测试库运行，覆盖注册、重复用户名（409）、字段校验（422）、"
            "正确/错误密码、停用账户、未登录访问（401）与权限不足（403）。学习闭环另有并发重复提交只计一次、写入中途出错整笔回滚等测试。",
        ),
    ]
    s6 = [
        (
            "p",
            "本实验完成了 Flask 与 MySQL 的集成：设计并通过迁移创建数据表，用 PyMySQL 参数化 SQL 读写数据，实现了注册、登录、退出与会话管理，"
            "并在此基础上完成了练习、复习与统计等背单词核心功能。",
        ),
        (
            "p",
            "思考：登录功能“能用”与“安全”之间有不少细节——密码哈希算法、提示信息是否泄露用户存在、会话固定和 CSRF 都需要专门处理。"
            "另外，数据库写操作应当放在显式事务中，并用约束（唯一索引、CHECK）兜底并发与异常情况，而不能只依赖 Python 中“先查后插”的判断。",
        ),
    ]
    return s5, s6


# ---------------- 实验三 ----------------


def report3():
    data = load("evidence/exp03/data_manifest.json")
    metrics = load("evidence/exp03/metrics.json")
    latency = load("evidence/exp03/latency.json")
    names = {
        "model": "随机森林",
        "baseline_train_label_mean": "训练集标签均值",
        "baseline_smoothed_accuracy": "平滑历史正确率",
    }
    rows = data["rows"]
    split_rows = [
        (name, f["rows"], f["users"], f"{f['time_range_utc'][0][:10]} — {f['time_range_utc'][1][:10]}", f["label_mean"])
        for name, f in data["split"]["files"].items()
    ]
    metric_rows = [
        (split, names[m], v["mae"], v["rmse"])
        for split in ("validation", "test")
        for m, v in metrics[split]["overall"].items()
    ]
    test = metrics["test"]["overall"]
    gain = 1 - test["model"]["mae"] / test["baseline_train_label_mean"]["mae"]
    subgroup_rows = [
        (label, g["rows"], names[m], g[m]["mae"]) for label, g in metrics["test"]["subgroups"].items() for m in names
    ]
    worst = metrics["test"]["largest_errors"][:3]
    events = [line for line in read("evidence/exp03/inference-events.txt").splitlines() if "manual_lab" in line][:3]
    consistency = [
        line for line in read("evidence/exp03/consistency.txt").splitlines() if "一致" in line and "(" in line
    ]
    warm = latency["warm"]
    s5 = [
        ("h", "1. 任务与数据"),
        (
            "p",
            "任务：根据学习者对某个词的历史记录（距上次练习的间隔、历史出现次数、历史正确次数），回归预测这一次练习中正确回忆的比例，"
            "输出字段为 expected_recall。它是对公开数据源任务的估计，不代表掌握度或考试分数，也不改写系统的作答记录与复习安排。",
        ),
        (
            "p",
            f"数据：Duolingo halflife-regression 学习记录（Harvard Dataverse，CC BY-NC 4.0），原始文件 MD5 与官方记录一致。"
            f"处理流程：原始 {rows['raw']:,} 行 → 学英语的记录 {rows['english']:,} 行 → 8 条规则检查后 {rows['after_checks']:,} 行"
            f"（仅去除 {data['checks_failed']['exact_duplicate']} 行完全重复记录）→ 按用户抽样 5%（种子 42，"
            f"{data['sampling']['users_sampled']:,}/{data['sampling']['users_total']:,} 名用户，保留完整时间序列）共 {rows['sampled']:,} 行。"
            "按全局时间约 70/15/15 切分，同一时间戳不跨集合：",
        ),
        ("table", ["集合", "行数", "用户数", "时间范围（UTC）", "标签均值"], split_rows),
        ("h", "2. 特征、模型与 Web 集成"),
        (
            "table",
            ["特征", "变换"],
            [
                ("log_delta_days", "log1p(delta_seconds / 86400)"),
                ("log_seen", "log1p(history_seen)"),
                ("log_correct", "log1p(history_correct)"),
                ("smoothed_accuracy", "(history_correct + 1) / (history_seen + 2)"),
            ],
        ),
        (
            "p",
            "训练与 Web 推理调用同一个特征函数，避免两边各写一份造成不一致。模型为 RandomForestRegressor"
            "（n_estimators=200、max_depth=12、min_samples_leaf=10、random_state=42，未做超参搜索），"
            f"训练 {metrics['train_rows']:,} 行用时 {metrics['fit_seconds']} 秒，导出为 joblib 文件并在清单中记录 SHA-256、特征版本与库版本。",
        ),
        ("code", source("ml/features.py", "build_recall_features")),
        (
            "p",
            "Web 端只加载已登记且校验通过的制品：核对清单、特征版本、scikit-learn 版本、文件哈希以及数据库 model_versions 中的登记记录，"
            "每个进程加载一次；接口 POST /api/v1/ml/recall 校验输入（非法 422、无历史返回冷启动 null），推理后把输入、输出、"
            "模型版本和耗时写入 MySQL 的 inference_events。",
        ),
        ("code", source("app/blueprints/ml_lab.py", "recall", keep=40)),
        ("h", "3. 实验结果"),
        ("p", "逐记录误差（越小越好），与两个简单基线对照："),
        ("table", ["集合", "方法", "MAE", "RMSE"], metric_rows),
        (
            "p",
            f"test 集上随机森林的 MAE 比“训练集标签均值”基线低 {pct(gain)}，RMSE 由 {test['baseline_train_label_mean']['rmse']} "
            f"降到 {test['model']['rmse']}；“平滑历史正确率”基线明显更差。特征重要性："
            + "，".join(f"{k} {v}" for k, v in metrics["feature_importances"].items())
            + "。",
        ),
        ("table", ["test 子群", "行数", "方法", "MAE"], subgroup_rows),
        (
            "p",
            "Web 与离线一致性：同一制品对固定参考输入的预测，在 Web 接口上与训练脚本导出时的结果逐位相同（evidence/exp03/consistency.txt）：",
        ),
        ("code", consistency),
        (
            "table",
            ["耗时（Osaka，CPU）", "HTTP 往返", "处理", "模型计算"],
            [
                (
                    "首次请求（含校验与加载）",
                    latency["first_request"]["http_ms"],
                    latency["first_request"]["processing_time_ms"],
                    latency["first_request"]["model_time_ms"],
                ),
                (
                    f"预热后 p50（{warm['requests']} 次，失败 {warm['failures']}）",
                    warm["http_ms"]["p50"],
                    warm["processing_time_ms"]["p50"],
                    warm["model_time_ms"]["p50"],
                ),
                ("预热后 p95", warm["http_ms"]["p95"], warm["processing_time_ms"]["p95"], warm["model_time_ms"]["p95"]),
            ],
        ),
        ("note", "单位：毫秒。"),
        ("p", "MySQL 中的推理记录（evidence/exp03/inference-events.txt 节选）："),
        ("code", [re.sub(r"\s+\|", " |", line)[:118] for line in events]),
        ("img", shot("e3_ml"), "图 1  实验三页面：模型状态、离线误差表与在线估计结果"),
        ("h", "4. 探讨分析"),
        (
            "p",
            "（1）效果有限但真实：模型相对均值基线的改进幅度不大，原因之一是标签高度集中（训练集标签均值约 "
            f"{metrics['train_label_mean']:.3f}，大多数练习全部答对），而可用特征只有 4 个。"
            "在间隔超过 30 天的子群上，模型的 MAE 反而略高于均值基线，说明长间隔样本少、模型在这部分没有学到稳定规律。",
        ),
        (
            "p",
            f"（2）误差最大的样例集中在“历史表现很好但本次答错”的情况，例如 {worst[0]['lexeme_string']}："
            f"历史 {worst[0]['history_seen']} 次中对 {worst[0]['history_correct']} 次，本次只练 {worst[0]['session_seen']} 次且答错，"
            f"标签为 {worst[0]['p_recall']}，模型预测 {worst[0]['prediction']}。只练一次时标签只能是 0 或 1，偶然失误不可预测。",
        ),
        (
            "p",
            "（3）评价方法的边界：按时间切分只说明模型对“之后时间段”的表现，同一用户可能同时出现在训练集和测试集，不能据此推断对新用户的泛化；"
            "公开数据按 lexeme 计数，本系统按词义与题型计数，两者不能直接等同，所以模型只在独立实验页展示，没有用于改写复习安排。",
        ),
        (
            "p",
            "（4）工程问题：训练时多线程预测会让各棵树结果的累加顺序变化，导致末位浮点数不同，离线与 Web 输出无法逐位核对，"
            "导出前把预测改为单线程后解决。另外实验发现被篡改的压缩模型文件会让 joblib.load 长时间卡住，"
            "因此哈希校验必须放在加载之前。模型文件缺失或不匹配时接口返回 503，并记录一条失败事件，练习与复习功能不受影响。",
        ),
    ]
    s6 = [
        (
            "p",
            "本实验完成了从公开数据处理、特征构建、随机森林训练与评价，到 Flask 在线推理和 MySQL 留证的完整流程。"
            f"在真实数据上，模型在 test 集的 MAE 为 {test['model']['mae']}，优于两个简单基线，并实现了离线与 Web 输出的逐位一致。",
        ),
        (
            "p",
            "思考：模型上线不只是“能预测”，更重要的是可追溯（数据哈希、制品哈希、版本登记）、可验证（离线与在线一致、"
            "与基线对照）和可降级（模型不可用时核心功能照常）。另外，指标提升有限时应如实报告，并分析误差来源，"
            "而不是继续在测试集上调参。",
        ),
    ]
    return s5, s6


# ---------------- 实验四 ----------------


def report4():
    payload = load("evidence/exp04/retrieval-metrics.json")
    result = payload["result"]
    index = load("evidence/exp04/index_manifest.json")
    latency = load("evidence/exp04/latency.json")
    names = {"sentence_embedding": "句向量", "tfidf": "TF-IDF"}
    overall = [
        (split, names[m], r["with_relevant"], r["recall_at_3"], r["mrr_at_3"])
        for split in ("dev", "test")
        for m, r in result[split].items()
    ]
    by_type = [
        (t, names[m], g["queries"], g["recall_at_3"], g["mrr_at_3"])
        for m, r in result["test"].items()
        for t, g in r["by_type"].items()
    ]
    misses = [q for q in result["test"]["sentence_embedding"]["per_query"] if q.get("rr_at_3") == 0.0]
    lab = read("evidence/exp04/lab-http.txt").splitlines()
    start = next(i for i, line in enumerate(lab) if line.startswith("## M04"))
    end = next(i for i, line in enumerate(lab) if line.startswith("## T13"))
    stale = lab[start:end]
    warm = latency["warm"]
    annotated = payload["annotation_status"]
    s5 = [
        ("h", "1. 任务与模型"),
        (
            "p",
            "任务：英语语境例句检索。用户输入一句英语（或对某个意思的描述），系统找出语义最接近的已校对例句，并给出例句对应的词条与词义，"
            "用于帮助区分多义词的不同含义。",
        ),
        (
            "p",
            f"模型：预训练句向量编码器 {index['encoder']['repo']}（Apache-2.0），固定 revision {index['encoder']['revision'][:12]}，"
            f"只下载 safetensors 权重与分词器到本地并核对 SHA-256；Web 运行时离线加载，请求中不下载模型。"
            f"语料为数据库中启用的 {index['count']} 条演示例句（每个词义两条），编码为 {index['dimensions']} 维、L2 归一化的 float32 向量，"
            "因此查询向量与例句向量的点积即余弦相似度。",
        ),
        ("h", "2. 实现"),
        (
            "p",
            "离线构建：flask build-example-index 从 MySQL 读取启用例句，编码前用分词器核对长度（超过 256 个 word piece 直接报错，不静默截断），"
            "写出向量、例句 ID 映射与清单；清单记录编码器 revision、权重哈希、向量与 ID 文件哈希，以及由例句 ID、版本和正文哈希算出的语料指纹。",
        ),
        ("code", source("ml/example_index.py", "encode") + [""] + source("ml/example_index.py", "check_length")),
        (
            "p",
            "在线检索：每个进程只加载一次编码器；每次检索都用当前启用的例句重新计算语料指纹，与索引不一致（例句被修改或停用）时返回 503，"
            "要求重建索引，避免返回已经失效的例句。检索结果与版本信息一并写入 inference_events（kind=dl）。",
        ),
        ("code", source("app/services/example_search.py", "search", keep=34)),
        ("h", "3. 实验结果"),
        (
            "p",
            f"评价查询：dev 10 条、test 30 条英语查询，分为近义改写、多义词的特定词义和语料中没有相关例句三类，同语料上与 TF-IDF 对照。"
            f"标注状态：{annotated}。",
        ),
        ("table", ["集合", "方法", "有相关项查询", "Recall@3", "MRR@3"], overall),
        ("table", ["test 查询类型", "方法", "查询数", "Recall@3", "MRR@3"], by_type),
        (
            "p",
            "没有相关例句的 test 查询，句向量的最高相似度为 "
            + "、".join(str(s) for s in result["test"]["sentence_embedding"]["no_relevant"]["top1_scores"])
            + "，TF-IDF 为 "
            + "、".join(str(s) for s in result["test"]["tfidf"]["no_relevant"]["top1_scores"])
            + "。",
        ),
        (
            "table",
            ["耗时（Osaka，CPU）", "HTTP 往返", "处理", "模型计算"],
            [
                (
                    "首次请求（含加载 torch 与编码器）",
                    latency["first_request"]["http_ms"],
                    latency["first_request"]["processing_time_ms"],
                    latency["first_request"]["model_time_ms"],
                ),
                (
                    f"预热后 p50（{warm['requests']} 次，失败 {warm['failures']}）",
                    warm["http_ms"]["p50"],
                    warm["processing_time_ms"]["p50"],
                    warm["model_time_ms"]["p50"],
                ),
                ("预热后 p95", warm["http_ms"]["p95"], warm["processing_time_ms"]["p95"], warm["model_time_ms"]["p95"]),
            ],
        ),
        ("note", "单位：毫秒。"),
        (
            "p",
            "索引一致性实测：停用一条例句后，旧索引被拒绝；恢复启用后语料指纹重新一致，检索恢复（evidence/exp04/lab-http.txt）：",
        ),
        ("code", stale),
        ("img", shot("e4_examples"), "图 1  查询“We sat on the grass beside the river.”：第一名为 bank 的“河岸”词义"),
        (
            "img",
            shot("e4_examples_money"),
            "图 2  查询“I need to open a savings account at the bank.”：第一名为 bank 的“银行”词义",
        ),
        ("h", "4. 探讨分析"),
        (
            "p",
            "（1）语义检索的优势体现在多义词上：TF-IDF 只看词面重合，查询“河边的草地”和“开银行账户”都只能匹配到单词 bank；"
            "句向量能利用上下文区分两个词义（图 1、图 2），test 集多义词查询的 MRR@3 明显高于 TF-IDF。",
        ),
        (
            "p",
            "（2）错误分析："
            + "；".join(
                f"{q['query_id']}“{q['text']}”前三名为 " + "、".join(t["example_key"] for t in q["top3"])
                for q in misses
            )
            + "。查询描述的是“激励”这个概念，而“涨价后销量下降”“顾客不愿为环保产品多付钱”等例句与查询同属价格与购买话题，"
            "模型更多捕捉到了话题相似，而不是 incentive 这个词义本身。",
        ),
        (
            "p",
            "（3）没有相关例句时，句向量仍会返回相似度较低的结果，TF-IDF 有时因为偶然的同词得到较高分数；"
            "本实验未设相似度阈值，因为阈值只能在 dev 集上确定，而 dev 集只有 2 条无相关查询，样本太少。",
        ),
        (
            "p",
            "（4）评价的局限：语料与查询都是项目自编的小规模演示内容，查询与相关性标注目前由 AI 起草、尚待人工逐条确认，"
            "因此上述指标只反映这份演示语料，确认后需要重新运行评价。",
        ),
    ]
    s6 = [
        (
            "p",
            "本实验完成了预训练深度学习模型的本地部署与集成：固定模型版本并校验文件、离线构建向量索引、Flask 在线检索、MySQL 留证，"
            "并用独立查询集与 TF-IDF 对照评价。句向量检索在 test 集上的 MRR@3 为 "
            f"{result['test']['sentence_embedding']['mrr_at_3']}，TF-IDF 为 {result['test']['tfidf']['mrr_at_3']}。",
        ),
        (
            "p",
            "思考：深度学习模型的首次加载开销远大于单次推理（本实验首次请求约 7 秒，预热后约 20 毫秒），"
            "应在进程内只加载一次；模型、向量与语料三者的版本必须绑定，任何一方变化都要能被发现并拒绝旧结果。"
            "此外，评价数据必须独立于语料、并由人工确认，否则指标很容易高估真实效果。",
        ),
    ]
    return s5, s6


REPORTS = {
    "1_实验一：Web框架搭建（实验报告模板）.doc": ("实验一_Web框架搭建.docx", report1),
    "2_实验二：Web页面设计（实验报告模板）.doc": ("实验二_Web页面设计.docx", report2),
    "3_实验三：案例数据分析（机器学习）.doc": ("实验三_案例数据分析（机器学习）.docx", report3),
    "4_实验四：案例数据分析（深度学习）.doc": ("实验四_案例数据分析（深度学习）.docx", report4),
}


def main(out_dir=None):
    out = Path(out_dir) if out_dir else ROOT / "docs" / "reports"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for template, (target, build) in REPORTS.items():
            subprocess.run(
                ["soffice", "--headless", "--convert-to", "docx", "--outdir", tmp, str(TEMPLATES / template)],
                check=True,
                capture_output=True,
            )
            section5, section6 = build()
            fill(Path(tmp) / template.replace(".doc", ".docx"), out / target, section5, section6)
            print("已生成", out / target)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
