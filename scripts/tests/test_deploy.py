"""Exercise deployment failure boundaries without Docker, SSH or a real database."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "deploy.sh"
SHA = "a" * 40
MOCKS = r'''
record() { printf '%s\n' "$*" >> "$TEST_LOG"; }
git() {
    record "git $*"
    case "$*" in
        'rev-parse --show-toplevel') pwd ;;
        'rev-parse --git-path ttc-deploy.lock') printf '.test-lock\n' ;;
        'status --porcelain') if [[ "$SCENARIO" == dirty ]]; then printf ' M tracked.txt\n'; fi ;;
        'rev-parse origin/main')
            if [[ "$SCENARIO" == moved ]]; then printf '%040d\n' 1; else printf '%s\n' "$TEST_SHA"; fi ;;
        'rev-parse HEAD') printf '%040d\n' 1 ;;
    esac
    return 0
}
flock() { [[ "$SCENARIO" != locked ]]; }
docker() {
    record "docker $*"
    if [[ "$*" == *'build api web' && "$SCENARIO" == build ]]; then return 1; fi
    if [[ "$*" == *'alembic upgrade head' && "$SCENARIO" == migration ]]; then return 1; fi
    if [[ "$*" == *'config --format json' ]]; then
        printf '{"services":{"web":{"environment":{"SITE_ADDRESS":"example.org"}}}}\n'
    fi
    return 0
}
sudo() {
    record "sudo $*"
    if [[ "$*" == '-n /usr/bin/systemctl start ttc-backup.service' && "$SCENARIO" == backup ]]; then return 1; fi
    return 0
}
systemctl() { printf 'success\n'; }
curl() {
    record "curl $*"
    if [[ "$SCENARIO" == health ]]; then return 1; fi
    if [[ "$*" == *'/api/event-categories' ]]; then printf '[]\n'; fi
    return 0
}
python3() { "$TEST_PYTHON" "$@"; }
source "$1" "$2" "$3"
'''


class DeploymentControlFlowTests(unittest.TestCase):
    def run_deployment(self, scenario):
        bash = (r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt"
                else shutil.which("bash"))
        self.assertTrue(bash, "Bash is required for deployment checks")
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / ".env.production").touch()
            log = project / "commands.log"
            result = subprocess.run(
                [bash, "--noprofile", "--norc", "-c", MOCKS, "test",
                 SCRIPT.as_posix(), project.as_posix(), SHA],
                env={**os.environ, "SCENARIO": scenario, "TEST_SHA": SHA,
                     "TEST_LOG": log.as_posix(), "TEST_PYTHON": Path(sys.executable).as_posix()},
                capture_output=True, text=True, timeout=20,
            )
            return result, log.read_text() if log.exists() else ""

    def test_success_orders_backup_migration_and_worker_start(self):
        result, log = self.run_deployment("success")
        self.assertEqual(result.returncode, 0, result.stderr)
        steps = ["build api web", "stop --timeout 30 api worker",
                 "sudo -n /usr/bin/systemctl start", "alembic upgrade head",
                 "alembic check", "up -d --no-deps", "/api/event-categories"]
        positions = [log.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("--wait-timeout 120 api web worker", log)
        self.assertIn(f"checkout --detach {SHA}", log)

    def test_dirty_checkout_moved_main_or_lock_aborts_before_checkout(self):
        for scenario in ("dirty", "moved", "locked"):
            with self.subTest(scenario=scenario):
                result, log = self.run_deployment(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("checkout --detach", log)
                self.assertNotIn("build api web", log)

    def test_build_failure_keeps_existing_services_running(self):
        result, log = self.run_deployment("build")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("stop --timeout", log)

    def test_backup_failure_prevents_migration(self):
        result, log = self.run_deployment("backup")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("alembic upgrade", log)
        self.assertNotIn("up -d", log)

    def test_migration_failure_prevents_application_start(self):
        result, log = self.run_deployment("migration")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("up -d", log)

    def test_health_failure_does_not_report_success(self):
        result, _ = self.run_deployment("health")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Deployment completed", result.stdout)


if __name__ == "__main__":
    unittest.main()
