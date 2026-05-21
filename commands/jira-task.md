---
description: Jira task 등록·전환·자동 상태 전이 + task 별 작업 격리(worktree 또는 현재 디렉토리 선택)
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion, Skill, mcp__atlassian__atlassianUserInfo, mcp__atlassian__getAccessibleAtlassianResources, mcp__atlassian__getVisibleJiraProjects, mcp__atlassian__getJiraProjectIssueTypesMetadata, mcp__atlassian__getJiraIssueTypeMetaWithFields, mcp__atlassian__searchJiraIssuesUsingJql, mcp__atlassian__createJiraIssue, mcp__atlassian__editJiraIssue, mcp__atlassian__addCommentToJiraIssue, mcp__atlassian__getTransitionsForJiraIssue, mcp__atlassian__transitionJiraIssue, mcp__atlassian__lookupJiraAccountId, mcp__atlassian__getJiraIssue
argument-hint: "[요약] 또는 list / switch <KEY> / deactivate <KEY> / config reset / config set <KEY>"
---

`jira-task` 스킬을 호출해서 Jira task 등록·전환·상태 전이·작업 격리(worktree 또는 현재 디렉토리)를 처리한다.

사용자 인자: $ARGUMENTS

분기:
- 인자가 비어 있거나 요약 텍스트로 시작 → 신규 등록 흐름 (필요 시 `default_project_key` 결정 흐름부터, 끝에서 격리 방식도 함께 선택)
- `list` → 활성 task 목록 출력 (각 task 의 격리 방식 포함)
- `switch <KEY>` → 작업 컨텍스트 전환 (worktree 모드면 그 디렉토리로, 현재 디렉토리 모드면 그 브랜치로 체크아웃)
- `deactivate <KEY>` → 활성 목록에서 제거 (Jira 이슈는 그대로 · worktree 가 있으면 정리 여부 한 번 확인)
- `config reset` → 현재 repo 의 `.claude/jira-config.json` 의 `default_project_key` 제거
- `config set <KEY>` → 현재 repo 의 `default_project_key` 즉시 덮어쓰기

자세한 절차는 `jira-task` 스킬 본문을 따른다.
