---
name: jira-task
description: Use whenever (1) the user invokes /jira-task, (2) asks about Jira task management (registration · transition · switching · default-project setup), OR (3) Claude is about to perform any action producing artifacts (file edits, git commits, builds, deploys) without an active Jira task linked to the current branch — in case (3) this skill's "Safety net" section auto-registers a task before the action proceeds. Handles repo-scoped default project selection, issue creation flow (type/summary/description/assignee/epic/labels), automatic state transitions, active-task tracking, and per-task git worktree isolation. Works with any Jira project; default project is selected per repo on first use.
---

# jira-task

Claude Code 안에서 모든 산출물 있는 작업을 Jira 에 등록하고, task 마다 git worktree 로 격리하며, 상태 전이를 자동 처리한다.

---

## 사전 점검 — Atlassian MCP 서버

이 스킬의 모든 등록·전이·조회는 `mcp__atlassian__*` 도구에 의존한다. 스킬이 처음 호출되는 시점에 가용성을 확인한다.

**검사 방법**
- `mcp__atlassian__atlassianUserInfo` 를 한 번 호출 시도.
  - 정상 응답: MCP 정상. 응답의 `account_id`, `email`, `name` 등을 세션 캐시(이후 assignee 기본값으로 사용)하고 다음 단계 진행.
  - 도구가 존재하지 않음 / "No such tool" / 인증 실패 등의 오류: MCP 미설치 또는 미인증으로 판단 → 아래 안내 출력 후 등록 흐름 **중단**.

**미설치 안내 — 사용자에게 그대로 출력**

```
Atlassian MCP 서버가 설치(또는 인증)되어 있지 않습니다.
claude-jira-task 플러그인은 Anthropic 공식 Atlassian Remote MCP 서버에 의존합니다.

설치 (Claude Code 터미널에서):

    claude mcp add --transport http atlassian https://mcp.atlassian.com/v1/mcp

등록 후 Claude Code 를 재시작하면 OAuth 인증 안내가 표시됩니다.
인증을 완료한 뒤 다시 `/jira-task` 를 호출하세요.

이미 다른 세션에서 인증을 끝냈다고 생각되는데도 본 안내가 다시 뜬다면,
serverUrl 이 바뀐 직후(예: /v1/sse → /v1/mcp 마이그레이션)일 가능성이 높습니다.
Claude Code 는 OAuth 토큰을 (serverName + serverUrl) 단위로 분리 저장하므로
URL 이 달라지면 같은 "atlassian" 이라도 새 OAuth 가 필요합니다.
가장 간단한 해결: Claude Code 재시작 → 새 endpoint 로 OAuth 처음부터 진행.

자세한 내용 / cache 잔존물 청소: README "Troubleshooting — 알려진 함정" 참고.

공식 문서:
- https://support.atlassian.com/atlassian-rovo-mcp-server/docs/getting-started-with-the-atlassian-remote-mcp-server/
```

사용자가 안내를 받기 전엔 등록 절차 진입 금지. 단순 안내 출력만 하고 스킬 종료.

---

## 버전 확인 (스킬 진입 시 1회)

MCP 검사가 통과되면 새 버전 출시 여부를 best-effort 로 확인한다. 실패는 침묵; 알림은 부가 기능이지 등록 흐름을 막지 않는다. 같은 세션에서 이미 한 번 안내가 출력됐으면 재호출하지 않는다.

**실행 방법** (Bash 도구로 1회):

```bash
SCRIPT=$(ls -d "$HOME"/.claude/plugins/cache/*/claude-jira-task/*/scripts/version_check.py 2>/dev/null | sort -V | tail -1)
[ -n "$SCRIPT" ] && python3 "$SCRIPT" 2>/dev/null
```

**출력 처리**
- stdout 에 한 줄이 출력되면 (예: `📦 claude-jira-task v0.1.5 사용 가능 (현재 v0.1.4)`) 그 줄을 사용자에게 그대로 한 번 보여주고 등록 흐름으로 진행.
- 출력이 없으면 (최신이거나 비교 불가) 침묵 진행.

