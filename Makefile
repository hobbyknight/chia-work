.PHONY: smoke test experiments status

smoke:
	PYTHONPATH=src python scripts/smoke_test.py

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

experiments:
	PYTHONPATH=src python scripts/run_experiments.py --config configs/experiment.example.json

status:
	@cat CHECKPOINT.md
