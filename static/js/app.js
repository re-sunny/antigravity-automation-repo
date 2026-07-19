/**
 * 클라이언트 측 스크립트로 데이터 파싱, 대시보드 통계 분석,
 * 파이프라인 빌더 상호작용, 모달 제어 및 실행 로그 모니터링을 담당합니다.
 */

// 전역 상태 컨테이너
let pipelines = [];
let executions = [];
let actions = [];
let builderSteps = [];
let activePipelineId = null;

// DOM 로드 완료 시 초기화 시행
document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

/**
 * 초기 목록을 연동하고 대시보드 무한 루프 조회 폴을 기동하여 프로그램을 활성화합니다.
 *
 * 입력인자: 없음
 * 반환값: 없음
 */
async function initApp() {
    setupEventListeners();
    await fetchActions();
    await refreshDashboard();

    // 백그라운드에서 4초마다 대시보드 내용 및 이력 목록 갱신
    setInterval(async () => {
        await refreshDashboard();
    }, 4000);
}

/**
 * HTML 요소의 이벤트 리스너와 핸들러를 바인딩합니다.
 *
 * 입력인자: 없음
 * 반환값: 없음
 */
function setupEventListeners() {
    // 파이프라인 생성 버튼 클릭 이벤트
    document.getElementById("btn-create-pipeline").addEventListener("click", () => {
        openPipelineBuilder();
    });

    document.getElementById("btn-close-builder").addEventListener("click", () => {
        closeModal("modal-builder");
    });

    document.getElementById("btn-close-details").addEventListener("click", () => {
        closeModal("modal-details");
    });

    document.getElementById("btn-add-step").addEventListener("click", () => {
        addStepToBuilder();
    });

    document.getElementById("pipeline-form").addEventListener("submit", (e) => {
        e.preventDefault();
        savePipeline();
    });

    // 선택한 트리거 유형에 따라 입력 영역을 동적으로 숨기거나 보여줍니다.
    document.getElementById("trigger-type").addEventListener("change", (e) => {
        handleTriggerTypeChange(e.target.value);
    });
}

/**
 * 시스템 백엔드에 기등록된 액션 플러그인 리스트를 호출합니다.
 *
 * 입력인자: 없음
 * 반환값: 없음
 */
async function fetchActions() {
    try {
        const response = await fetch("/api/actions");
        if (response.ok) {
            const data = await response.json();
            actions = data.actions;
        }
    } catch (error) {
        console.error("등록된 액션 정보를 가져오는데 실패했습니다:", error);
    }
}

/**
 * 파이프라인 현황 데이터, 실행 통계, 목록 등을 전체 새로고침합니다.
 *
 * 입력인자: 없음
 * 반환값: 없음
 */
async function refreshDashboard() {
    try {
        const pipesResponse = await fetch("/api/pipelines");
        const execsResponse = await fetch("/api/executions");

        if (pipesResponse.ok && execsResponse.ok) {
            pipelines = await pipesResponse.json();
            executions = await execsResponse.json();

            renderPipelines();
            renderExecutions();
            updateDashboardStats();
        }
    } catch (error) {
        console.error("대시보드 갱신 오류:", error);
    }
}

/**
 * 대시보드 메인 화면 상단의 통계 지표 수치를 갱신합니다.
 *
 * 입력인자: 없음
 * 반환값: 없음
 */
function updateDashboardStats() {
    const totalPipes = pipelines.length;
    const activePipes = pipelines.filter(p => p.status === "active").length;

    const totalExecs = executions.length;
    const successExecs = executions.filter(e => e.status === "success").length;
    const failedExecs = executions.filter(e => e.status === "failed").length;

    document.getElementById("stat-total-pipelines").innerText = totalPipes;
    document.getElementById("stat-active-pipelines").innerText = activePipes;
    document.getElementById("stat-success-runs").innerText = successExecs;
    document.getElementById("stat-failed-runs").innerText = failedExecs;
}

/**
 * 선택한 트리거 유형에 알맞게 UI 폼과 플레이스홀더를 변경합니다.
 *
 * 입력인자:
 * - triggerType: 트리거 구분 코드 문자열 ("cron", "interval", "manual").
 *
 * 반환값: 없음
 */
