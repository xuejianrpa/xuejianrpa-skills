---
name: xuejian-redskill-rank
description: Query REDSkill ranking data for Xiaohongshu REDSkill rankings, hot skills, cumulative users, cumulative use counts, 7-day growth, daily new skills, author publishing rankings, keyword search, skill detail lookup, and exports. Use when the user asks for REDSkill data or fields such as skill_id, skill_name, skill_description, use_users, use_cnt, new7_cnt, cum_cnt, note_id, author_id, nickname, or skill_cnt. This skill uses a local client with built-in default access settings.
---

# Xuejian REDSkill Rank

Use this skill to query REDSkill ranking data with the bundled local client.

## Boundary

- The skill contains only the local query client.
- Use the bundled defaults; do not ask the user to configure access before querying.
- Do not print or explain the default access settings in user-facing answers.
- Keep answers focused on the ranking data and the metric used.

## Defaults

- No user setup is required for normal use.
- The client has built-in default access settings.
- Advanced overrides can exist in the environment or local config, but do not request them unless troubleshooting requires it.

## Local Cache

- The client uses a short local cache by default to reduce repeated requests.
- Default cache directory is chosen automatically by platform:
  - Windows: `D:\redskill-rank-cache` when the D drive exists.
  - macOS: `~/Library/Caches/redskill-rank`
  - Linux/Unix: `${XDG_CACHE_HOME}/redskill-rank` or `~/.cache/redskill-rank`
- Default cache lifetime: 600 seconds.
- Cache files contain query responses and expiry metadata. They do not contain access keys.
- Use `--refresh` to fetch fresh data and update the cache.
- Use `--no-cache` to skip cache for one run.
- Use `--cache-dir` or config key `cache_dir` to choose another local cache directory.
- Use `--cache-ttl` or config key `cache_ttl` to change the lifetime.

## Ranking Mapping

Use the official display meaning exactly:

- `useList`: usage-users ranking. Ranked by cumulative users, field `use_users`.
- `newList`: 7-day growth ranking. Ranked by 7-day use count growth, field `new7_cnt`.
- `todayList`: daily new skill ranking. Skills created on the data date, ranked by users, field `use_users`.
- `authorList`: author publishing ranking. Ranked by author skill count, field `skill_cnt`.
- `allSkills`: full searchable skill list. Fields are `skill_id`, `skill_name`, `skill_description`.

Do not call `use_cnt` "usage users"; it is cumulative use count. `use_users` is cumulative user count.

## Workflow

1. Run `python scripts/redskill_client.py summary` to confirm the configured data source is reachable and inspect `dataDate`, `genTime`, counts, and fields.
2. Run `top` for a ranking list, `search` for keyword lookup, or `detail` for one skill/note.
3. Include `dataDate` and `genTime` when reporting numbers.
4. If access fails, tell the user the local configuration is missing or incorrect. Do not guess credentials.
5. If exporting data, write files into the user's current project unless they request another path.

## Script Examples

From the skill directory:

```powershell
python .\scripts\redskill_client.py summary
python .\scripts\redskill_client.py top --list use --limit 20
python .\scripts\redskill_client.py top --list new --limit 20 --format csv --output D:\xuejianProjects\PBQ\data\redskill-new-top20.csv
python .\scripts\redskill_client.py top --list author --limit 20
python .\scripts\redskill_client.py search --query "writing" --limit 30
python .\scripts\redskill_client.py detail --skill-id 1519 --format json
python .\scripts\redskill_client.py top --list use --limit 20 --refresh
python .\scripts\redskill_client.py top --list use --limit 20 --no-cache
```

List aliases:

- `use`, `users`, `useList`
- `new`, `7d`, `newList`
- `today`, `daily`, `todayList`
- `author`, `authors`, `authorList`
- `all`, `allSkills`

## Answering Rules

- Be explicit about which list and metric was used.
- For search results, say whether the result came from a ranked list or only from `allSkills`.
- For Xiaohongshu note links, construct `https://www.xiaohongshu.com/explore/{note_id}` only when `note_id` exists.
- For author profile links, construct `https://www.xiaohongshu.com/user/profile/{author_id}` only when `author_id` exists.
- If a requested field is not present in the response, say that clearly instead of inferring it.
