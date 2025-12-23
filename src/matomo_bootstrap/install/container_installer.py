import subprocess


def ensure_installed(
    container_name: str = "e2e-matomo-1",
) -> None:
    """
    Ensure Matomo is installed by executing PHP bootstrap inside container.
    Idempotent: safe to run multiple times.
    """

    cmd = [
        "docker",
        "exec",
        container_name,
        "php",
        "-r",
        r"""
        if (file_exists('/var/www/html/config/config.ini.php')) {
            echo "Matomo already installed\n";
            exit(0);
        }

        require '/var/www/html/core/bootstrap.php';

        \Piwik\FrontController::getInstance()->init();
        \Piwik\Plugins\Installation\Installation::install();

        echo "Matomo installed\n";
        """
    ]

    subprocess.check_call(cmd)

