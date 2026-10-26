(() => {
  const panel = document.querySelector(".editor-panel");
  if (!panel) return;

  const problemId = Number(panel.dataset.problemId);
  const source = document.querySelector("#source-code");
  const submitButton = document.querySelector("#submit-code");
  const message = document.querySelector("#submit-message");
  const state = document.querySelector("#submission-state");
  const resultBox = document.querySelector("#grading-result");
  const summary = document.querySelector("#result-summary");
  const publicResults = document.querySelector("#public-results");

  function setState(text, kind = "neutral") {
    state.textContent = text;
    state.className = `status-pill ${kind}`;
  }

  function renderResult(payload) {
    const totals = payload.summary;
    resultBox.hidden = false;
    summary.textContent = `${totals.passed_count}/${totals.expected_test_count} test đạt.`;
    publicResults.replaceChildren();

    payload.public_results.forEach((item) => {
      const card = document.createElement("article");
      card.className = `test-result ${item.status === "passed" ? "passed" : "failed"}`;
      const heading = document.createElement("strong");
      heading.textContent = `Test ${item.test_index}: ${item.status}`;
      const details = document.createElement("pre");
      details.textContent = `args = ${JSON.stringify(item.args)}\nexpected = ${JSON.stringify(item.expected)}\nactual = ${JSON.stringify(item.actual)}`;
      card.append(heading, details);
      if (item.error_summary) {
        const error = document.createElement("p");
        error.textContent = item.error_summary;
        card.append(error);
      }
      publicResults.append(card);
    });

    if (payload.status === "completed") {
      setState(payload.all_passed ? "Đạt" : "Chưa đạt", payload.all_passed ? "success" : "danger");
    } else if (payload.status === "technical_error") {
      setState("Lỗi kỹ thuật", "danger");
      message.textContent = "Không thể kết luận bài làm. Hãy thử lại sau.";
    }
  }

  async function pollResult(submissionId, runId, attempts = 0) {
    if (attempts >= 120) {
      setState("Chờ quá lâu", "danger");
      message.textContent = "Lượt chấm chưa hoàn tất. Bạn có thể xem lại trong lịch sử.";
      submitButton.disabled = false;
      return;
    }
    try {
      const response = await fetch(`/api/submissions/${submissionId}/grading-runs/${runId}`);
      if (!response.ok) throw new Error("Không đọc được kết quả chấm.");
      const payload = await response.json();
      if (payload.status === "queued" || payload.status === "running") {
        setState(payload.status === "queued" ? "Đang chờ" : "Đang chấm");
        window.setTimeout(() => pollResult(submissionId, runId, attempts + 1), 1000);
        return;
      }
      renderResult(payload);
      submitButton.disabled = false;
    } catch (error) {
      setState("Lỗi kết nối", "danger");
      message.textContent = error.message;
      submitButton.disabled = false;
    }
  }

  submitButton.addEventListener("click", async () => {
    submitButton.disabled = true;
    message.textContent = "";
    resultBox.hidden = true;
    setState("Đang gửi");
    try {
      const response = await fetch("/api/submissions", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({problem_id: problemId, source_code: source.value}),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Không thể nộp bài.");
      }
      setState("Đang chờ");
      pollResult(payload.submission_id, payload.grading_run_id);
    } catch (error) {
      setState("Nộp thất bại", "danger");
      message.textContent = error.message;
      submitButton.disabled = false;
    }
  });
})();
