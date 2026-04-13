.PHONY: install paso0 paso1 paso2 paso3 run test clean

install:
	pip install -r requirements.txt
	@echo "✓ Listo. Copia .env.example → .env y configura tus credenciales."

paso0:
	python step0_preparar.py

paso1:
	python step1_extraer.py

paso2:
	python step2_clasificar.py

paso3:
	python step3_llm.py

run:
	python main.py

test:
	pytest -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache logs/pipeline.log
