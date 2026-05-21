# claude-jira-task

Claude Code 안에서 **Jira 등록 · 상태 전이 · 작업 격리(worktree 또는 현재 디렉토리 선택)** 를 한 워크플로로 묶은 플러그인.

## 핵심 기능

| 기능 | 동작 |
|---|---|
| `/jira-task <요약>` | 새 Jira 이슈 등록 (이슈 타입·요약·상세·assignee·Epic·라벨·격리 방식을 순차 확인) |
| repo 단위 default project | 새 repo 의 첫 호출 시점에 한 번만 묻고 `.claude/jira-config.json` 에 저장 |
| 강제 등록 | 산출물 있는 작업이면 "등록할까요?" 묻지 않고 바로 등록 절차 진입 |
| 자동 상태 전이 | 편집/Bash → `In Progress`, 커밋/PR → `Resolved` 자동 전이 (Closed 만 수동) |
| 작업 격리 (등록 시 선택) | **별도 worktree** (sibling 경로 `<repo>-<KEY>`, 다중 task 동시 진행 안전) 또는 **현재 디렉토리** (dev server / IDE / 브라우저 컨텍스트 재사용 — 프론트엔드 작업 권장) 중 선택. 어느 쪽이든 새 브랜치는 동일 |
| 활성 task 추적 | `.claude/active-jira-tasks.json` 에 다중 task 상태 보관 (`worktree_path` 가 비어 있으면 현재 디렉토리 모드) |
| 버전 알림 | `/jira-task` 첫 호출 시 marketplace 의 origin/main 과 로컬 설치 버전을 비교해 새 버전 있으면 한 줄 안내 (24h 캐시, best-effort, 실패 시 침묵) |

## 의존성

| 항목 | 요구 | 비고 |
|---|---|---|
| **Claude Code** | ≥ 플러그인 시스템 지원 버전 | 모든 OS |
| **Atlassian MCP server** | Anthropic 공식 Atlassian Remote MCP | 아래 [Atlassian MCP 설치](#atlassian-mcp-설치) 참고. 미설치 시 `/jira-task` 첫 호출 때 안내가 자동으로 뜸 |
| **git** | ≥ 2.5 | worktree 사용 |
| **bash** | 모든 OS — Linux/macOS 는 기본, Windows 는 Git Bash 로 충족 | Hook wrapper 가 bash 로 동작 |
| **Python** | 3.x (`python3` 또는 `python` 어느 쪽이든 PATH 에 있으면 OK) | Hook 스크립트 실행. 없으면 hook 만 비활성(skill 본문은 그대로 동작) |

### Atlassian MCP 설치

```
claude mcp add --transport http atlassian https://mcp.atlassian.com/v1/mcp
```

설치 후 Claude Code 를 재시작하면 OAuth 인증 화면이 나옴. 인증 완료까지 한 번만 필요.

공식 가이드: https://support.atlassian.com/atlassian-rovo-mcp-server/docs/getting-started-with-the-atlassian-remote-mcp-server/

> Plugin 설치 후 `/jira-task` 를 호출했을 때 MCP 가 없으면 위 안내가 자동으로 출력되어 등록 흐름이 중단됩니다 — 그 시점에 위 명령을 실행해도 됩니다.

## 설치

```
/plugin marketplace add <this-repo-url>
/plugin install <plugin-name>
```

설치 후 Claude Code 를 재시작하면 `/jira-task` 슬래시 명령이 활성화된다.

## 첫 사용

새 repo 폴더 안에서:

```
/jira-task 로그인 화면 OAuth 버그 수정
```

첫 호출이면 다음 흐름이 자동으로 진행된다:

1. 사용 가능한 Jira 프로젝트 목록에서 default 선택 → `.claude/jira-config.json` 에 저장
2. 이슈 타입 / 요약 / 상세 / assignee / Epic / 라벨 / **격리 방식** 차례로 승인
3. `mcp__atlassian__createJiraIssue` 로 등록
4. 격리 방식에 따라 분기 — **별도 worktree** 선택 시 sibling worktree(`<repo>-<KEY>`) 자동 생성 + 그 안으로 컨텍스트 이동 / **현재 디렉토리** 선택 시 cwd 에서 `git checkout -b <type>/<KEY>-<slug>` 만 수행
5. 첫 파일 편집 시 `In Progress` 자동 전이

이후 동일 repo 에서는 default project 를 다시 묻지 않는다.

### 언제 어떤 격리 방식을 고를까

| 상황 | 권장 |
|---|---|
| Backend · 에이전트 · 라이브러리 작업, 동시에 여러 task 진행 가능 | **별도 worktree** (기본) |
| Frontend 작업 — dev server 핫리로드, 브라우저 미리보기, IDE 인덱스 재사용이 중요 | **현재 디렉토리** |
| 한 사람이 한 번에 한 가지 task 만 다룸 | **현재 디렉토리** 가 더 가벼움 |
| `.env.local` / Docker 볼륨 / `node_modules` 등 로컬 캐시 의존 큰 작업 | **현재 디렉토리** (worktree 는 매번 새로 깔아야 함) |

## 소비 repo 의 권장 `.gitignore`

이 플러그인이 만드는 두 파일은 **로컬 개인 상태** 라 git 에 올리지 말 것:

```gitignore
# Claude Code — claude-jira-task plugin 의 로컬 상태
.claude/active-jira-tasks.json
.claude/jira-config.json
```

(Claude Code 의 다른 개인 설정 `.claude/settings.local.json` 도 같이 무시 권장.)

## 서브 명령 요약

| 호출 | 의미 |
|---|---|
| `/jira-task <요약>` | 신규 등록 |
| `/jira-task list` | 현재 활성 task 목록 |
| `/jira-task switch <KEY>` | 작업 컨텍스트 전환 (worktree 동반) |
| `/jira-task deactivate <KEY>` | 활성 목록에서 제거 (Jira 이슈는 그대로) |
| `/jira-task config reset` | 이 repo 의 default project 제거 — 다음 호출에 다시 선택 |
| `/jira-task config set <KEY>` | 이 repo 의 default project 즉시 변경 |

자세한 워크플로 규칙은 `skills/jira-task/SKILL.md` 본문 참고.

## Hook 동작 — git commit 게이트

플러그인은 `PreToolUse` hook 을 함께 등록합니다. Claude 가 `git commit` 을 실행하기 직전 다음을 검사:

1. 현재 repo 에 `.claude/jira-config.json` 이 있는가? (없으면 통과 — 워크플로 opt-out)
2. 현재 브랜치 이름에 활성 task 키(`TASK-123` 등) 가 포함되는가?

매칭 안 되면 hook 이 커밋을 차단하고 Claude 에게 "`/jira-task` 로 먼저 등록하세요" 메시지를 돌려줍니다. Claude 는 그 자리에서 등록 흐름으로 진입 → 새 worktree 에서 커밋을 다시 시도합니다.

**한계**: Claude Code 외부 터미널/IDE 에서 직접 `git commit` 하는 경우 hook 은 발동 안 됨. 그 케이스까지 차단하려면 각 repo 에 `.git/hooks/pre-commit` 별도 설정 필요.

## 변경 / 확장

워크플로 본문은 `skills/jira-task/SKILL.md` 에 있다. 팀 차원에서 규칙을 바꾸려면 그 파일을 수정해 PR.