**동작 요약** (스크립트 내부 — 참고용)
- 로컬 버전: `~/.claude/plugins/cache/*/claude-jira-task/<VERSION>/` 중 최고 버전.
- 원격 버전: `~/.claude/plugins/marketplaces/*/` 중 manifest 의 `name == "claude-jira-task"` 인 디렉토리에서 `git fetch origin` 후 `origin/main:.claude-plugin/plugin.json` 의 version.
- 결과는 `~/.cache/claude-jira-task/version-check.json` 에 24h TTL 캐시 — 매 호출마다 fetch 안 함.

---

## 핵심 원칙

1. **모든 산출물 있는 작업은 Jira 에 등록한다.** "등록할까요?" 라고 묻지 않는다 — 산출물이 발생하는 작업이면 바로 등록 절차로 진입한다. (예외는 산출물 없는 대화 — Safety net 섹션 참고)
2. **등록은 항상 `/jira-task` 슬래시 명령으로만 일어난다.** Claude 가 임의로 `createJiraIssue` 를 호출하지 않는다.
3. **사용자 승인은 등록 메타 정보(이슈 타입 · 요약 · 상세 · Epic · 라벨)에만 받는다.** "등록할지 말지" 는 묻지 않는다.
4. **자동 전이 확인 정책**
   - **이 세션에서 `/jira-task` 로 새로 등록한 task**: 첫 전이를 **묻지 않고 바로 자동 전이**. (등록 절차에서 이미 사용자 의사 표시 완료)
   - **이전 세션에서 이어진 활성 task**: 그 세션의 첫 자동 전이 직전에 한 번만 확인. 동의하면 이후 동일 세션에선 추가 확인 없음.

---

## 기본 컨텍스트

| 항목 | 값 |
|---|---|
| Atlassian 사이트 | `mcp__atlassian__getAccessibleAtlassianResources` 로 확인) |
| cloudId | `c223af3a-a533-4a18-a1af-c852a53c8fc8` (조직별 변경 가능 — 동일 도구로 확인) |
| 기본 프로젝트 키 | **repo 별로 결정** — 각 repo 의 `.claude/jira-config.json` 에 저장. 처음 호출 시 1회 선택. 자세한 절차는 아래 "기본 프로젝트 결정" 참고 |
| 기본 assignee | **현재 Atlassian 에 로그인된 계정** — 세션 시작 시 `mcp__atlassian__atlassianUserInfo` 로 한 번 조회해 캐시 |
| 기본 이슈 타입 | **고정하지 않음 — 등록 직전에 사용자에게 선택받는다** |

프로젝트의 이슈 타입: Epic / Story / Task / Sub-task / Bug / 인프라.
다른 프로젝트는 그 repo 의 `default_project_key` 로 지정된 경우 자동 사용.

---

## 기본 프로젝트 결정

`/jira-task` 가 호출되면 가장 먼저 그 repo 의 기본 Jira 프로젝트를 결정한다. **저장 단위는 repo (working directory)** 다 — 같은 repo 에서는 한 번만 묻고, 다른 repo 로 이동하면 다시 처음 1회 묻는다.

**저장 위치**

```
<repo 루트>/.claude/jira-config.json
```

스키마:
```json
{
  "default_project_key": "<your-project-key>"
}
```

> 이 파일은 **gitignore 권장** — 팀원마다 다른 프로젝트를 default 로 둘 수 있으므로 (예: 프론트 담당자는 `WEBRTC`).

**결정 로직**

```
① <cwd 의 git repo 루트>/.claude/jira-config.json 의 default_project_key 가 있으면 → 그것 사용
② 없으면 → "맨 처음" → 아래 선택 흐름 발동
```

**선택 흐름 ("맨 처음")**

1. `mcp__atlassian__getVisibleJiraProjects` 로 사용자가 접근 가능한 프로젝트 목록 조회 (`fields: key, name`).
2. `AskUserQuestion` 으로 선택받음. **label 은 `<프로젝트 이름> (<KEY>)` 형식** 으로 키와 이름을 함께 노출 — Epic 표시 규칙과 동일한 원칙(이름 우선, 키는 보조).
   - 예시 라벨:
     ```
     ○ Server 백엔드 (TASK)
     ○ WebRTC 미디어 (WEBRTC)
     ○ Mix & Pop (MIXPOP)
     ```
   - 목록이 4개를 넘으면 최근 활동 순(`ORDER BY updated DESC` 가능한 별도 JQL 또는 alphabetical) 으로 상위 3개 + "기타 (직접 입력)" 옵션을 둠.
