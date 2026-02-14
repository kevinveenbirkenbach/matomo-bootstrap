{
  description = "matomo-bootstrap";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
  let
    systems = [ "x86_64-linux" "aarch64-linux" ];
    forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);
  in
  {
    packages = forAllSystems (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python312;
        playwrightDriver = pkgs.playwright-driver;
      in
      rec {
        matomo-bootstrap = python.pkgs.buildPythonApplication {
          pname = "matomo-bootstrap";
          version = "1.1.12"; # keep in sync with pyproject.toml
          pyproject = true;
          src = self;

          # disable import-check phase (prevents Playwright/installer side effects)
          pythonImportsCheck = [ ];

          nativeBuildInputs =
            (with python.pkgs; [
              setuptools
              wheel
            ])
            ++ [
              pkgs.makeWrapper
            ];

          propagatedBuildInputs = with python.pkgs; [
            playwright
          ];

          doCheck = false;

          # IMPORTANT (Nix):
          # Do NOT let Playwright download ubuntu/fhs browser binaries into ~/.cache/ms-playwright.
          # Instead, point Playwright to nixpkgs-provided browsers (playwright-driver).
          #
          # This fixes errors like:
          #   BrowserType.launch ... headless_shell ENOENT
          #
          # ...which happens when Playwright downloads a fallback ubuntu build that cannot run on NixOS.
          postFixup = ''
            wrapProgram "$out/bin/matomo-bootstrap" \
              --set PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD 1 \
              --set PLAYWRIGHT_BROWSERS_PATH "${playwrightDriver.browsers}"
          '';

          meta = with pkgs.lib; {
            description = "Headless bootstrap tooling for Matomo (installation + API token provisioning)";
            homepage = "https://github.com/kevinveenbirkenbach/matomo-bootstrap";
            license = licenses.mit;
            mainProgram = "matomo-bootstrap";
          };
        };

        default = matomo-bootstrap;
      }
    );

    apps = forAllSystems (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python312;
        playwrightDriver = pkgs.playwright-driver;

        pythonPlaywright = python.withPackages (ps: [
          ps.playwright
        ]);

        matomo = self.packages.${system}.matomo-bootstrap;

        playwright-install = pkgs.writeShellApplication {
          name = "matomo-bootstrap-playwright-install";
          runtimeInputs = [ pythonPlaywright ];

          text = ''
            # Nix mode: NO browser downloads.
            #
            # Playwright upstream "install" downloads ubuntu/fhs browser binaries into ~/.cache/ms-playwright.
            # Those binaries often don't run on NixOS, producing ENOENT on launch (missing loader/libs).
            #
            # We keep this app for backwards-compat (tests/docs call it), but it is intentionally a NO-OP.
            #
            # IMPORTANT: Do not print anything to stdout (tests expect token-only stdout).
            {
              echo "Playwright browsers are provided by nixpkgs (playwright-driver)."
              echo "Using PLAYWRIGHT_BROWSERS_PATH=${playwrightDriver.browsers}"
              echo "Set PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 to prevent downloads."
            } 1>&2
            exit 0
          '';
        };
      in
      {
        matomo-bootstrap = {
          type = "app";
          program = "${matomo}/bin/matomo-bootstrap";
        };

        matomo-bootstrap-playwright-install = {
          type = "app";
          program = "${playwright-install}/bin/matomo-bootstrap-playwright-install";
        };

        default = self.apps.${system}.matomo-bootstrap;
      }
    );

    devShells = forAllSystems (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python312;
      in
      {
        default = pkgs.mkShell {
          packages = with pkgs; [
            python
            python.pkgs.ruff
          ];
        };
      }
    );
  };
}
