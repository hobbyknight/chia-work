.PHONY: smoke test experiments real-chia real-agent gemmini-up real-gemmini real-agent-gemmini gemmini-down status

smoke:
	PYTHONPATH=src python scripts/smoke_test.py

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

experiments:
	PYTHONPATH=src python scripts/run_experiments.py --config configs/experiment.example.json

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

gemmini-down:
	chia down configs/chia-gemmini-local.yaml

status:
	@cat CHECKPOINT.md