3. 사용자가 선택하면 `<repo>/.claude/jira-config.json` 에 `default_project_key` 를 저장 후 등록 절차 step 1 로 진입.

**재설정 / 변경**

- 한 번 잘못 골랐거나 repo 가 다른 프로젝트로 이관됐을 때:
  - `/jira-task config reset` → `.claude/jira-config.json` 의 `default_project_key` 제거. 다음 `/jira-task` 호출 시 다시 선택 흐름 발동.
  - `/jira-task config set <KEY>` → 키만 즉시 덮어쓰기 (선택 흐름 건너뜀).

---

## 등록 절차 — `/jira-task` 명령어

사용자가 `/jira-task [요약]` 을 호출하면 Claude 는 `AskUserQuestion` 으로 다음을 순서대로 묻는다.

1. **이슈 타입** — Task / Story / Bug / 인프라 / Epic
2. **요약(Summary)** — 인자가 있으면 그것을 기반 초안, 없으면 직전 대화 맥락으로 초안 제안 → 사용자 승인
3. **상세(Description)** — 작업 배경 · 입력 · 예상 산출물 초안을 만들어 보여주고 승인
4. **Assignee** — 기본은 **현재 로그인된 Atlassian 계정** (`mcp__atlassian__atlassianUserInfo` 로 조회, 세션 내 캐시). 변경 의사 확인.
5. **Epic 연결** — 현재 살아 있는 Epic 목록을 JQL 로 조회해 보여줌. **옵션에 `(none) — Epic 연결 안 함` 포함**
   - 조회: `searchJiraIssuesUsingJql` 로 `project = <KEY> AND issuetype = Epic AND statusCategory != Done ORDER BY updated DESC` (fields: `summary,status`)
   - **표시 형식**: 사용자가 Epic 이름으로 구분할 수 있어야 한다.
     - `AskUserQuestion` 의 `label` 은 **Epic summary (이름)** 로 표시 — 키는 노출하지 않거나, 노출하더라도 보조로만.
     - 예시 라벨: `메인 캐릭터 동기화 파이프라인 정비`
     - `description` 필드에 `TASK-2046 · In Progress` 같은 형식으로 키와 status 를 보조 정보로 같이 보여준다.
     - summary 가 너무 길어 가독성을 크게 초과하면 앞 30자 + `…` 으로 잘라 label 에 넣고, 전체 summary 를 description 으로 옮긴다.
     - 내부적으로 사용자의 선택을 Epic 키로 매핑할 때는 `(label → key)` 사전을 미리 만들어 둔다 (라벨 중복 가능성에 대비).
6. **Labels** — 사용 중인 label 집합을 조회해 보여줌. **옵션에 `(none) — 라벨 없음` 포함**. 다중 선택 허용. 목록에 없는 새 라벨은 사용자가 명시한 경우만 추가
   - 조회: 최근 이슈들의 `labels` 필드를 모아 중복 제거
7. **작업 격리 방식** — 이 task 를 어디서 작업할지 선택. 두 옵션 모두 새 브랜치(`<type>/<JIRA-KEY>-<slug>`)는 동일하게 생성하고, **분리되는 건 디렉토리뿐**이다.
   - **`별도 worktree (Recommended)`** — sibling 경로(`<repo>-<KEY>`)에 새 git worktree 생성. 다른 task 와 동시에 진행해도 파일/빌드/dev server 가 섞이지 않음. backend·에이전트 작업 기본값.
   - **`현재 디렉토리에서 작업`** — worktree 를 만들지 않고 현재 위치에서 `git checkout -b <branch>` 만 수행. 이미 떠 있는 dev server / IDE / 브라우저 / `node_modules` 캐시를 그대로 재사용. 프론트엔드 작업처럼 핫리로드·미리보기 컨텍스트가 중요한 경우 권장. **트레이드오프**: 같은 디렉토리에서 동시에 두 task 를 띄울 수 없으므로, 다른 활성 task 의 브랜치를 점유 중이라면 그쪽 변경을 먼저 커밋/stash 한 후 진행해야 한다.

