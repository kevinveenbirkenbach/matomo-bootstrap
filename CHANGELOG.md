## [1.1.12] - 2026-02-14

* This release fixes the intermittent Matomo installer failure in the setupSuperUser step by adding more robust waiting logic and introduces E2E tests for deployments under very tight resource constraints.


## [1.1.11] - 2026-02-14

* This release improves matomo-bootstrap installer resilience by adding robust setupSuperUser field and button detection to prevent intermittent bootstrap failures.


## [1.1.10] - 2026-02-14

* This release fixes a reproducible Playwright navigation race in the Matomo installer (setupSuperUser), hardens the Next/Continue flow, and adds integration tests for transient locator errors and progress detection without a visible Next button.


## [1.1.9] - 2026-02-14

* Reworked CI to run on all branches while restricting Docker image publishing and stable tagging to tagged commits on main, using git-based SemVer detection.


## [1.1.8] - 2026-02-14

* Refactored CI to use a single coordinator workflow with strict SemVer-based release gating and adjusted Docker image publishing to strip the leading v from version tags.


## [1.1.7] - 2026-02-14

* Harden compose installer timeouts and e2e stack diagnostics


## [1.1.6] - 2026-02-14

* Add installer table-step timeout env vars (MATOMO_INSTALLER_TABLES_CREATION_TIMEOUT_S, MATOMO_INSTALLER_TABLES_ERASE_TIMEOUT_S) to compose/docs and e2e checks.


## [1.1.5] - 2026-02-14

* Harden web installer flow for nix e2e


## [1.1.4] - 2026-02-13

* This release hardens Matomo bootstrap by adding installer UI readiness waits/retries.


## [1.1.3] - 2026-02-12

* Increase Playwright step wait from 200ms to 1000ms to improve CI stability during Matomo installation.


## [1.1.2] - 2025-12-24

* **Improved error visibility during Matomo installation**: When the setup fails (for example due to an invalid admin email or missing required fields), the installer now **prints the actual Matomo error messages to the logs**, instead of failing with a generic error.


## [1.1.1] - 2025-12-24

* Improved Docker image publishing: automatic `vX.Y.Z`, `latest`, and `stable` tags for releases.


## [1.1.0] - 2025-12-23

* Implemented bootstrap docker image to auto install matomo in docker compose


## [1.0.1] - 2025-12-23

* * Support for running `matomo-bootstrap` **fully via Nix** in a clean, containerized environment.
* A **token-only stdout contract**: the bootstrap command now prints only the API token, making it safe for automation.
* Reproducible Nix builds via a pinned `flake.lock`.


## [1.0.0] - 2025-12-23

* 🥳

