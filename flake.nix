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
      in
      rec {
        matomo-bootstrap = python.pkgs.buildPythonApplication {
          pname = "matomo-bootstrap";
          version = "1.0.1"; # keep in sync with pyproject.toml
          pyproject = true;
          src = self;

          nativeBuildInputs = with python.pkgs; [
            setuptools
            wheel
          ];

          propagatedBuildInputs = with python.pkgs; [
            playwright
          ];

          doCheck = false;

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

        pythonPlaywright = python.withPackages (ps: [
          ps.playwright
        ]);

        matomo = self.packages.${system}.matomo-bootstrap;

        playwright-install = pkgs.writeShellApplication {
          name = "matomo-bootstrap-playwright-install";
          runtimeInputs = [ pythonPlaywright ];

          text = ''
            # Install Playwright browsers.
            # IMPORTANT: Do not print anything to stdout (tests expect token-only stdout).
            exec ${pythonPlaywright}/bin/python -m playwright install chromium 1>&2
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