승인이 모두 끝나면 `mcp__atlassian__createJiraIssue` 로 생성하고, **이슈 키를 활성 task 목록에 추가** (이때 `auto_transition_confirmed: true` 도 같이 기록 — 신규 등록 task 는 이후 자동 전이를 확인 없이 진행) 한 뒤 사용자에게 이슈 키 + Jira URL + 격리 방식 + 현재 활성 task 목록을 알려준다.

격리 방식의 실제 수행은 아래 "작업 격리 — worktree / 현재 디렉토리" 섹션을 따른다.

---

## 활성 task 관리

한 세션에서 여러 task 가 동시에 활성 상태일 수 있다.

**저장 위치**: 프로젝트 루트의 `.claude/active-jira-tasks.json` (per-project). 파일이 없으면 슬래시 명령이 만든다.

**파일 스키마 (예시)**
```json
{
  "tasks": [
    {
      "key": "TASK-123",
      "summary": "...",
      "status": "In Progress",
      "branch": "feature/TASK-123-...",
      "worktree_path": "/path/to/<current-repo>-TASK-123",
      "registered_at": "2026-05-15T14:30:00Z",
      "auto_transition_confirmed": true
    },
    {
      "key": "TASK-124",
      "summary": "...",
      "status": "In Progress",
      "branch": "fix/TASK-124-...",
      "worktree_path": "",
      "registered_at": "2026-05-15T15:10:00Z",
      "auto_transition_confirmed": true
    }
  ]
}
```

`worktree_path` 가 **빈 문자열이거나 누락**되어 있으면 그 task 는 "현재 디렉토리" 모드로 등록된 것이다. 별도 `mode` 필드는 두지 않는다.

**서브 명령 (모두 `/jira-task` 로 호출)**
| 호출 | 의미 |
|---|---|
| `/jira-task <요약>` 또는 `/jira-task` | 신규 등록 |
| `/jira-task list` | 현재 활성 task 목록 출력 |
| `/jira-task switch <KEY>` | 작업 컨텍스트를 해당 이슈로 전환 (해당 이슈가 활성에 없으면 추가) |
| `/jira-task deactivate <KEY>` | 활성 목록에서만 제거 (Jira 이슈는 그대로) |
| `/jira-task config reset` | 현재 repo 의 `default_project_key` 제거 — 다음 호출 시 다시 선택 |
| `/jira-task config set <KEY>` | 현재 repo 의 `default_project_key` 를 즉시 덮어쓰기 |

활성 task 가 여러 개일 때 어떤 작업이 어느 task 에 속하는지는 **현재 git 브랜치 이름** 으로 판정한다 (아래 "커밋/PR 연결" 참고). 브랜치 매칭이 안 되면 사용자에게 묻는다.

---

## 작업 격리 — worktree / 현재 디렉토리

Jira task 단위로 작업을 격리한다. 격리 방식은 등록 절차 step 7 에서 사용자가 선택한 결과를 따른다 — **별도 worktree** 또는 **현재 디렉토리**. 어느 쪽이든 새 브랜치(`<type>/<JIRA-KEY>-<slug>`) 는 항상 생성한다.

**생성 시점**

| 트리거 | 동작 |
|---|---|
| `/jira-task` 신규 등록 (사용자 직접 호출) | step 7 선택에 따라 worktree 생성 **또는** 현재 디렉토리에 브랜치만 생성. 어느 쪽이든 후속 작업은 그 위치 · 새 브랜치에서 진행 |
| Safety net 발동 후 자동 등록 | 동일 — step 7 까지 모두 묻는다. 단, 산출물(stash 필요)이 이미 떠 있는 경우는 아래 "Edge case" 참고 |
| `/jira-task switch <KEY>` | active-jira-tasks.json 의 `worktree_path` 가 있으면 그쪽으로 전환, 비어 있으면 현재 디렉토리에서 `git checkout <branch>` |
| 정보 조회·질문 답변·디버깅 상담 (산출물 없음) | 아무것도 만들지 않음 — 그 자체로 Jira 등록 대상도 아님 |

**공통 브랜치 규칙**

- 브랜치 이름: `<type>/<JIRA-KEY>-<slug>` (예: `feature/TASK-123-jira-workflow`, `fix/TASK-456-image-upload`)
- 어느 모드든 브랜치 이름이 활성 task 와 커밋/Hook 을 연결하는 단일 키. PreToolUse hook 도 이 이름만 본다.

### 모드 A — 별도 worktree (기본)

