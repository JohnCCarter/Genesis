Agent Plan and Coordination

Status
- Focus: AI Agent Communication System
- Owners: Cursor (backend core), Codex (frontend & config)
- Communication: Direct messaging system implemented

Ground rules
- Always lock files before editing (see `.cursorrules`).
- Use communication system for coordination.
- Keep PR/commit scope tight; no unrelated refactors.
- Never modify local `.env` files or secrets.

Active tasks
1) Add `.cursorrules` with lock policy (Done)
2) Add PowerShell lock helper (Done)
3) Add `.gitignore` entry for `.agent-locks/` (Done)
4) Add AI communication system (Done)

Communication system
- Send: `.\scripts\agent_communication.ps1 send -Message "Hello" -To "Codex" -From "Cursor" -Priority "high" -Context "trading optimization"`
- Read: `.\scripts\agent_communication.ps1 read -From "Cursor"`
- Status: `.\scripts\agent_communication.ps1 status`
- Clear: `.\scripts\agent_communication.ps1 clear`

Lock usage examples
- Lock: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/agent_lock.ps1 lock -Path "scripts/start_normal.ps1" -By "Codex" -Reason "Edit start flow"`
- Unlock: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/agent_lock.ps1 unlock -Path "scripts/start_normal.ps1" -By "Codex"`
- Status: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/agent_lock.ps1 status`

Notes
- If a lock is older than the TTL and clearly stale, unlock with `-Force` and leave a short note in the next commit message.
- Use communication system for real-time coordination between agents.
