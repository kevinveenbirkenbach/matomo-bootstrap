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

