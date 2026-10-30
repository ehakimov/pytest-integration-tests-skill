# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions: [SemVer](https://semver.org/).
The plugin version is `version` in `.claude-plugin/plugin.json`: change it together with the `vX.Y.Z` tag (the release workflow checks that they match).

## [1.0.0] - 2026-10-30

### Added

- Skill `pytest-integration-tests`: layers models → client → steps → test → asserts; templates of a test, steps, a client, models, assertions and fixtures; Allure report and parallel run rules; working in a project built differently; investigating failed and flaky tests; a checklist. UI and Kafka in `references/`.
- Skill `pytest-integration-bootstrap`: the core as real files in `templates/` and `scripts/scaffold.py` (HttpClient, authorization profiles oauth2 / basic / api_key, masked attachments, `wait_until`, report categories by exception class, Playwright fixtures, a Kafka listener, ruff layer rules, GitLab and GitHub CI with optional Allure TestOps); a table of common breakages.
- An example project with a demo stand, built from the skills, and failures on purpose for every report category.
- A Claude Code plugin and marketplace, skill zips for the Claude app.
- CI: the example matches the skills, tests pass, failures land in the right categories, no demo secret leaks into the report, POST is never retried, the Kafka listener works against a real broker, the plugin manifests are valid; a release runs the same checks and requires the tag to match the plugin version.
