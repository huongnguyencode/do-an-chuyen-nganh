(() => {
  const panel = document.querySelector(".editor-panel");
  if (!panel) return;

  const problemId = Number(panel.dataset.problemId);
  const problemSlug = panel.dataset.problemSlug;
  const functionName = panel.dataset.functionName;
  const source = document.querySelector("#source-code");
  const runSampleButton = document.querySelector("#run-public-samples");
  const submitButton = document.querySelector("#submit-code");
  const message = document.querySelector("#submit-message");
  const state = document.querySelector("#submission-state");
  const resultBox = document.querySelector("#grading-result");
  const summary = document.querySelector("#result-summary");
  const publicResults = document.querySelector("#public-results");

  const quotaBadge = document.querySelector("#quota-badge");
  const quotaDetail = document.querySelector("#quota-detail");
  const hintButton = document.querySelector("#request-hint");
  const cooldownTimer = document.querySelector("#cooldown-timer");
  const hintMessage = document.querySelector("#hint-message");
  const hintList = document.querySelector("#hint-list");

  const CLIENT_SAMPLE_TIMEOUT_MS = 5000;

  const ERROR_MESSAGES = {
    cooldown_active: "Bạn vừa nhận gợi ý. Vui lòng chờ hết thời gian cooldown trước khi yêu cầu tiếp.",
    quota_exhausted: "Bạn đã sử dụng hết 3/3 lượt gợi ý cho bài tập này.",
    request_already_processing: "Hệ thống đang xử lý một yêu cầu gợi ý trước đó của bạn.",
    no_public_evidence_available: "Bài làm chỉ sai ở kiểm thử ẩn nên hệ thống không trích xuất dữ kiện để tránh lộ test ẩn.",
    all_passed: "Bài làm đã đạt toàn bộ kiểm thử nên không cần gợi ý sửa lỗi.",
    grading_pending: "Lượt chấm chưa hoàn tất. Vui lòng đợi kết quả chấm trước khi yêu cầu gợi ý.",
    grading_technical_error: "Lượt chấm gặp lỗi kỹ thuật nên chưa thể tạo gợi ý.",
    llm_busy: "Hệ thống trợ giảng AI đang xử lý tối đa luồng đồng thời. Vui lòng thử lại sau vài giây (bạn không bị trừ lượt).",
  };

  let activeSubmissionId = null;
  let activeRunId = null;
  let activeRunEligibleForHint = false;
  let isRequestingHint = false;
  let sampleWorker = null;
  let pollTimerId = null;
  let currentQuota = {
    used_count: 0,
    max_quota: 3,
    remaining_count: 3,
    next_level: "KM",
    cooldown_remaining_seconds: 0,
    has_processing_request: false,
  };
  let cooldownIntervalId = null;

  function setState(text, kind = "neutral") {
    state.textContent = text;
    state.className = `status-pill ${kind}`;
  }

  function makeRequestKey() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function formatHintError(code) {
    if (!code) return "Không thể yêu cầu gợi ý.";
    return ERROR_MESSAGES[code] || code;
  }

  function updateHintButtonState() {
    if (!hintButton) return;
    const canRequest =
      !isRequestingHint &&
      activeRunEligibleForHint &&
      currentQuota.remaining_count > 0 &&
      currentQuota.cooldown_remaining_seconds <= 0 &&
      !currentQuota.has_processing_request;
    hintButton.disabled = !canRequest;
    if (currentQuota.remaining_count <= 0) {
      hintButton.textContent = "Đã hết lượt gợi ý";
    } else if (currentQuota.next_level) {
      hintButton.textContent = `Yêu cầu gợi ý (${currentQuota.next_level})`;
    } else {
      hintButton.textContent = "Yêu cầu gợi ý";
    }
  }

  function startCooldownCountdown(seconds) {
    if (cooldownIntervalId) {
      window.clearInterval(cooldownIntervalId);
      cooldownIntervalId = null;
    }
    currentQuota.cooldown_remaining_seconds = Math.max(0, Number(seconds) || 0);
    if (!cooldownTimer) return;

    const tick = () => {
      if (currentQuota.cooldown_remaining_seconds <= 0) {
        cooldownTimer.hidden = true;
        cooldownTimer.textContent = "";
        if (cooldownIntervalId) {
          window.clearInterval(cooldownIntervalId);
          cooldownIntervalId = null;
        }
        updateHintButtonState();
        return;
      }
      cooldownTimer.hidden = false;
      cooldownTimer.textContent = `Chờ cooldown: ${currentQuota.cooldown_remaining_seconds}s`;
      currentQuota.cooldown_remaining_seconds -= 1;
      updateHintButtonState();
    };

    tick();
    if (currentQuota.cooldown_remaining_seconds > 0) {
      cooldownIntervalId = window.setInterval(tick, 1000);
    }
  }

  function renderQuota(quota) {
    if (!quota) return;
    currentQuota = quota;
    if (quotaBadge) {
      quotaBadge.textContent = `Còn ${quota.remaining_count}/${quota.max_quota} lượt`;
      quotaBadge.className = `status-pill ${quota.remaining_count > 0 ? "neutral" : "danger"}`;
    }
    if (quotaDetail) {
      if (quota.remaining_count <= 0) {
        quotaDetail.textContent = "Bạn đã sử dụng hết 3/3 lượt gợi ý cho bài tập này.";
      } else {
        const levelDesc =
          quota.next_level === "KM"
            ? "KM (Nhận diện vị trí và nguyên nhân lỗi)"
            : "KH (Định hướng bước kiểm tra và sửa bài)";
        quotaDetail.textContent = `Mức gợi ý tiếp theo: ${levelDesc}. Đã dùng ${quota.used_count}/${quota.max_quota} lượt.`;
      }
    }
    startCooldownCountdown(quota.cooldown_remaining_seconds);
    updateHintButtonState();
  }

  function createHintCard(item) {
    const card = document.createElement("article");
    const levelClass = (item.level || "KM").toLowerCase();
    card.className = `hint-card level-${levelClass}`;

    const header = document.createElement("div");
    header.className = "hint-card-header";
    const strong = document.createElement("strong");
    strong.textContent = `Gợi ý mức ${item.level}`;
    const meta = document.createElement("span");
    meta.textContent = `Lượt chấm #${item.grading_run_id} · ${item.model_id}`;
    header.append(strong, meta);

    const body = document.createElement("p");
    body.className = "hint-body";
    body.textContent = item.hint_text || "";

    card.append(header, body);
    return card;
  }

  function renderHintList(hints) {
    if (!hintList) return;
    hintList.replaceChildren();
    (hints || []).forEach((item) => {
      hintList.append(createHintCard(item));
    });
  }

  async function loadProblemHints() {
    if (!problemSlug) return;
    try {
      const response = await fetch(`/api/problems/${problemSlug}/hints`);
      if (!response.ok) return;
      const payload = await response.json();
      renderQuota(payload.quota);
      renderHintList(payload.hints);
    } catch (_) {
      // Bỏ qua lỗi mạng tạm thời khi tải trạng thái ban đầu
    }
  }

  function renderTestCards(results) {
    publicResults.replaceChildren();
    results.forEach((item) => {
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
  }

  function renderResult(payload) {
    const totals = payload.summary;
    resultBox.hidden = false;
    summary.textContent = `${totals.passed_count}/${totals.expected_test_count} test đạt.`;
    renderTestCards(payload.public_results);

    if (payload.status === "completed") {
      setState(payload.all_passed ? "Đạt" : "Chưa đạt", payload.all_passed ? "success" : "danger");
      activeSubmissionId = payload.submission_id;
      activeRunId = payload.grading_run_id;
      activeRunEligibleForHint = payload.all_passed === false;
    } else if (payload.status === "technical_error") {
      setState("Lỗi kỹ thuật", "danger");
      message.textContent = "Không thể kết luận bài làm. Hãy thử lại sau.";
      activeRunEligibleForHint = false;
    }
    updateHintButtonState();
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
        pollTimerId = window.setTimeout(() => pollResult(submissionId, runId, attempts + 1), 1000);
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

  function createPyodideWorker() {
    const workerSource = `
      let pyodideReadyPromise = null;
      function getPyodide() {
        if (!pyodideReadyPromise) {
          importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js");
          pyodideReadyPromise = self.loadPyodide({
            indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.2/full/"
          });
        }
        return pyodideReadyPromise;
      }

      self.onmessage = async (event) => {
        const { sourceCode, functionName, examples } = event.data;
        try {
          const pyodide = await getPyodide();
          pyodide.globals.set("_USER_CODE", sourceCode);
          pyodide.globals.set("_FUNC_NAME", functionName);
          pyodide.globals.set("_TESTS_JSON", JSON.stringify(examples));
          const rawJson = await pyodide.runPythonAsync(\`
import copy, json

# Đồng nhất 100% thuật toán so sánh đệ quy kiểm tra kiểu trước giá trị với app/judging/comparison.py trên Server
def _values_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _values_equal(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, dict):
        return set(left.keys()) == set(right.keys()) and all(
            _values_equal(left[k], right[k]) for k in left
        )
    return left == right

_ns = {"__name__": "client_sample_runner"}
_out = []
try:
    _comp = compile(_USER_CODE, "<student_submission>", "exec")
    exec(_comp, _ns, _ns)
    _fn = _ns.get(_FUNC_NAME)
    if not callable(_fn):
        raise TypeError("required_function_not_found")
    for _t in json.loads(_TESTS_JSON):
        try:
            _val = _fn(*copy.deepcopy(_t["args"]))
            json.dumps(_val, ensure_ascii=False, allow_nan=False)
            _ok = _values_equal(_val, _t["expected"])
            _out.append({
                "test_index": _t["test_index"],
                "status": "passed" if _ok else "wrong_answer",
                "args": _t["args"],
                "expected": _t["expected"],
                "actual": _val,
                "error_summary": None,
            })
        except Exception as _e:
            _out.append({
                "test_index": _t["test_index"],
                "status": "runtime_error",
                "args": _t["args"],
                "expected": _t["expected"],
                "actual": None,
                "error_summary": f"{type(_e).__name__}: {_e}",
            })
except SyntaxError as _se:
    for _t in json.loads(_TESTS_JSON):
        _out.append({
            "test_index": _t["test_index"],
            "status": "syntax_error",
            "args": _t["args"],
            "expected": _t["expected"],
            "actual": None,
            "error_summary": f"SyntaxError: {_se}",
        })
except Exception as _re:
    for _t in json.loads(_TESTS_JSON):
        _out.append({
            "test_index": _t["test_index"],
            "status": "runtime_error",
            "args": _t["args"],
            "expected": _t["expected"],
            "actual": None,
            "error_summary": f"{type(_re).__name__}: {_re}",
        })
json.dumps(_out, ensure_ascii=False)
          \`);
          self.postMessage({ ok: true, results: JSON.parse(rawJson) });
        } catch (err) {
          self.postMessage({ ok: false, error: err ? err.message : "Lỗi thực thi Pyodide Worker." });
        }
      };
    `;
    const blob = new Blob([workerSource], { type: "application/javascript" });
    const blobUrl = URL.createObjectURL(blob);
    const worker = new Worker(blobUrl);
    URL.revokeObjectURL(blobUrl);
    return worker;
  }

  function runSamplesInWebWorker(sourceCode, fnName, examples) {
    return new Promise((resolve, reject) => {
      if (!sampleWorker) {
        sampleWorker = createPyodideWorker();
      }
      const timeoutId = window.setTimeout(() => {
        if (sampleWorker) {
          sampleWorker.terminate();
          sampleWorker = null;
        }
        const tleResults = examples.map((t) => ({
          test_index: t.test_index,
          status: "time_limit_exceeded",
          args: t.args,
          expected: t.expected,
          actual: null,
          error_summary: "Vòng lặp quá 5 giây: Web Worker đã tự động ngắt để bảo vệ trình duyệt.",
        }));
        resolve(tleResults);
      }, CLIENT_SAMPLE_TIMEOUT_MS);

      sampleWorker.onmessage = (event) => {
        window.clearTimeout(timeoutId);
        if (event.data && event.data.ok) {
          resolve(event.data.results);
        } else {
          reject(new Error((event.data && event.data.error) || "Lỗi chạy thử trên Web Worker."));
        }
      };
      sampleWorker.onerror = (err) => {
        window.clearTimeout(timeoutId);
        sampleWorker.terminate();
        sampleWorker = null;
        reject(new Error(err.message || "Lỗi khởi tạo Pyodide Web Worker."));
      };
      sampleWorker.postMessage({
        sourceCode,
        functionName: fnName,
        examples,
      });
    });
  }

  if (runSampleButton && functionName) {
    runSampleButton.addEventListener("click", async () => {
      runSampleButton.disabled = true;
      message.textContent = "Đang chạy thử 3 test công khai trong Web Worker cô lập (giới hạn 5s)...";
      try {
        const examples = Array.from(document.querySelectorAll(".examples .example")).map((el) => ({
          test_index: Number(el.dataset.testIndex),
          args: JSON.parse(el.dataset.args || "[]"),
          expected: JSON.parse(el.dataset.expected || "null"),
        }));
        const results = await runSamplesInWebWorker(source.value, functionName, examples);
        const passed = results.filter((r) => r.status === "passed").length;
        resultBox.hidden = false;
        summary.textContent = `[Chạy thử Client Web Worker] ${passed}/${results.length} ví dụ công khai đạt.`;
        renderTestCards(results);
        setState(passed === results.length ? "Ví dụ đạt" : "Ví dụ chưa đạt", passed === results.length ? "success" : "danger");
        message.textContent = "Đã chạy thử trong Web Worker. Bấm 'Nộp bài' để chấm chính thức 8 test trên Judge0.";
      } catch (err) {
        message.textContent = err.message || "Lỗi khi chạy thử trên trình duyệt.";
      } finally {
        runSampleButton.disabled = false;
      }
    });
  }

  if (source) {
    source.addEventListener("keydown", (event) => {
      if (event.key === "Tab") {
        event.preventDefault();
        const start = source.selectionStart;
        const end = source.selectionEnd;
        source.value = `${source.value.slice(0, start)}    ${source.value.slice(end)}`;
        source.selectionStart = source.selectionEnd = start + 4;
      }
    });
  }

  submitButton.addEventListener("click", async () => {
    if (pollTimerId) {
      window.clearTimeout(pollTimerId);
      pollTimerId = null;
    }
    submitButton.disabled = true;
    activeSubmissionId = null;
    activeRunId = null;
    activeRunEligibleForHint = false;
    updateHintButtonState();
    message.textContent = "";
    if (hintMessage) hintMessage.textContent = "";
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

  if (hintButton) {
    hintButton.addEventListener("click", async () => {
      if (!activeSubmissionId || !activeRunId || isRequestingHint) return;
      isRequestingHint = true;
      updateHintButtonState();
      if (hintMessage) {
        hintMessage.className = "hint-status-msg";
        hintMessage.textContent = "Đang tạo và kiểm duyệt gợi ý...";
      }
      try {
        const response = await fetch(`/api/submissions/${activeSubmissionId}/hints`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            grading_run_id: activeRunId,
            request_key: makeRequestKey(),
          }),
        });
        const payload = await response.json();
        if (!response.ok) {
          if (typeof payload.remaining_count === "number") {
            currentQuota.remaining_count = payload.remaining_count;
            currentQuota.used_count = Math.max(0, currentQuota.max_quota - payload.remaining_count);
          }
          if (payload.retry_after_seconds) {
            startCooldownCountdown(payload.retry_after_seconds);
          }
          throw new Error(formatHintError(payload.error_code || payload.detail));
        }
        if (payload.quota) {
          renderQuota(payload.quota);
        }
        if (payload.status === "succeeded" && payload.hint_text) {
          if (hintMessage) {
            hintMessage.className = "hint-status-msg success";
            hintMessage.textContent = `Đã lưu gợi ý mức ${payload.level}.`;
          }
          if (hintList) {
            hintList.append(createHintCard(payload));
          }
        } else {
          if (hintMessage) {
            hintMessage.className = "hint-status-msg danger";
            hintMessage.textContent = `Không tạo được gợi ý hợp lệ (${payload.error_code || "lỗi dịch vụ"}) — bạn không bị trừ lượt.`;
          }
        }
      } catch (error) {
        if (hintMessage) {
          hintMessage.className = "hint-status-msg danger";
          hintMessage.textContent = error.message;
        }
      } finally {
        isRequestingHint = false;
        updateHintButtonState();
      }
    });
  }

  loadProblemHints();
})();
