.PHONY: smoke test experiments safety-challenges capture-env real-chia real-agent gemmini-up real-gemmini real-agent-gemmini real-gemmini-sanity real-agent-gemmini-sanity real-gemmini-mvin-mvout real-agent-gemmini-mvin-mvout hardware-pilot gemmini-down status

smoke:
	PYTHONPATH=src python scripts/smoke_test.py

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

experiments:
	PYTHONPATH=src python scripts/run_experiments.py --config configs/experiment.example.json

safety-challenges:
	PYTHONPATH=src python scripts/evaluate_safety_challenges.py

capture-env:
	PYTHONPATH=src python scripts/capture_environment.py

real-chia:
	PYTHONPATH=src python scripts/real_chia_smoke.py

real-agent:
	PYTHONPATH=src python scripts/real_gemini_chia_smoke.py

gemmini-up:
	chia up configs/chia-gemmini-local.yaml

real-gemmini:
	chia job submit --working-dir . -- python scripts/real_gemmini_build.py

real-agent-gemmini:
	chia job submit --working-dir . -- python scripts/real_gemini_gemmini_build.py

real-gemmini-sanity:
	chia job submit --working-dir . -- python scripts/real_gemmini_sanity.py

real-agent-gemmini-sanity:
	chia job submit --working-dir . -- python scripts/real_gemini_gemmini_sanity.py

real-gemmini-mvin-mvout:
	chia job submit --working-dir . -- python scripts/real_gemmini_mvin_mvout.py

real-agent-gemmini-mvin-mvout:
	chia job submit --working-dir . -- python scripts/real_gemini_gemmini_mvin_mvout.py

hardware-pilot:
	chia job submit --working-dir . -- python scripts/run_real_hardware_pilot.py

gemmini-down:
	chia down configs/chia-gemmini-local.yaml

status:
	@cat CHECKPOINT.md