- 경로: `<현재 repo 부모>/<repo 이름>-<JIRA-KEY>` (sibling 형태)
  - 예: 메인이 `<parent>/<current-repo>/` → worktree 는 `<parent>/<current-repo>-TASK-123/` (Windows · macOS · Linux 동일)
- 명령:
  ```
  git worktree add ../<repo>-<JIRA-KEY> -b <type>/<JIRA-KEY>-<slug>
  ```
- active-jira-tasks.json 에 `worktree_path` 를 절대경로로 저장.
- **환경 / 캐시 안내** — worktree 생성 직후 사용자에게: "`.env` · Python venv · `node_modules` · Docker 볼륨 등은 worktree 마다 새로 세팅이 필요합니다. 프론트엔드 dev server 도 새로 띄워야 합니다."
- **충돌 회피** — 같은 브랜치를 두 worktree 가 동시에 체크아웃할 수 없다. `git worktree add` 가 거부하면 기존 worktree 위치를 사용자에게 알리고 그쪽으로 전환 제안. 동일 task 키로 worktree 가 이미 존재하면 새로 만들지 않고 그쪽으로 컨텍스트 전환.

### 모드 B — 현재 디렉토리

- worktree 를 만들지 않는다. 현재 cwd 에서 `git checkout -b <type>/<JIRA-KEY>-<slug>` 만 수행.
- 이미 떠 있는 변경(staged·unstaged)은 자연스럽게 새 브랜치로 따라간다 — stash 가 필요 없다.
- active-jira-tasks.json 의 `worktree_path` 는 빈 문자열로 저장.
- **언제 권장**: 프론트엔드 작업(dev server hot reload, 브라우저 미리보기, IDE 인덱스 재사용), 로컬 환경 파일(`.env.local`)에 의존하는 디버깅, 한 사람이 한 번에 한 가지 task 만 진행하는 경우.
- **충돌 회피** — 이미 다른 활성 task 의 브랜치가 현재 디렉토리에 체크아웃돼 있고 그 브랜치에 커밋 안 된 변경이 떠 있으면, `git checkout -b` 가 안전한지 먼저 확인한다 (충돌 가능성이 있으면 사용자에게 "현재 변경을 어떻게 처리할까요? — 커밋 / stash / 취소" 를 물음).
- **두 모드 혼용** — 한 repo 안에서 task A 는 worktree, task B 는 현재 디렉토리로 등록될 수 있다. 단, 같은 시점에 같은 디렉토리에서는 한 task 의 브랜치만 체크아웃 가능하므로 모드 B 의 task 들은 순차적으로만 작업된다.

### 정리 · 삭제

- `/jira-task deactivate <KEY>` 또는 task 가 `Closed` 로 전이될 때 **자동 삭제 안 함**.
- `worktree_path` 가 비어 있는 task: 활성 목록에서만 제거하면 끝. 별도 정리 질문 없음.
- `worktree_path` 가 채워진 task: 한 번 묻는다 — "이 task 의 worktree(`<경로>`) 정리할까요? (Y/keep)". `Y` 면 `git worktree remove <경로>` + `git worktree prune`.

### Edge case — 변경이 떠 있는 상태에서 task 가 뒤늦게 등록되는 경우

작업 시작 시점 safety net 이 누락되어 (예: 한 줄 수정인 줄 알았는데 점점 커진 경우) **커밋 시점에야 task 가 등록되는 상황**에서는, main(또는 임의 브랜치)에 staged·unstaged 변경이 떠 있다. 등록 절차 step 7 에서 선택한 모드에 따라 처리가 갈린다.

**모드 A (별도 worktree) 선택 시** — 일관성을 위해 변경을 새 worktree 로 옮긴다:

```
git stash push -u -m "auto: move to <KEY> worktree"
git worktree add ../<repo>-<KEY> -b <type>/<KEY>-<slug>
cd ../<repo>-<KEY>
git stash pop
```

이후 새 worktree 에서 `[<KEY>] ...` prefix 로 커밋. 원래 위치(main 등)는 깨끗한 상태로 복구된다. `stash pop` 시 충돌이 나면 작업을 멈추고 사용자에게 보고.

**모드 B (현재 디렉토리) 선택 시** — 떠 있는 변경을 그대로 새 브랜치로 가져간다:

