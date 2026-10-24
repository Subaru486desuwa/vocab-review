// 今日任务：按钮直接创建练习，再进入练习页作答。
(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const error = document.getElementById("today-error");

  for (const button of document.querySelectorAll("button[data-skill]")) {
    button.addEventListener("click", async () => {
      if (button.disabled) return;
      button.disabled = true;
      error.textContent = "";
      const body = { skill_type: button.dataset.skill, count: Number(button.dataset.count) };
      if (button.dataset.focus) body.focus = button.dataset.focus;
      try {
        const response = await fetch("/api/v1/practice/sessions", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify(body),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error.message);
        location.href = `/practice?session=${payload.data.id}`;
      } catch (err) {
        error.textContent = err.message;
        button.disabled = false;
      }
    });
  }
})();
