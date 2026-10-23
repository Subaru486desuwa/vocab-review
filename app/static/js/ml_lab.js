// 实验三：提交手工样例，显示模型输出、版本与耗时。
(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const form = document.getElementById("recall-form");
  const box = document.getElementById("recall-result");

  function line(text) {
    const p = document.createElement("p");
    p.textContent = text;
    return p;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const body = Object.fromEntries(["delta_seconds", "history_seen", "history_correct"].map((k) => [k, Number(data.get(k))]));
    const response = await fetch("/api/v1/ml/recall", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    box.replaceChildren();
    if (!response.ok) {
      box.append(line(`无法估计：${payload.error.message}`));
    } else if (payload.data.status === "cold_start") {
      box.append(line("冷启动：没有历史作答，不给出估计（expected_recall = null）。"));
    } else {
      const d = payload.data;
      box.append(
        line(`expected_recall = ${d.expected_recall.toFixed(4)}`),
        line(`模型 ${d.model.model_code} ${d.model.version} · ${d.model.feature_schema_version}`),
        line(`模型计算 ${d.model_time_ms} ms · 处理 ${d.processing_time_ms} ms · request_id ${payload.request_id}`),
      );
    }
    box.hidden = false;
  });
})();
