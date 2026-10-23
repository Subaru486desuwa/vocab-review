// 练习：一屏一题，提交后显示服务端判分结果。重复提交由服务端幂等处理。
(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const $ = (id) => document.getElementById(id);
  const skillNames = { recognition: "辨义", spelling: "拼写", context: "语境" };
  const errorNames = { meaning: "释义", spelling: "拼写", context: "语境", unanswered: "未作答", unknown: "未知" };
  let session = null;
  let current = null;

  async function request(method, url, body) {
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error.message);
    return payload.data;
  }

  function showError(error) {
    $("practice-error").textContent = error ? error.message : "";
  }

  function nextItem() {
    return session.items.find((item) => item.result === null) || null;
  }

  function renderItem() {
    current = nextItem();
    if (current === null) return renderSummary();
    $("start-form").hidden = true;
    $("practice").hidden = false;
    $("feedback").hidden = true;
    $("next").hidden = true;
    $("submit-answer").hidden = false;
    $("submit-answer").disabled = false;
    $("progress").textContent = `${skillNames[current.skill_type]} · 第 ${current.position} / ${session.total} 题`;
    $("prompt").textContent = current.prompt;
    const area = $("answer-area");
    area.replaceChildren();
    if (current.options) {
      for (const option of current.options) {
        const label = document.createElement("label");
        label.className = "choice option";
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "answer";
        radio.value = option.id;
        label.append(radio, ` ${option.text}`);
        area.append(label);
      }
    } else {
      const input = document.createElement("input");
      input.name = "answer";
      input.autocomplete = "off";
      input.autocapitalize = "off";
      input.spellcheck = false;
      input.setAttribute("aria-label", "输入单词");
      area.append(input);
      input.focus();
    }
  }

  function readAnswer() {
    if (current.options) {
      const checked = $("answer-area").querySelector("input:checked");
      return checked ? checked.value : "";
    }
    return $("answer-area").querySelector("input").value;
  }

  function renderFeedback(result) {
    const box = $("feedback");
    box.replaceChildren();
    const verdict = document.createElement("p");
    verdict.className = result.is_correct ? "verdict correct" : "verdict wrong";
    verdict.textContent = result.is_correct ? "回答正确" : `回答错误（${errorNames[result.error_type] || result.error_type}）`;
    const detail = document.createElement("p");
    detail.textContent = `标准答案：${result.correct_answer.text} · ${result.lemma}：${result.definition_zh}`;
    box.append(verdict, detail);
    box.hidden = false;
    $("submit-answer").hidden = true;
    $("next").hidden = false;
    $("next").textContent = nextItem() ? "下一题" : "查看小结";
    $("next").focus();
  }

  function renderSummary() {
    $("practice").hidden = true;
    const correct = session.items.filter((item) => item.result && item.result.is_correct).length;
    const box = $("summary");
    box.replaceChildren();
    const title = document.createElement("h2");
    title.textContent = "本组练习完成";
    const line = document.createElement("p");
    line.className = "lead";
    line.textContent = `${skillNames[session.skill_type]}题 ${session.total} 道，答对 ${correct} 道。错题会在 10 分钟后进入复习。`;
    const again = document.createElement("a");
    again.className = "button";
    again.href = "/practice";
    again.textContent = "再练一组";
    box.append(title, line, again);
    box.hidden = false;
  }

  $("start-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    showError(null);
    const form = new FormData(event.target);
    try {
      session = await request("POST", "/api/v1/practice/sessions", {
        skill_type: form.get("skill_type"),
        count: Number(form.get("count")),
      });
      history.replaceState(null, "", `/practice?session=${session.id}`);
      renderItem();
    } catch (error) {
      showError(error);
    }
  });

  $("answer-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if ($("submit-answer").disabled || $("submit-answer").hidden) return;
    $("submit-answer").disabled = true;
    showError(null);
    try {
      const result = await request("POST", `/api/v1/practice/items/${current.id}/answer`, { answer: readAnswer() });
      current.result = result;
      renderFeedback(result);
    } catch (error) {
      $("submit-answer").disabled = false;
      showError(error);
    }
  });

  $("next").addEventListener("click", renderItem);

  const resumeId = new URLSearchParams(location.search).get("session");
  if (resumeId) {
    request("GET", `/api/v1/practice/sessions/${encodeURIComponent(resumeId)}`)
      .then((data) => {
        session = data;
        renderItem();
      })
      .catch(showError);
  }
})();
