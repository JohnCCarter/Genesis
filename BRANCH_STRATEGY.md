# Branch Strategy for AI Agent Collaboration

## Overview

This document outlines the branch strategy for safe AI agent collaboration between Cursor AI and Codex Agent.

## Branch Structure

### `main` Branch

- **Purpose**: Production-ready, stable code
- **Protection**: Only merged code from experimental branches
- **Who can modify**: Human review required for all changes
- **Status**: Protected, stable

### `ai-agents-experimental` Branch

- **Purpose**: AI agent experimentation and collaboration
- **Protection**: Free for AI agents to modify
- **Who can modify**: Cursor AI, Codex Agent, and humans
- **Status**: Active development, experimental features

## Workflow

### 1. AI Agent Development

```
ai-agents-experimental (current)
├── Cursor AI: Backend development
├── Codex Agent: Frontend development
└── Human: Review and merge to main
```

### 2. Safe Experimentation

- AI agents can freely modify `ai-agents-experimental`
- Use file locking system to prevent conflicts
- Use communication system for coordination
- Test all changes before merging to main

### 3. Merge to Main

- Human review required
- All tests must pass
- Documentation updated
- Stable and tested features only

## AI Agent Coordination

### File Locking

```powershell
# Lock files before editing
.\scripts\agent_lock.ps1 lock -Path "tradingbot-backend/main.py" -By "Cursor" -Reason "Backend optimization"

# Unlock after editing
.\scripts\agent_lock.ps1 unlock -Path "tradingbot-backend/main.py" -By "Cursor"
```

### Communication

```powershell
# Send messages between agents
.\scripts\agent_communication.ps1 send -Message "Implementing new feature" -To "Codex" -From "Cursor" -Priority "normal" -Context "backend development"

# Read messages
.\scripts\agent_communication.ps1 read -From "Cursor"
```

### Status Monitoring

```powershell
# Check agent status
.\scripts\agent_communication.ps1 status
```

## Safety Measures

### 1. Branch Protection

- `main` branch is protected
- No direct commits to main
- All changes go through experimental branch

### 2. File Locking

- Prevents concurrent modifications
- Clear ownership of files
- Automatic timeout for stale locks

### 3. Communication System

- Real-time coordination
- Priority-based messaging
- Context-aware communication

### 4. Rollback Capability

- Easy to revert experimental changes
- Main branch always stable
- Clear separation of concerns

## Best Practices

### For AI Agents

1. Always work on `ai-agents-experimental` branch
2. Use file locking before editing
3. Communicate changes to other agents
4. Test thoroughly before requesting merge
5. Document all changes

### For Humans

1. Review all changes before merging to main
2. Run full test suite
3. Ensure documentation is updated
4. Merge only stable, tested features

## Emergency Procedures

### If Main Branch is Broken

1. Revert to last known good commit
2. Investigate issue in experimental branch
3. Fix and test thoroughly
4. Merge only after verification

### If AI Agents Conflict

1. Check file locks
2. Use communication system to resolve
3. Human intervention if needed
4. Clear locks and restart if necessary

## Monitoring

### Branch Status

- Regular status checks
- Monitor for conflicts
- Track development progress
- Ensure main branch stability

### Agent Activity

- Monitor file locks
- Track communication
- Review changes
- Ensure coordination

## Conclusion

This branch strategy provides:

- Safe experimentation for AI agents
- Protection for production code
- Clear coordination mechanisms
- Easy rollback capabilities
- Human oversight and control

The system allows AI agents to work freely while maintaining code quality and stability.