function handleTriggerTypeChange(triggerType) {
    const valueGroup = document.getElementById("trigger-val-group");
    const valLabel = document.getElementById("trigger-val-label");
    const valInput = document.getElementById("trigger-value");
    const helper = document.getElementById("trigger-val-helper");

    if (triggerType === "manual") {
        valueGroup.style.display = "none";
        valInput.removeAttribute("required");
    } else {
        valueGroup.style.display = "flex";
        valInput.setAttribute("required", "true");

        if (triggerType === "cron") {
            valLabel.innerText = "크론 표현식";
            valInput.placeholder = "예: 0 9 * * * (매일 오전 9시 정각 실행)";
            helper.innerText = "표준 크론 표현식을 규격에 맞게 입력하세요: 분 시 일 월 요일";
        } else if (triggerType === "interval") {
            valLabel.innerText = "간격 설정값 (초 단위)";
            valInput.placeholder = "예: 60 (1분마다 주기적 반복 실행)";
            helper.innerText = "실행과 다음 실행 사이의 기동 대기 연장 간격을 정수 단위(초)로 적어주세요.";
        }
    }
}

/**
 * 화면에 설정되어 구성된 파이프라인 카드 목록을 다시 그립니다.
 *
 * 입력인자: 없음
 * 반환값: 없음
 */
function renderPipelines() {
    const listContainer = document.getElementById("pipelines-list-container");
    listContainer.innerHTML = "";

    if (pipelines.length === 0) {
        listContainer.innerHTML = `<div class="no-data">설정된 자동화 파이프라인이 없습니다. 오른쪽 위의 [파이프라인 생성] 단추를 클릭해 신규 흐름을 구성해보세요.</div>`;
        return;
    }

    pipelines.forEach(pipe => {
        const item = document.createElement("div");
        item.className = "pipeline-item";

        // 파이프라인 내부 흐름 단계를 가시화하는 노드 스트링 세팅
        const stepsFlow = pipe.steps.map(s => {
            return `<span class="pipeline-step-node">${s.action_name}</span>`;
        }).join('<span class="pipeline-step-arrow">→</span>');

        const isActive = pipe.status === "active";

        item.innerHTML = `
            <div class="pipeline-meta">
                <div class="pipeline-info">
                    <div class="pipeline-name">${pipe.name}</div>
                    <div class="pipeline-trigger">
                        <span>트리거:</span>
                        <span class="tag">${pipe.trigger_type.toUpperCase()}</span>
                        ${pipe.trigger_value ? `<span>${pipe.trigger_value}</span>` : ""}
                        <span class="pulse-light ${isActive ? '' : 'inactive'}"></span>
                    </div>
                </div>
                <div>
                    <label class="switch">
                        <input type="checkbox" ${isActive ? 'checked' : ''} onchange="togglePipelineStatus(${pipe.id}, this.checked)">
                        <span class="slider"></span>
                    </label>
                </div>
            </div>
            
            <div class="pipeline-flow">
                ${stepsFlow || '<span class="text-muted">설정된 실행 단계 없음</span>'}
            </div>
            
            <div class="pipeline-actions">
                <button class="btn btn-action" onclick="triggerPipeline(${pipe.id})">즉시 실행</button>
                <button class="btn btn-secondary btn-action" onclick="openPipelineBuilder(${pipe.id})">편집</button>
                <button class="btn btn-outline-danger" onclick="deletePipeline(${pipe.id})">삭제</button>
            </div>
        `;
        listContainer.appendChild(item);
    });
}

/**
 * 실행 완료된 전체 내역 리스트 표를 갱신합니다.
 *
 * 입력인자: 없음
 * 반환값: 없음
 */
function renderExecutions() {
    const listContainer = document.getElementById("executions-list-container");
    listContainer.innerHTML = "";

    if (executions.length === 0) {
        listContainer.innerHTML = `<div class="no-data">저장된 실행 이력 데이터가 존재하지 않습니다.</div>`;
        return;
    }

    executions.forEach(exec => {
        const row = document.createElement("div");
        row.className = "execution-row";
        row.onclick = () => viewExecutionDetails(exec.id);

        const timestamp = new Date(exec.started_at).toLocaleString();
        const durationDisplay = exec.duration ? `${exec.duration}초` : "대기 중";

        let statusText = "대기";
        if (exec.status === "success") statusText = "성공";
        else if (exec.status === "failed") statusText = "실패";
        else if (exec.status === "running") statusText = "진행 중";

        row.innerHTML = `
            <div class="execution-info">
                <span class="execution-name-row">${exec.pipeline_name}</span>
                <span class="execution-id-sub">실행 ID: ${exec.id.substring(0, 8)}...</span>
            </div>
            <div class="execution-time-row">
                <span>시작 시간: ${timestamp}</span>
                <span style="margin-left: 1rem; color: var(--text-muted);">| 소요 시간: ${durationDisplay}</span>
            </div>
            <div>
                <span class="status-badge ${exec.status}">
                    ${statusText}
                </span>
            </div>
        `;
        listContainer.appendChild(row);
    });
}