```
git checkout -b <type>/<KEY>-<slug>
```

`git checkout -b` 는 워킹트리 변경을 보존한 채 브랜치만 새로 만들므로 stash 가 필요 없다. 이후 동일 위치에서 `[<KEY>] ...` prefix 로 커밋.

---

## 커밋/PR 연결

활성 task 와 작업 산출물(커밋, PR) 의 연결은 두 가지를 **모두** 적용한다.

1. **브랜치 이름 규칙**: `<type>/<JIRA-KEY>-<slug>` 형식 (예: `feature/TASK-123-jira-workflow`, `fix/TASK-456-image-upload`).
2. **커밋 메시지 prefix**: 모든 커밋 제목 앞에 `[<JIRA-KEY>]` 를 붙인다. PR 제목도 동일.
   - 예: `[TASK-123] Add jira-task slash command`
   - 여러 task 가 한 커밋에 묶일 수 있으면 `[TASK-123][TASK-456]` 처럼 나열.

**연결 판정 로직** (자동 전이 / safety net 에서 사용)
- 현재 브랜치 이름에 `<프로젝트키>-N` 패턴이 포함되면 그 키를 활성 task 로 본다.
- 그 키가 활성 task 목록에 없으면 Safety net 발동 (아래).

---

## 자동 상태 전이

상태 흐름:
```
Open (To Do)  →  In Progress  →  Resolved  →  Closed
```

> 위 상태 흐름은 Jira 기본 워크플로 기준. 프로젝트마다 워크플로 정의가 다를 수 있으므로 `mcp__atlassian__getTransitionsForJiraIssue` 로 해당 이슈에서 가용한 transition 을 확인 후 적용.

전이 규칙:

| 트리거 | 전이 | 자동 여부 |
|---|---|---|
| 활성 task 의 브랜치에서 첫 파일 편집/Bash 명령 실행 | `Open` → `In Progress` | **자동** (이번 세션에서 새로 등록된 task 는 확인 없이 바로 전이 / 이전 세션 이어진 task 는 세션 첫 1회만 확인) |
| 활성 task 와 연결된 커밋 또는 PR 생성 | `In Progress` → `Resolved` | **자동** (동일 정책) |
| 검증 통과 / 작업 완료 판단 | `Resolved` → `Closed` | **사용자 명시 승인 필수** |
| 되돌리기 (예: `Resolved` → `In Progress`) | 역방향 | **사용자 명시 승인 필수** |

**자동 전이 확인 — 두 경로**

*경로 A — 이번 세션에서 `/jira-task` 로 신규 등록한 task*
- `/jira-task` 등록 직후 active-jira-tasks.json 의 해당 task 항목에 `auto_transition_confirmed: true` 를 즉시 기록한다.
- 첫 전이를 **확인 없이 바로 실행**. (등록 자체가 이미 사용자 의사 표시)

*경로 B — 이전 세션에서 이어진 활성 task*
- 그 세션의 첫 자동 전이가 일어나기 직전에 한 번:
  > "`TASK-123` 을 자동으로 `In Progress` 로 옮기겠습니다. 이 세션에서 이후 자동 전이도 별도 확인 없이 진행할까요?"
- 사용자가 동의하면 `auto_transition_confirmed: true` 를 기록하고, 이후 동일 세션에서는 추가 확인 없이 전이.
- 사용자가 거부하면 그 세션은 전이마다 묻는 모드로 전환.

---

## Safety net — 미등록 작업 회수

활성 task 없이 다음 중 하나가 발생하면 Claude 는 즉시 작업을 멈추고 사용자에게 등록 의사를 묻는다.

| 상황 | 조치 |
|---|---|
| 파일 편집/Bash 명령으로 실제 작업이 시작됨, 활성 task 없음 | 즉시 `/jira-task` 등록 절차로 진입 (이슈 타입·요약·상세·격리 방식 등 메타만 사용자 승인). 등록 후 선택한 모드대로 worktree 생성 또는 현재 디렉토리에 브랜치 생성 (위 "작업 격리 — worktree / 현재 디렉토리" 참고) → `In Progress` 자동 전이 |
| 커밋/PR 이 생성되려는 시점, 활성 task 없음 또는 브랜치-task 매칭 실패 | 즉시 `/jira-task` 등록 절차로 진입 → 모드 A 면 stash 후 새 worktree 로 이동, 모드 B 면 현재 위치에서 `git checkout -b` (위 "작업 격리 § Edge case" 참고) → 새 브랜치에서 `[<KEY>] ...` prefix 커밋 → `Resolved` 자동 전이 |
| 활성 task 가 여러 개인데 어느 것에 속하는지 모호 | 후보 키 목록을 보여주고 사용자가 선택 |

