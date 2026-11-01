"""Run the reviewed deterministic scenarios in catalogue order."""

from agent.cli import OUTPUT_ROOT, run_scenario
from . import SCENARIOS, STATE01, STATE02, MP01
from .state01 import run_restart
from .mp01 import assess as assess_multiplayer, run_multiplayer
from .state02 import assess as assess_followup, run_followup

failed = False
for name, case in SCENARIOS.items():
    output = OUTPUT_ROOT / name.lower()
    result = run_scenario(name, output=output)
    failures = case.assess(result)
    failed = failed or bool(failures)
    print(
        name + ": " + ("PASSED" if not failures else "FAILED: " + ", ".join(failures))
    )
    print("Trace: " + str(output / "trace.md"))
output = OUTPUT_ROOT / STATE01.lower()
failures = run_restart(output)
failed = failed or bool(failures)
print(STATE01 + ": " + ("PASSED" if not failures else "FAILED: " + ", ".join(failures)))
print("Trace: " + str(output / "trace.md"))
output = OUTPUT_ROOT / STATE02.lower()
failures = assess_followup(*run_followup(output))
failed = failed or bool(failures)
print(STATE02 + ": " + ("PASSED" if not failures else "FAILED: " + ", ".join(failures)))
print("Trace: " + str(output / "trace.md"))
output = OUTPUT_ROOT / MP01.lower()
failures = assess_multiplayer(run_multiplayer(output))
failed = failed or bool(failures)
print(MP01 + ": " + ("PASSED" if not failures else "FAILED: " + ", ".join(failures)))
print("Trace: " + str(output / "trace.md"))
print(
    "Evidence: real SDK orchestration; synthetic model and source data. Model quality is not assessed."
)
raise SystemExit(failed)