/**
 * 스케줄에 등록되어 작동 중인 파이프라인의 활성화 여부를 토글합니다.
 *
 * 입력인자:
 * - id: 대상 파이프라인 데이터베이스 Primary Key.
 * - isActive: 활성화 토글 스위치의 체크 값 상태 플래그.
 *
 * 반환값: 없음
 */
async function togglePipelineStatus(id, isActive) {
    try {
        const status = isActive ? "active" : "inactive";
        const response = await fetch(`/api/pipelines/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status })
        });
        if (response.ok) {
            await refreshDashboard();
        }
    } catch (error) {
        console.error("상태 전환 실패:", error);
    }
}

/**
 * 파이프라인을 API 요청으로 무조건 즉각 백그라운드 수동 실행합니다.
 *
 * 입력인자:
 * - id: 강제로 실행하려는 대상 파이프라인 ID.
 *
 * 반환값: 없음
 */
async function triggerPipeline(id) {
    try {
        const response = await fetch(`/api/pipelines/${id}/trigger`, {
            method: "POST"
        });
        if (response.ok) {
            await refreshDashboard();
            alert("백그라운드에서 워크플로우 임시 수동 작업이 즉시 시작되었습니다!");
        }
    } catch (error) {
        console.error("수동 트리거 실행 실패:", error);
    }
}

/**
 * 파이프라인을 완전히 제거하고 일정을 비웁니다.
 *
 * 입력인자:
 * - id: 삭제 대상으로 설정한 파이프라인 ID.
 *
 * 반환값: 없음
 */
async function deletePipeline(id) {
    if (!confirm("이 자동화 파이프라인을 데이터베이스에서 영구 삭제하시겠습니까?")) return;

    try {
        const response = await fetch(`/api/pipelines/${id}`, {
            method: "DELETE"
        });
        if (response.ok) {
            await refreshDashboard();
        }
    } catch (error) {
        console.error("파이프라인 삭제 실패:", error);
    }
}

/**
 * 파이프라인 생성 또는 수정 상세 모달 빌러를 표시합니다.
 *
 * 입력인자:
 * - id: 수정 데이터 대상 파이프라인 고유 ID (그 외 신규 생성 시 null 또는 생략).
 *
 * 반환값: 없음
 */
function openPipelineBuilder(id = null) {
    activePipelineId = id;
    builderSteps = [];

    const modalTitle = document.getElementById("builder-modal-title");
    const nameInput = document.getElementById("pipeline-name");
    const triggerSelect = document.getElementById("trigger-type");
    const valInput = document.getElementById("trigger-value");

    if (activePipelineId) {
        // 편집 모드로 데이터 로드
        modalTitle.innerText = "자동화 파이프라인 편집";
        const pipeline = pipelines.find(p => p.id === activePipelineId);
        if (pipeline) {
            nameInput.value = pipeline.name;
            triggerSelect.value = pipeline.trigger_type;
            valInput.value = pipeline.trigger_value || "";
            builderSteps = JSON.parse(JSON.stringify(pipeline.steps));
        }
    } else {
        // 신규 추가 모드 리셋
        modalTitle.innerText = "자동화 파이프라인 생성";
        nameInput.value = "";
        triggerSelect.value = "manual";
        valInput.value = "";
    }

    handleTriggerTypeChange(triggerSelect.value);
    renderBuilderSteps();
    openModal("modal-builder");
}

/**
 * 빌더 시퀀스에 특정한 개별 행동 처리 단계를 덧붙여 선언합니다.
 *
 * 입력인자: 없음
 * 반환값: 없음
 */
function addStepToBuilder() {
    const select = document.getElementById("step-action-selector");
    const actionName = select.value;

    if (!actionName) return;

    // 선택 액션 형태에 기본 전달 매개변수 구조 구성
    let defaultArgs = {};
    if (actionName === "scrape_news_feed") {
        defaultArgs = { url: "", limit: 5 };
    } else if (actionName === "create_excel") {
        defaultArgs = { filename: "output.xlsx", file_format: "xlsx" };
    } else if (actionName === "send_email") {
        defaultArgs = { to_email: "", subject: "자동 데이터 알림", body: "데이터 내용:\n{input_data}" };
    } else if (actionName === "scrape_tech_news") {
        defaultArgs = { limit: 5 };
    } else if (actionName === "save_to_supabase") {
        defaultArgs = {};
    } else if (actionName === "send_gmail") {
        defaultArgs = { to_email: "", subject: "일일 IT/테크 트렌드 리포트" };
    }

    builderSteps.push({
        action_name: actionName,
        args: defaultArgs
    });

    renderBuilderSteps();
    select.value = ""; // 선택 필트 메뉴 초기화
}

/**
 * 저장 중인 빌더 단계 객체에서 특정 한 행의 액션을 순서에서 덜어냅니다.
 *
 * 입력인자:
 * - index: 삭제를 위해 참조 설정할 해당 배열 인덱스.
 *
 * 반환값: 없음
 */
function removeStepFromBuilder(index) {
    builderSteps.splice(index, 1);
    renderBuilderSteps();
}

/**
 * 빌더 상에서 입력 또는 편집 중인 작업들의 상세 내용 및 폼 매개변수를 렌더링합니다.
 *
 * 입력인자: 없음
 * 반환값: 없음
 */
function renderBuilderSteps() {
    const container = document.getElementById("builder-steps-list");
    container.innerHTML = "";

    if (builderSteps.length === 0) {
        container.innerHTML = `<span class="no-data" style="padding: 1rem 0;">현재 설정된 실행 단계가 없습니다. 위의 목록에서 원하시는 액션을 찾아 [단계 추가]를 수행해주세요.</span>`;
        return;
    }

    builderSteps.forEach((step, index) => {
        const div = document.createElement("div");
        div.className = "builder-step-item";

        let argsInputs = "";

        // 개별 액션 분류에 맞도록 알맞은 전용 매개변수 설정 폼 그리기
        if (step.action_name === "scrape_news_feed") {
            argsInputs = `
                <div class="form-group">
                    <label>RSS / 뉴스 피드 URL (가상의 대체 데이터를 사용하는 경우 비워두십시오)</label>
                    <input type="text" value="${step.args.url || ''}" onchange="updateStepArg(${index}, 'url', this.value)" placeholder="https://example.com/rss">
                </div>
                <div class="form-group">
                    <label>기사 수집 개수 제한</label>
                    <input type="text" value="${step.args.limit || 5}" onchange="updateStepArg(${index}, 'limit', this.value)" placeholder="예: 5">
                </div>
            `;
        } else if (step.action_name === "create_excel") {
            argsInputs = `
                <div class="form-group">
                    <label>출력 파일명</label>
                    <input type="text" value="${step.args.filename || 'output.xlsx'}" onchange="updateStepArg(${index}, 'filename', this.value)" placeholder="예: report.xlsx">
                </div>
                <div class="form-group">
                    <label>파일 형식</label>
                    <select onchange="updateStepArg(${index}, 'file_format', this.value)">
                        <option value="xlsx" ${step.args.file_format === 'xlsx' ? 'selected' : ''}>Excel 그리드 (.xlsx)</option>
                        <option value="csv" ${step.args.file_format === 'csv' ? 'selected' : ''}>일반 CSV (.csv)</option>
                    </select>
                </div>
            `;
        } else if (step.action_name === "send_email") {
            argsInputs = `
                <div class="form-group">
                    <label>수신자 이메일 주소</label>
                    <input type="text" value="${step.args.to_email || ''}" onchange="updateStepArg(${index}, 'to_email', this.value)" placeholder="admin@example.com" required>
                </div>
                <div class="form-group">
                    <label>이메일 제목</label>
                    <input type="text" value="${step.args.subject || ''}" onchange="updateStepArg(${index}, 'subject', this.value)" placeholder="이메일 제목 입력">
                </div>
                <div class="form-group">
                    <label>이메일 본문 ({input_data} 입력 시 이전 단계의 결과물로 대체됨)</label>
                    <textarea rows="3" onchange="updateStepArg(${index}, 'body', this.value)" placeholder="이메일 상세 본문 입력...">${step.args.body || ''}</textarea>
                </div>
            `;
        } else if (step.action_name === "scrape_tech_news") {
            argsInputs = `
                <div class="form-group">
                    <label>정보 소스별 수집 기사 개수 제한 (GeekNews, ITWorld, TechCrunch 각각 적용)</label>
                    <input type="number" min="1" max="50" value="${step.args.limit || 5}" onchange="updateStepArg(${index}, 'limit', parseInt(this.value) || 5)" placeholder="예: 5">
                </div>
            `;
        } else if (step.action_name === "save_to_supabase") {
            argsInputs = `
                <div style="background: rgba(255,255,255,0.02); padding: 0.75rem; border-radius: 6px; border: 1px solid var(--border-color); font-size: 0.85rem; color: var(--text-muted);">
                    ⚡ 추가 입력 인자 없음. 수집된 뉴스(List)를 받아 .env에 등록된 Supabase의 <code>collected_news</code> 테이블로 자동으로 저장 및 중복 방지(Upsert) 처리를 수행합니다.
                </div>
            `;
        } else if (step.action_name === "send_gmail") {
            argsInputs = `
                <div class="form-group">
                    <label>수신자 Gmail 주소 (비워둘 시 발신자 본인에게 전송)</label>
                    <input type="text" value="${step.args.to_email || ''}" onchange="updateStepArg(${index}, 'to_email', this.value)" placeholder="username@gmail.com">
                </div>
                <div class="form-group">
                    <label>메일 제목</label>
                    <input type="text" value="${step.args.subject || ''}" onchange="updateStepArg(${index}, 'subject', this.value)" placeholder="예: 일일 IT/테크 트렌드 리포트">
                </div>
            `;
        }

        div.innerHTML = `
            <div class="builder-step-header">
                <span class="builder-step-title">
                    <span>단계 ${index + 1}:</span>
                    <span class="tag cyan">${step.action_name}</span>
                </span>
                <span class="builder-step-remove" onclick="removeStepFromBuilder(${index})">단계 삭제</span>
            </div>
            
            <div class="step-args-grid">
                ${argsInputs}
            </div>
        `;
        container.appendChild(div);
    });
}

/**
 * 사용자가 기입한 상세 설정 매개변수를 메모리 내 단계 매트릭스 변수에 실시간 바인딩시킵니다.
 *
 * 입력인자:
 * - stepIndex: 파이프라인 단계 배열 위치.
 * - key: 전달할 매개변수의 Key 키.
 * - value: 입력창에 작성한 최종 설정값.
 *
 * 반환값: 없음
 */
function updateStepArg(stepIndex, key, value) {
    builderSteps[stepIndex].args[key] = value;
}

/**
 * 작성 중인 전체 내역을 검사하고 REST API를 통해 백엔드 데이터 테이블에 파이프라인 정보를 확정 저장합니다.
 *
 * 입력인자: 없음
 * 반환값: 없음
 */
async function savePipeline() {
    const name = document.getElementById("pipeline-name").value;
    const trigger_type = document.getElementById("trigger-type").value;
    const trigger_value = trigger_type === "manual" ? null : document.getElementById("trigger-value").value;

    if (builderSteps.length === 0) {
        alert("자동화 파이프라인에 최소 하나 이상의 단계를 추가해 주세요.");
        return;
    }

    const payload = {
        name,
        trigger_type,
        trigger_value,
        steps: builderSteps
    };

    try {
        let response;
        if (activePipelineId) {
            // 변경 수정 사항 발생 처리
            response = await fetch(`/api/pipelines/${activePipelineId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        } else {
            // 신규 신설 작업 저장
            response = await fetch("/api/pipelines", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

        if (response.ok) {
            closeModal("modal-builder");
            await refreshDashboard();
        } else {
            const err = await response.json();
            alert(`파이프라인 저장에 실패하였습니다: ${err.detail || '상세 불명의 서버 에러'}`);
        }
    } catch (e) {
        console.error("파이프라인 저장 오류:", e);
    }
}

/**
 * 특정 상세 실행 고유 ID의 데이터 연동 이력을 역추적하여 전용 감사 모달창을 오픈합니다.
 *
 * 입력인자:
 * - execId: 세부 조회를 실행할 실행 고유 이력 ID.
 *
 * 반환값: 없음
 */
async function viewExecutionDetails(execId) {
    try {
        const response = await fetch(`/api/executions/${execId}`);
        if (response.ok) {
            const exec = await response.json();

            document.getElementById("detail-pipe-name").innerText = exec.pipeline_name;
            document.getElementById("detail-run-id").innerText = exec.id;

            const badge = document.getElementById("detail-status-badge");
            badge.className = `status-badge ${exec.status}`;

            let statusText = "대기";
            if (exec.status === "success") statusText = "성공";
            else if (exec.status === "failed") statusText = "실패";
            else if (exec.status === "running") statusText = "진행 중";
            badge.innerText = statusText;

            document.getElementById("detail-start-time").innerText = new Date(exec.started_at).toLocaleString();
            document.getElementById("detail-duration").innerText = exec.duration ? `${exec.duration}초` : "대기 중";

            // 전반적 취약 에러 내용 유무 확인 후 알림창 관리
            const errorBox = document.getElementById("detail-pipeline-error-box");
            if (exec.error_message) {
                errorBox.style.display = "block";
                document.getElementById("detail-pipeline-error").innerText = exec.error_message;
            } else {
                errorBox.style.display = "none";
            }

            // 개별 단위 루프 상세 현황 추적
            const stepsContainer = document.getElementById("detail-steps-trace-container");
            stepsContainer.innerHTML = "";

            if (exec.step_logs.length === 0) {
                stepsContainer.innerHTML = `<span class="no-data">이 실행에 대한 단계별 로그가 없습니다.</span>`;
            } else {
                exec.step_logs.forEach(step => {
                    const stepItem = document.createElement("div");
                    stepItem.className = "trace-step-item";

                    const isSuccess = step.status === "success";

                    let stepStatusText = "대기";
                    if (step.status === "success") stepStatusText = "성공";
                    else if (step.status === "failed") stepStatusText = "실패";
                    else if (step.status === "running") stepStatusText = "진행 중";

                    let errorBlock = "";
                    if (step.traceback) {
                        // 유발된 stack trace 예외 보고 내용 추출
                        errorBlock = `
                            <div class="io-box" style="grid-column: span 2; margin-top: 1rem;">
                                <span class="io-title" style="color: var(--color-danger)">단계 오류 및 트레이스백(Traceback)</span>
                                <pre class="code-block error">${step.traceback}</pre>
                            </div>
                        `;
                    }

                    stepItem.innerHTML = `
                        <div class="trace-step-header">
                            <span class="trace-step-title">
                                <span>단계 ${step.step_index + 1}:</span>
                                <span class="tag cyan">${step.action_name}</span>
                            </span>
                            <span class="status-badge ${step.status}">${stepStatusText} (${step.duration || 0}초)</span>
                        </div>
                        <div class="trace-step-body">
                            <div class="io-box">
                                <span class="io-title">입력 페이로드 데이터 컨텍스트</span>
                                <pre class="code-block json">${JSON.stringify(step.input_data, null, 2) || "없음"}</pre>
                            </div>
                            <div class="io-box">
                                <span class="io-title">출력 페이로드 데이터 응답</span>
                                <pre class="code-block json">${isSuccess ? JSON.stringify(step.output_data, null, 2) : "오류로 실행 중단됨"}</pre>
                            </div>
                            ${errorBlock}
                        </div>
                    `;
                    stepsContainer.appendChild(stepItem);
                });
            }

            openModal("modal-details");
        }
    } catch (e) {
        console.error("실행 세부정보 로드 실패:", e);
    }
}

/**
 * 대상 레이아웃 팝업 창을 활성 노출 상태로 변경 표시시킵니다.
 *
 * 입력인자:
 * - id: 대상 팝업 모달창 고유 ID.
 *
 * 반환값: 없음
 */
function openModal(id) {
    document.getElementById(id).classList.add("active");
}

/**
 * 대상 팝업 창을 비활성 은닉 상태로 만듭니다.
 *
 * 입력인자:
 * - id: 가림 처리할 팝업 모달창 고유 ID.
 *
 * 반환값: 없음
 */
function closeModal(id) {
    document.getElementById(id).classList.remove("active");
}