**예외 (Safety net 발동 안 함)**
- 정보 조회·질문 답변·디버깅 상담처럼 **산출물 없이 끝나는 대화**. (코드·문서 변경, 커밋, 빌드·배포 명령 등 산출물이 발생하면 무조건 등록 대상)

---

## PreToolUse Hook — 커밋 게이트

이 플러그인은 `hooks/hooks.json` 에 등록된 `PreToolUse` 훅으로 **Claude 가 `git commit` Bash 명령을 호출하는 시점**에 자동 게이트를 건다. 작동 흐름:

1. Claude 가 Bash 로 `git commit ...` 실행 시도
2. Hook 스크립트 (`hooks/pretooluse_jira_check.py`) 가 다음을 검사:
   - 현재 repo 에 `.claude/jira-config.json` 이 있는가? (없으면 opt-out 으로 간주 → 통과)
   - 현재 git 브랜치 이름에 `.claude/active-jira-tasks.json` 의 어떤 활성 task `key` 가 포함되는가?
3. 매칭되면 통과. 아니면 exit code 2 + stderr 메시지로 **커밋 차단**.

Claude 가 이 차단 메시지를 받으면 **즉시 `/jira-task` 등록 절차로 진입**한다 (위 Safety net 흐름 동일). 등록 → worktree 이동 (stash 포함) → 새 worktree 에서 다시 `git commit`. 두 번째 시도에서는 hook 이 통과시킨다.

**한계**: Claude Code 외부 터미널·IDE 에서 직접 `git commit` 하는 경우는 hook 이 발동되지 않는다. 그것까지 막으려면 각 repo 의 `.git/hooks/pre-commit` 별도 설정이 필요 — 이 플러그인 범위 밖.

---

## 사용할 MCP 도구

| 용도 | 도구 |
|---|---|
| cloudId 조회 | `mcp__atlassian__getAccessibleAtlassianResources` |
| 프로젝트 / 이슈 타입 메타 | `mcp__atlassian__getVisibleJiraProjects`, `mcp__atlassian__getJiraProjectIssueTypesMetadata`, `mcp__atlassian__getJiraIssueTypeMetaWithFields` |
| Epic / 라벨 / 중복 검색 | `mcp__atlassian__searchJiraIssuesUsingJql` |
| 이슈 생성 | `mcp__atlassian__createJiraIssue` |
| 이슈 수정 | `mcp__atlassian__editJiraIssue` |
| 코멘트 | `mcp__atlassian__addCommentToJiraIssue` |
| 상태 전이 | `mcp__atlassian__getTransitionsForJiraIssue` → `mcp__atlassian__transitionJiraIssue` |
| 현재 로그인 사용자 정보 (기본 assignee) | `mcp__atlassian__atlassianUserInfo` |
| 임의 사용자 accountId 조회 (assignee 변경 시) | `mcp__atlassian__lookupJiraAccountId` |

---

## TodoWrite 와의 관계

- TodoWrite 는 세션 내 진행 관리용. Jira 와 별개로 자유롭게 사용한다.
- TodoWrite 항목이 활성 task 와 관련되면 본문 끝에 `(TASK-123)` 를 덧붙여 추적한다.
- TodoWrite 항목이 `completed` 로 바뀌어도 Jira 이슈는 자동으로 `Closed` 로 가지 않는다 — `Closed` 전이는 별도 사용자 승인.

---

## 금지 / 주의

- `Closed` 로 자동 전이 금지.
- Claude 가 임의로 새 라벨을 만들지 않는다 (사용자가 신규 라벨을 명시한 경우에만).
- 커밋/PR 의 prefix 누락 금지. 사용자가 prefix 없이 커밋하라고 명시한 경우만 예외.
- 한 번에 여러 티켓이 필요하면 묶음으로 보여주고 **단일 승인** 으로 처리 (티켓마다 따로 묻지 않음).
